"""
🏃 Etapa 4 — Executor.

Recebe um comando já analisado (AST) e o executa sobre o armazenamento.
O SELECT vira um plano (``planner.py``) e basta puxar as linhas dele.
Os outros comandos — CREATE, INSERT, UPDATE, DELETE... — são executados
aqui mesmo, conferindo tipos e restrições antes de mexer nos dados.
"""

from . import nodes as n
from .datatypes import coerce, sql_literal
from .errors import CatalogError, ConstraintError, ExecutionError
from .expressions import compile_expr, evaluate_constant
from .operators import table_scope
from .planner import find_rows, plan_select
from .result import Result
from .schema import Column, TableSchema


class Executor:
    def __init__(self, storage):
        self.storage = storage

    def execute(self, stmt: n.Node) -> Result:
        match stmt:
            case n.Select():
                return self.select(stmt)
            case n.Insert():
                return self.insert(stmt)
            case n.Update():
                return self.update(stmt)
            case n.Delete():
                return self.delete(stmt)
            case n.CreateTable():
                return self.create_table(stmt)
            case n.DropTable():
                return self.drop_table(stmt)
            case n.CreateIndex():
                return self.create_index(stmt)
            case n.Explain():
                return self.explain(stmt)
        raise ExecutionError(f"Comando não suportado: {type(stmt).__name__}")

    # ─────────────────────────── consultas ───────────────────────────

    def select(self, stmt: n.Select) -> Result:
        plan = plan_select(stmt, self.storage)
        rows = list(plan.rows())
        columns = [slot.name for slot in plan.scope.slots]
        return Result(columns=columns, rows=rows, rowcount=len(rows))

    def explain(self, stmt: n.Explain) -> Result:
        plan = plan_select(stmt.statement, self.storage)
        return Result(columns=["plano"], rows=[(line,) for line in plan.explain()])

    # ─────────────────────────── definição (DDL) ───────────────────────────

    def create_table(self, stmt: n.CreateTable) -> Result:
        if stmt.name in self.storage.tables:
            if stmt.if_not_exists:
                return Result(message=f"A tabela '{stmt.name}' já existe — nada a fazer")
            raise CatalogError(f"A tabela '{stmt.name}' já existe")

        columns = []
        for definition in stmt.columns:
            if any(c.name == definition.name for c in columns):
                raise CatalogError(f"A coluna '{definition.name}' foi declarada duas vezes")
            default = None
            if definition.default is not None:
                default = coerce(evaluate_constant(definition.default), definition.type, definition.name)
            columns.append(Column(
                name=definition.name,
                type=definition.type,
                primary_key=definition.primary_key,
                not_null=definition.not_null or definition.primary_key,
                unique=definition.unique and not definition.primary_key,
                default=default,
                references=definition.references,
            ))

        if sum(c.primary_key for c in columns) > 1:
            raise CatalogError("Só uma coluna pode ser PRIMARY KEY (chaves compostas ficam de exercício!)")
        for column in columns:
            if column.references:
                self._check_reference_target(stmt.name, columns, column)

        self.storage.create_table(TableSchema(stmt.name, columns))
        return Result(message=f"Tabela '{stmt.name}' criada")

    def _check_reference_target(self, table_name, own_columns, column):
        target_table, target_column = column.references
        if target_table == table_name:  # referência à própria tabela
            target = next((c for c in own_columns if c.name == target_column), None)
            if target is None:
                raise CatalogError(f"A tabela '{table_name}' não tem a coluna '{target_column}'")
        else:
            target = self.storage.get_table(target_table).schema.column(target_column)
        if not (target.primary_key or target.unique):
            raise CatalogError(
                f"REFERENCES {target_table}({target_column}): a coluna referenciada "
                f"precisa ser PRIMARY KEY ou UNIQUE")
        if target.type != column.type:
            raise CatalogError(
                f"REFERENCES {target_table}({target_column}): os tipos não batem "
                f"({column.type} × {target.type})")

    def drop_table(self, stmt: n.DropTable) -> Result:
        if stmt.name not in self.storage.tables:
            if stmt.if_exists:
                return Result(message=f"A tabela '{stmt.name}' não existe — nada a fazer")
            raise CatalogError(f"A tabela '{stmt.name}' não existe")
        for other in self.storage.tables.values():
            if other.name == stmt.name:
                continue
            for column in other.schema.columns:
                if column.references and column.references[0] == stmt.name:
                    raise ConstraintError(
                        f"Não dá para apagar '{stmt.name}': {other.name}.{column.name} aponta para ela")
        self.storage.drop_table(stmt.name)
        return Result(message=f"Tabela '{stmt.name}' apagada")

    def create_index(self, stmt: n.CreateIndex) -> Result:
        if self.storage.find_index(stmt.name):
            raise CatalogError(f"Já existe um índice chamado '{stmt.name}'")
        table = self.storage.get_table(stmt.table)
        table.create_index(stmt.name, stmt.column, stmt.unique)
        return Result(message=f"Índice '{stmt.name}' criado em {stmt.table}({stmt.column})")

    # ─────────────────────────── dados (DML) ───────────────────────────

    def insert(self, stmt: n.Insert) -> Result:
        table = self.storage.get_table(stmt.table)
        schema = table.schema
        if stmt.columns is None:
            targets = schema.column_names
        else:
            targets = list(stmt.columns)
            for name in targets:
                schema.index_of(name)  # reclama se a coluna não existe
            if len(set(targets)) != len(targets):
                raise ExecutionError("Há colunas repetidas na lista do INSERT")

        for values in stmt.rows:
            if len(values) != len(targets):
                raise ExecutionError(
                    f"O INSERT tem {len(targets)} coluna(s), mas {len(values)} valor(es) nesta linha")
            given = dict(zip(targets, (evaluate_constant(v) for v in values)))
            row = [given.get(c.name, c.default) for c in schema.columns]

            # INTEGER PRIMARY KEY sem valor ganha o próximo número (auto-incremento)
            pk = schema.primary_key
            if pk and pk.type == "INTEGER":
                position = schema.index_of(pk.name)
                if row[position] is None:
                    row[position] = table.next_key()

            table.insert(self._validate_row(table, row))
        count = len(stmt.rows)
        return Result(message=f"{count} linha(s) inserida(s)", rowcount=count)

    def update(self, stmt: n.Update) -> Result:
        table = self.storage.get_table(stmt.table)
        scope = table_scope(table, table.name)
        assignments = [(table.schema.index_of(column), compile_expr(expr, scope))
                       for column, expr in stmt.assignments]

        matches = find_rows(table, stmt.where)
        for rowid, row in matches:
            old_values = tuple(row)
            new_row = list(row)
            for position, compute in assignments:
                new_row[position] = compute(old_values)  # sempre a partir dos valores antigos
            new_row = self._validate_row(table, new_row)
            self._check_not_referenced(table, row, new_row)
            table.update(rowid, new_row)
        return Result(message=f"{len(matches)} linha(s) atualizada(s)", rowcount=len(matches))

    def delete(self, stmt: n.Delete) -> Result:
        table = self.storage.get_table(stmt.table)
        matches = find_rows(table, stmt.where)
        for rowid, row in matches:
            self._check_not_referenced(table, row)
            table.delete(rowid)
        return Result(message=f"{len(matches)} linha(s) apagada(s)", rowcount=len(matches))

    # ─────────────────────────── restrições ───────────────────────────

    def _validate_row(self, table, row: list) -> list:
        """Confere tipos, NOT NULL e REFERENCES. (PK e UNIQUE são com a tabela.)"""
        checked = []
        for column, value in zip(table.schema.columns, row):
            value = coerce(value, column.type, column.name)
            if value is None and column.not_null:
                raise ConstraintError(f"NOT NULL violada: {table.name}.{column.name} não aceita NULL")
            checked.append(value)

        for column, value in zip(table.schema.columns, checked):
            if column.references is None or value is None:
                continue
            target_name, target_column = column.references
            target = self.storage.get_table(target_name)
            if not target.index_for(target_column).lookup(value):
                raise ConstraintError(
                    f"REFERENCES violada: não existe {target_name}.{target_column} = {sql_literal(value)}")
        return checked

    def _check_not_referenced(self, table, old_row: list, new_row: list | None = None) -> None:
        """Impede apagar (ou mudar a chave de) uma linha que outra tabela usa."""
        for other in self.storage.tables.values():
            for position, column in enumerate(other.schema.columns):
                if not column.references or column.references[0] != table.name:
                    continue
                key_position = table.schema.index_of(column.references[1])
                value = old_row[key_position]
                if value is None or (new_row is not None and new_row[key_position] == value):
                    continue
                if any(row[position] == value for row in other.rows.values()):
                    raise ConstraintError(
                        f"REFERENCES violada: {other.name}.{column.name} ainda aponta para "
                        f"{table.name}.{column.references[1]} = {sql_literal(value)}")
