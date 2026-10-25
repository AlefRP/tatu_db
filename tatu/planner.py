"""
🧭 Etapa 3 — Planejador.

Recebe a AST de um SELECT e monta a árvore de operadores que vai
executá-lo. A ordem das etapas é a ordem *lógica* do SQL — que é
diferente da ordem em que a gente escreve!

    escrevemos:  SELECT … FROM … WHERE … GROUP BY … HAVING … ORDER BY … LIMIT
    executamos:  FROM → WHERE → GROUP BY → HAVING → ORDER BY → SELECT → DISTINCT → LIMIT

O planejador também faz uma otimização clássica: se o WHERE tem
``coluna = valor`` e essa coluna tem índice, ele troca a varredura
completa (SeqScan) por uma busca no índice (IndexScan).
"""

from dataclasses import replace

from . import nodes as n
from .datatypes import family, type_family
from .errors import CatalogError, ExecutionError
from .expressions import Scope, compile_expr, is_aggregate, truth
from .operators import (
    Distinct,
    Filter,
    HashAggregate,
    IndexScan,
    Limit,
    NestedLoopJoin,
    Operator,
    Project,
    SeqScan,
    SingleRow,
    Sort,
    table_scope,
)


def plan_select(stmt: n.Select, storage) -> Operator:
    """Monta o plano de um SELECT, de baixo (FROM) para cima (LIMIT)."""
    conditions = split_and(stmt.where)

    # 1. FROM + JOINs: de onde vêm as linhas
    if stmt.from_ is None:
        node = SingleRow()
    else:
        refs = [stmt.from_] + [join.table for join in stmt.joins]
        _check_unique_names(refs)
        tables = [storage.get_table(ref.name) for ref in refs]
        everything = Scope([])
        for table, ref in zip(tables, refs):
            everything = everything + table_scope(table, ref.ref_name)

        # a primeira tabela pode ser lida por índice, se o WHERE ajudar
        node, conditions = _access_path(tables[0], refs[0].ref_name, conditions, everything)
        for join, table in zip(stmt.joins, tables[1:]):
            right = SeqScan(table, join.table.ref_name)
            node = NestedLoopJoin(node, right, join.kind, join.on)

    # 2. WHERE: o que sobrou das condições vira um filtro
    if conditions:
        node = Filter(node, join_and(conditions))

    # 3. GROUP BY + agregações (COUNT, SUM...) e HAVING
    order_by = [_resolve_order_item(item, stmt.items) for item in stmt.order_by]
    calls = collect_aggregates([item.expr for item in stmt.items]
                               + [stmt.having] + [item.expr for item in order_by])
    if stmt.group_by or calls:
        node = HashAggregate(node, list(stmt.group_by), calls)
        if stmt.having is not None:
            node = Filter(node, stmt.having)
    elif stmt.having is not None:
        raise ExecutionError("HAVING só pode ser usado com GROUP BY ou com agregações")

    # 4. ORDER BY (antes da projeção: pode ordenar por colunas que não aparecem)
    if order_by:
        node = Sort(node, order_by)

    # 5. SELECT: escolhe/calcula as colunas de saída
    node = Project(node, list(stmt.items))
    if stmt.distinct:
        node = Distinct(node)

    # 6. LIMIT / OFFSET
    if stmt.limit is not None or stmt.offset is not None:
        node = Limit(node, _constant_int(stmt.limit, "LIMIT"),
                     _constant_int(stmt.offset, "OFFSET") or 0)
    return node


def find_rows(table, where: n.Node | None) -> list[tuple[int, list]]:
    """Linhas ``(rowid, linha)`` que satisfazem o WHERE — usado por UPDATE e DELETE."""
    scope = table_scope(table, table.name)
    conditions = split_and(where)
    choice = _choose_index(table, table.name, conditions, scope)
    if choice:
        index, value, conditions = choice
        candidates = [(rowid, table.rows[rowid]) for rowid in sorted(index.lookup(value))]
    else:
        candidates = list(table.scan())
    if not conditions:
        return candidates
    predicate = compile_expr(join_and(conditions), scope)
    return [(rowid, row) for rowid, row in candidates if truth(predicate(tuple(row))) is True]


