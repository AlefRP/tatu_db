"""
🌳 Etapa 2 — Parser (analisador sintático).

Lê a lista de tokens e monta a árvore sintática (AST) de ``nodes.py``.
É um parser *descendente recursivo*: cada regra da gramática vira um
método, e os métodos chamam uns aos outros seguindo a gramática.

As expressões são montadas por níveis de precedência, do mais fraco
para o mais forte:

    OR  →  AND  →  NOT  →  = < > IS IN LIKE BETWEEN  →  + - ||  →  * / %  →  -x  →  átomo

Cada nível só chama o nível seguinte. Por isso ``1 + 2 * 3`` vira
``1 + (2 * 3)``: o ``*`` é resolvido "mais embaixo", antes do ``+``.
"""

from . import nodes as n
from .datatypes import normalize_type
from .errors import TatuSyntaxError
from .tokenizer import Token, tokenize

COMPARISON_OPS = ("=", "!=", "<>", "<", "<=", ">", ">=")


def parse(sql: str) -> list[n.Node]:
    """Analisa um ou mais comandos separados por ``;``."""
    return Parser(sql).parse_script()


class Parser:
    def __init__(self, sql: str):
        self.sql = sql
        self.tokens = tokenize(sql)
        self.i = 0
        self.param_count = 0

    # ─────────────────────── utilidades de leitura ───────────────────────

    @property
    def tok(self) -> Token:
        """O token da vez (ainda não consumido)."""
        return self.tokens[self.i]

    def advance(self) -> Token:
        token = self.tokens[self.i]
        if token.kind != "EOF":
            self.i += 1
        return token

    def check(self, kind: str, value=None) -> bool:
        return self.tok.kind == kind and (value is None or self.tok.value == value)

    def accept(self, kind: str, value=None) -> Token | None:
        """Consome o token se ele for o esperado; senão, não faz nada."""
        return self.advance() if self.check(kind, value) else None

    def accept_kw(self, word: str):
        return self.accept("KEYWORD", word)

    def accept_sym(self, symbol: str):
        return self.accept("SYMBOL", symbol)

    def expect_kw(self, word: str) -> Token:
        if self.check("KEYWORD", word):
            return self.advance()
        raise self.error(f"Esperava {word}")

    def expect_sym(self, symbol: str) -> Token:
        if self.check("SYMBOL", symbol):
            return self.advance()
        raise self.error(f"Esperava '{symbol}'")

    def identifier(self, what: str = "um nome") -> str:
        if self.check("IDENT"):
            return self.advance().value
        raise self.error(f"Esperava {what}")

    def error(self, message: str) -> TatuSyntaxError:
        token = self.tok
        if token.kind == "EOF":
            found = "o fim do comando"
        elif token.kind == "STRING":
            found = f"o texto '{token.value}'"
        elif token.kind in ("IDENT", "KEYWORD") and not self.sql.startswith('"', token.pos):
            found = f"'{self.sql[token.pos:token.pos + len(token.value)]}'"  # como foi digitado
        else:
            found = f"'{token.value}'"
        return TatuSyntaxError(f"{message}, mas encontrei {found}", self.sql, token.pos)

    # ───────────────────────────── comandos ─────────────────────────────

    def parse_script(self) -> list[n.Node]:
        statements = []
        while True:
            while self.accept_sym(";"):
                pass
            if self.check("EOF"):
                return statements
            statements.append(self.statement())
            if not self.check("EOF"):
                self.expect_sym(";")

    def statement(self) -> n.Node:
        handlers = {
            "SELECT": self.select, "INSERT": self.insert, "UPDATE": self.update,
            "DELETE": self.delete, "CREATE": self.create, "DROP": self.drop,
            "BEGIN": self.begin, "COMMIT": self.commit, "ROLLBACK": self.rollback,
            "EXPLAIN": self.explain,
        }
        handler = handlers.get(self.tok.value) if self.tok.kind == "KEYWORD" else None
        if handler is None:
            raise self.error("Esperava um comando (SELECT, INSERT, UPDATE, DELETE, CREATE...)")
        return handler()

    # CREATE TABLE / CREATE [UNIQUE] INDEX

    def create(self) -> n.Node:
        self.expect_kw("CREATE")
        if self.accept_kw("TABLE"):
            return self.create_table()
        unique = bool(self.accept_kw("UNIQUE"))
        if self.accept_kw("INDEX"):
            return self.create_index(unique)
        raise self.error("Esperava TABLE ou INDEX depois de CREATE")

    def create_table(self) -> n.CreateTable:
        if_not_exists = False
        if self.accept_kw("IF"):
            self.expect_kw("NOT")
            self.expect_kw("EXISTS")
            if_not_exists = True
        name = self.identifier("o nome da tabela")
        self.expect_sym("(")
        columns = [self.column_def()]
        while self.accept_sym(","):
            columns.append(self.column_def())
        self.expect_sym(")")
        return n.CreateTable(name, tuple(columns), if_not_exists)

    def column_def(self) -> n.ColumnDef:
        name = self.identifier("o nome da coluna")
        if not self.check("IDENT"):
            raise self.error(f"Esperava o tipo da coluna '{name}' (INTEGER, REAL, TEXT ou BOOLEAN)")
        type_token = self.advance()
        type_name = normalize_type(type_token.value)
        if type_name is None:
            raise TatuSyntaxError(
                f"Tipo desconhecido '{type_token.value}' — use INTEGER, REAL, TEXT ou BOOLEAN",
                self.sql, type_token.pos)
        if self.accept_sym("("):  # VARCHAR(80): o tamanho é aceito e ignorado
            if not self.accept("NUMBER"):
                raise self.error("Esperava o tamanho do tipo")
            self.expect_sym(")")

        primary_key = not_null = unique = False
        default = references = None
        while True:
            if self.accept_kw("PRIMARY"):
                self.expect_kw("KEY")
                primary_key = True
            elif self.accept_kw("NOT"):
                self.expect_kw("NULL")
                not_null = True
            elif self.accept_kw("NULL"):
                pass  # "pode ser nulo" — já é o padrão
            elif self.accept_kw("UNIQUE"):
                unique = True
            elif self.accept_kw("DEFAULT"):
                default = self.unary()
            elif self.accept_kw("REFERENCES"):
                table = self.identifier("o nome da tabela referenciada")
                self.expect_sym("(")
                column = self.identifier("o nome da coluna referenciada")
                self.expect_sym(")")
                references = (table, column)
            else:
                break
        return n.ColumnDef(name, type_name, primary_key, not_null, unique, default, references)

    def create_index(self, unique: bool) -> n.CreateIndex:
        name = self.identifier("o nome do índice")
        self.expect_kw("ON")
        table = self.identifier("o nome da tabela")
        self.expect_sym("(")
        column = self.identifier("o nome da coluna")
        self.expect_sym(")")
        return n.CreateIndex(name, table, column, unique)

    # DROP TABLE

    def drop(self) -> n.DropTable:
        self.expect_kw("DROP")
        self.expect_kw("TABLE")
        if_exists = False
        if self.accept_kw("IF"):
            self.expect_kw("EXISTS")
            if_exists = True
        return n.DropTable(self.identifier("o nome da tabela"), if_exists)

    # INSERT INTO t [(colunas)] VALUES (...), (...)

    def insert(self) -> n.Insert:
        self.expect_kw("INSERT")
        self.expect_kw("INTO")
        table = self.identifier("o nome da tabela")
        columns = None
        if self.accept_sym("("):
            columns = [self.identifier("o nome da coluna")]
            while self.accept_sym(","):
                columns.append(self.identifier("o nome da coluna"))
            self.expect_sym(")")
            columns = tuple(columns)
        self.expect_kw("VALUES")
        rows = [self.value_row()]
        while self.accept_sym(","):
            rows.append(self.value_row())
        return n.Insert(table, columns, tuple(rows))

    def value_row(self) -> tuple:
        self.expect_sym("(")
        values = self.expr_list()
        self.expect_sym(")")
        return values

    # SELECT

    def select(self) -> n.Select:
        self.expect_kw("SELECT")
        distinct = bool(self.accept_kw("DISTINCT"))
        items = [self.select_item()]
        while self.accept_sym(","):
            items.append(self.select_item())

        from_, joins = None, ()
        if self.accept_kw("FROM"):
            from_ = self.table_ref()
            joins = self.joins()

        where = self.expr() if self.accept_kw("WHERE") else None

        group_by = ()
        if self.accept_kw("GROUP"):
            self.expect_kw("BY")
            group_by = self.expr_list()

        having = self.expr() if self.accept_kw("HAVING") else None

        order_by = []
        if self.accept_kw("ORDER"):
            self.expect_kw("BY")
            order_by.append(self.order_item())
            while self.accept_sym(","):
                order_by.append(self.order_item())

        limit = offset = None
        if self.accept_kw("LIMIT"):
            limit = self.expr()
            if self.accept_kw("OFFSET"):
                offset = self.expr()

        return n.Select(tuple(items), from_, joins, where, group_by, having,
                        tuple(order_by), limit, offset, distinct)

    def select_item(self) -> n.SelectItem:
        if self.accept_sym("*"):
            return n.SelectItem(n.Star())
        expr = self.expr()
        alias = None
        if self.accept_kw("AS"):
            alias = self.identifier("um apelido (alias)")
        elif self.check("IDENT"):  # o AS é opcional: SELECT nome apelido
            alias = self.advance().value
        return n.SelectItem(expr, alias)

    def table_ref(self) -> n.TableRef:
        name = self.identifier("o nome da tabela")
        alias = None
        if self.accept_kw("AS"):
            alias = self.identifier("um apelido (alias)")
        elif self.check("IDENT"):
            alias = self.advance().value
        return n.TableRef(name, alias)

    def joins(self) -> tuple:
        joins = []
        while True:
            if self.accept_sym(","):  # FROM a, b  ==  FROM a CROSS JOIN b
                joins.append(n.Join("CROSS", self.table_ref()))
                continue
            if self.accept_kw("CROSS"):
                self.expect_kw("JOIN")
                joins.append(n.Join("CROSS", self.table_ref()))
                continue
            if self.accept_kw("LEFT"):
                self.accept_kw("OUTER")
                self.expect_kw("JOIN")
                kind = "LEFT"
            elif self.accept_kw("INNER"):
                self.expect_kw("JOIN")
                kind = "INNER"
            elif self.accept_kw("JOIN"):
                kind = "INNER"
            else:
                return tuple(joins)
            table = self.table_ref()
            self.expect_kw("ON")
            joins.append(n.Join(kind, table, self.expr()))

    def order_item(self) -> n.OrderItem:
        expr = self.expr()
        if self.accept_kw("DESC"):
            return n.OrderItem(expr, desc=True)
        self.accept_kw("ASC")
        return n.OrderItem(expr)

    # UPDATE t SET a = 1, b = 2 [WHERE ...]

    def update(self) -> n.Update:
        self.expect_kw("UPDATE")
        table = self.identifier("o nome da tabela")
        self.expect_kw("SET")
        assignments = [self.assignment()]
        while self.accept_sym(","):
            assignments.append(self.assignment())
        where = self.expr() if self.accept_kw("WHERE") else None
        return n.Update(table, tuple(assignments), where)

    def assignment(self) -> tuple:
        column = self.identifier("o nome da coluna")
        self.expect_sym("=")
        return (column, self.expr())

    # DELETE FROM t [WHERE ...]

    def delete(self) -> n.Delete:
        self.expect_kw("DELETE")
        self.expect_kw("FROM")
        table = self.identifier("o nome da tabela")
        where = self.expr() if self.accept_kw("WHERE") else None
        return n.Delete(table, where)

    # Transações e EXPLAIN

    def begin(self) -> n.Begin:
        self.expect_kw("BEGIN")
        self.accept_kw("TRANSACTION")
        return n.Begin()

    def commit(self) -> n.Commit:
        self.expect_kw("COMMIT")
        return n.Commit()

    def rollback(self) -> n.Rollback:
        self.expect_kw("ROLLBACK")
        return n.Rollback()

    def explain(self) -> n.Explain:
        self.expect_kw("EXPLAIN")
        return n.Explain(self.select())

    # ──────────────────── expressões (por precedência) ────────────────────

    def expr(self) -> n.Node:
        return self.or_expr()

    def expr_list(self) -> tuple:
        items = [self.expr()]
        while self.accept_sym(","):
            items.append(self.expr())
        return tuple(items)

    def or_expr(self) -> n.Node:
        left = self.and_expr()
        while self.accept_kw("OR"):
            left = n.Binary("OR", left, self.and_expr())
        return left

    def and_expr(self) -> n.Node:
        left = self.not_expr()
        while self.accept_kw("AND"):
            left = n.Binary("AND", left, self.not_expr())
        return left

    def not_expr(self) -> n.Node:
        if self.accept_kw("NOT"):
            return n.Unary("NOT", self.not_expr())
        return self.comparison()

    def comparison(self) -> n.Node:
        left = self.additive()

        if self.check("SYMBOL") and self.tok.value in COMPARISON_OPS:
            op = self.advance().value
            return n.Binary("!=" if op == "<>" else op, left, self.additive())

        if self.accept_kw("IS"):
            negated = bool(self.accept_kw("NOT"))
            self.expect_kw("NULL")
            return n.IsNull(left, negated)

        negated = bool(self.accept_kw("NOT"))
        if self.accept_kw("IN"):
            self.expect_sym("(")
            items = self.expr_list()
            self.expect_sym(")")
            return n.InList(left, items, negated)
        if self.accept_kw("BETWEEN"):
            low = self.additive()  # additive, e não expr: o AND aqui é do BETWEEN
            self.expect_kw("AND")
            return n.Between(left, low, self.additive(), negated)
        if self.accept_kw("LIKE"):
            return n.Like(left, self.additive(), negated)
        if negated:
            raise self.error("Esperava IN, BETWEEN ou LIKE depois de NOT")
        return left

    def additive(self) -> n.Node:
        left = self.multiplicative()
        while self.check("SYMBOL") and self.tok.value in ("+", "-", "||"):
            op = self.advance().value
            left = n.Binary(op, left, self.multiplicative())
        return left

    def multiplicative(self) -> n.Node:
        left = self.unary()
        while self.check("SYMBOL") and self.tok.value in ("*", "/", "%"):
            op = self.advance().value
            left = n.Binary(op, left, self.unary())
        return left

    def unary(self) -> n.Node:
        if self.accept_sym("-"):
            operand = self.unary()
            # -5 já vira o literal -5 (em vez de "negativo de 5")
            if isinstance(operand, n.Literal) and type(operand.value) in (int, float):
                return n.Literal(-operand.value)
            return n.Unary("-", operand)
        if self.accept_sym("+"):
            return self.unary()
        return self.primary()

    def primary(self) -> n.Node:
        token = self.tok
        if token.kind in ("NUMBER", "STRING"):
            self.advance()
            return n.Literal(token.value)
        if token.kind == "PARAM":
            self.advance()
            self.param_count += 1
            return n.Param(self.param_count - 1)
        if self.accept_kw("NULL"):
            return n.Literal(None)
        if self.accept_kw("TRUE"):
            return n.Literal(True)
        if self.accept_kw("FALSE"):
            return n.Literal(False)
        if self.accept_sym("("):
            expr = self.expr()
            self.expect_sym(")")
            return expr
        if token.kind == "IDENT":
            self.advance()
            if self.accept_sym("("):  # nome( → chamada de função
                return self.call(token.value.upper())
            if self.accept_sym("."):  # tabela.coluna ou tabela.*
                if self.accept_sym("*"):
                    return n.Star(token.value)
                return n.Column(self.identifier("o nome da coluna"), token.value)
            return n.Column(token.value)
        raise self.error("Esperava um valor, uma coluna ou uma expressão")

    def call(self, name: str) -> n.Call:
        if self.accept_sym("*"):
            self.expect_sym(")")
            return n.Call(name, star=True)
        distinct = bool(self.accept_kw("DISTINCT"))
        args = () if self.check("SYMBOL", ")") else self.expr_list()
        self.expect_sym(")")
        return n.Call(name, args, distinct)
