"""
🌳 A árvore sintática (AST).

O parser transforma tokens nestes objetos. Cada classe representa uma
construção do SQL. São *dataclasses* imutáveis (``frozen``): podem ser
comparadas com ``==`` e usadas como chave de dicionário — o planejador
usa isso para perceber que o ``COUNT(*)`` do SELECT é o mesmo do HAVING.

    SELECT nome FROM tatus WHERE idade > 3

vira

    Select(
        items=(SelectItem(Column('nome')),),
        from_=TableRef('tatus'),
        where=Binary('>', Column('idade'), Literal(3)),
    )
"""

from dataclasses import dataclass, fields, replace
from typing import Any

from .datatypes import sql_literal


class Node:
    """Base de todos os nós da árvore."""


# ───────────────────────────── Expressões ─────────────────────────────

# Força de cada operador binário (usada só para imprimir com parênteses certos)
PRECEDENCE = {
    "OR": 1, "AND": 2,
    "=": 4, "!=": 4, "<": 4, "<=": 4, ">": 4, ">=": 4,
    "+": 5, "-": 5, "||": 5,
    "*": 6, "/": 6, "%": 6,
}


@dataclass(frozen=True)
class Literal(Node):
    value: Any

    def __str__(self):
        return sql_literal(self.value)


@dataclass(frozen=True)
class Param(Node):
    """Um ``?`` esperando valor (posição ``index``, começando em 0)."""
    index: int

    def __str__(self):
        return "?"


@dataclass(frozen=True)
class Column(Node):
    name: str
    table: str | None = None

    def __str__(self):
        return f"{self.table}.{self.name}" if self.table else self.name


@dataclass(frozen=True)
class Star(Node):
    """``*`` ou ``tabela.*``."""
    table: str | None = None

    def __str__(self):
        return f"{self.table}.*" if self.table else "*"


@dataclass(frozen=True)
class Unary(Node):
    op: str  # "-" ou "NOT"
    operand: Node

    def __str__(self):
        return f"NOT {self.operand}" if self.op == "NOT" else f"-{self.operand}"


@dataclass(frozen=True)
class Binary(Node):
    op: str
    left: Node
    right: Node

    def __str__(self):
        me = PRECEDENCE[self.op]

        def wrap(child, is_right):
            if isinstance(child, Binary):
                theirs = PRECEDENCE[child.op]
                if theirs < me or (is_right and theirs == me):
                    return f"({child})"
            return str(child)

        return f"{wrap(self.left, False)} {self.op} {wrap(self.right, True)}"


@dataclass(frozen=True)
class IsNull(Node):
    operand: Node
    negated: bool = False

    def __str__(self):
        return f"{self.operand} IS {'NOT ' if self.negated else ''}NULL"


@dataclass(frozen=True)
class InList(Node):
    operand: Node
    items: tuple
    negated: bool = False

    def __str__(self):
        items = ", ".join(map(str, self.items))
        return f"{self.operand} {'NOT ' if self.negated else ''}IN ({items})"


@dataclass(frozen=True)
class Between(Node):
    operand: Node
    low: Node
    high: Node
    negated: bool = False

    def __str__(self):
        return f"{self.operand} {'NOT ' if self.negated else ''}BETWEEN {self.low} AND {self.high}"


@dataclass(frozen=True)
class Like(Node):
    operand: Node
    pattern: Node
    negated: bool = False

    def __str__(self):
        return f"{self.operand} {'NOT ' if self.negated else ''}LIKE {self.pattern}"


@dataclass(frozen=True)
class Call(Node):
    """Chamada de função: ``UPPER(nome)``, ``COUNT(*)``, ``SUM(DISTINCT x)``."""
    name: str  # sempre em maiúsculas
    args: tuple = ()
    distinct: bool = False
    star: bool = False  # COUNT(*)

    def __str__(self):
        if self.star:
            return f"{self.name}(*)"
        prefix = "DISTINCT " if self.distinct else ""
        return f"{self.name}({prefix}{', '.join(map(str, self.args))})"


# ────────────────────────────── Comandos ──────────────────────────────

@dataclass(frozen=True)
class ColumnDef(Node):
    name: str
    type: str
    primary_key: bool = False
    not_null: bool = False
    unique: bool = False
    default: Node | None = None
    references: tuple | None = None  # (tabela, coluna)


@dataclass(frozen=True)
class CreateTable(Node):
    name: str
    columns: tuple
    if_not_exists: bool = False


@dataclass(frozen=True)
class DropTable(Node):
    name: str
    if_exists: bool = False


@dataclass(frozen=True)
class CreateIndex(Node):
    name: str
    table: str
    column: str
    unique: bool = False


@dataclass(frozen=True)
class Insert(Node):
    table: str
    columns: tuple | None  # None = todas as colunas, na ordem da tabela
    rows: tuple            # tupla de tuplas de expressões


@dataclass(frozen=True)
class TableRef(Node):
    name: str
    alias: str | None = None

    @property
    def ref_name(self) -> str:
        """Como as colunas desta tabela são qualificadas: ``t.nome``."""
        return self.alias or self.name

    def __str__(self):
        return f"{self.name} AS {self.alias}" if self.alias else self.name


@dataclass(frozen=True)
class Join(Node):
    kind: str  # INNER, LEFT ou CROSS
    table: TableRef
    on: Node | None = None


@dataclass(frozen=True)
class SelectItem(Node):
    expr: Node
    alias: str | None = None


@dataclass(frozen=True)
class OrderItem(Node):
    expr: Node
    desc: bool = False

    def __str__(self):
        return f"{self.expr} DESC" if self.desc else str(self.expr)


@dataclass(frozen=True)
class Select(Node):
    items: tuple
    from_: TableRef | None = None
    joins: tuple = ()
    where: Node | None = None
    group_by: tuple = ()
    having: Node | None = None
    order_by: tuple = ()
    limit: Node | None = None
    offset: Node | None = None
    distinct: bool = False


@dataclass(frozen=True)
class Update(Node):
    table: str
    assignments: tuple  # tupla de (coluna, expressão)
    where: Node | None = None


@dataclass(frozen=True)
class Delete(Node):
    table: str
    where: Node | None = None


@dataclass(frozen=True)
class Begin(Node):
    pass


@dataclass(frozen=True)
class Commit(Node):
    pass


@dataclass(frozen=True)
class Rollback(Node):
    pass


@dataclass(frozen=True)
class Explain(Node):
    statement: Select


# ──────────────────────── Passeando pela árvore ───────────────────────

def walk(node: Node):
    """Visita ``node`` e todos os seus descendentes (pré-ordem)."""
    yield node
    for f in fields(node):
        yield from _nodes_in(getattr(node, f.name))


def _nodes_in(value):
    if isinstance(value, Node):
        yield from walk(value)
    elif isinstance(value, tuple):
        for item in value:
            yield from _nodes_in(item)


def transform(node: Node, fn) -> Node:
    """Reconstrói a árvore de baixo para cima, aplicando ``fn`` em cada nó.

    Como os nós são imutáveis, nada é alterado no lugar: devolvemos uma
    árvore nova (reaproveitando os galhos que não mudaram).
    """
    changes = {}
    for f in fields(node):
        old = getattr(node, f.name)
        new = _transform_value(old, fn)
        if new is not old:
            changes[f.name] = new
    if changes:
        node = replace(node, **changes)
    return fn(node)


def _transform_value(value, fn):
    if isinstance(value, Node):
        return transform(value, fn)
    if isinstance(value, tuple):
        new = tuple(_transform_value(item, fn) for item in value)
        return new if any(a is not b for a, b in zip(new, value)) else value
    return value