# ─────────────────────────── escolha de índice ───────────────────────────

def _access_path(table, ref_name, conditions, scope):
    choice = _choose_index(table, ref_name, conditions, scope)
    if choice:
        index, value, rest = choice
        return IndexScan(table, ref_name, index, value), rest
    return SeqScan(table, ref_name), conditions


def _choose_index(table, ref_name, conditions, scope):
    """Procura uma condição ``coluna = constante`` que um índice responda.

    Devolve ``(índice, valor, condições_restantes)`` ou ``None``.
    """
    for condition in conditions:
        if not (isinstance(condition, n.Binary) and condition.op == "="):
            continue
        for column, literal in ((condition.left, condition.right),
                                (condition.right, condition.left)):
            if not (isinstance(column, n.Column) and isinstance(literal, n.Literal)):
                continue
            try:
                slot = scope.slots[scope.resolve(column)]
            except CatalogError:
                continue  # coluna ambígua ou inexistente: o Filter vai reclamar
            if slot.table != ref_name:
                continue  # é coluna de outra tabela do JOIN
            index = table.index_for(column.name)
            column_type = table.schema.column(column.name).type
            # Só usamos o índice se o tipo bate; senão o Filter reporta o erro.
            if index and family(literal.value) == type_family(column_type):
                rest = [c for c in conditions if c is not condition]
                return index, literal.value, rest
    return None


# ─────────────────────────── utilidades ───────────────────────────

def split_and(expr: n.Node | None) -> list[n.Node]:
    """``a AND b AND c`` → ``[a, b, c]``."""
    if expr is None:
        return []
    if isinstance(expr, n.Binary) and expr.op == "AND":
        return split_and(expr.left) + split_and(expr.right)
    return [expr]


def join_and(conditions: list[n.Node]) -> n.Node:
    """``[a, b, c]`` → ``a AND b AND c``."""
    result = conditions[0]
    for condition in conditions[1:]:
        result = n.Binary("AND", result, condition)
    return result


def collect_aggregates(exprs) -> list[n.Call]:
    """Acha as agregações usadas (sem repetir): ``[COUNT(*), SUM(peso)]``."""
    found = []
    for expr in exprs:
        if expr is None:
            continue
        for node in n.walk(expr):
            if not is_aggregate(node):
                continue
            if any(is_aggregate(inner) for arg in node.args for inner in n.walk(arg)):
                raise ExecutionError(f"Agregação dentro de agregação não é permitida: {node}")
            if not node.star and len(node.args) != 1:
                raise ExecutionError(f"{node.name}() recebe exatamente 1 argumento")
            if node.star and node.name != "COUNT":
                raise ExecutionError(f"Só COUNT aceita '*' — {node.name}(*) não existe")
            if node not in found:
                found.append(node)
    return found


def _resolve_order_item(item: n.OrderItem, select_items) -> n.OrderItem:
    """``ORDER BY 2`` e ``ORDER BY apelido`` viram a expressão do SELECT."""
    expr = item.expr
    if isinstance(expr, n.Literal) and type(expr.value) is int:
        position = expr.value
        if not 1 <= position <= len(select_items) or isinstance(select_items[position - 1].expr, n.Star):
            raise ExecutionError(f"ORDER BY {position}: não existe a coluna {position} no SELECT")
        return replace(item, expr=select_items[position - 1].expr)
    if isinstance(expr, n.Column) and expr.table is None:
        for select_item in select_items:
            if select_item.alias == expr.name:
                return replace(item, expr=select_item.expr)
    return item


def _check_unique_names(refs) -> None:
    seen = set()
    for ref in refs:
        if ref.ref_name in seen:
            raise CatalogError(
                f"A tabela '{ref.ref_name}' aparece duas vezes no FROM — "
                f"dê um apelido para cada uma (ex.: {ref.name} AS outro)")
        seen.add(ref.ref_name)


def _constant_int(expr: n.Node | None, what: str) -> int | None:
    if expr is None:
        return None
    if isinstance(expr, n.Literal) and type(expr.value) is int and expr.value >= 0:
        return expr.value
    raise ExecutionError(f"{what} precisa ser um número inteiro não negativo")
