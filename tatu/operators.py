"""
⚙️ Operadores — o modelo "Volcano" (de iteradores).

Um plano de execução é uma árvore de operadores. Cada operador tem um
método ``rows()`` que *puxa* linhas dos filhos, faz o seu trabalho e as
entrega para cima, uma de cada vez — são geradores Python!

        Project        ← pede linhas ao Filter e escolhe as colunas
           │
        Filter         ← pede linhas ao SeqScan e deixa passar só algumas
           │
        SeqScan        ← lê a tabela, linha por linha

Como tudo é preguiçoso, um ``LIMIT 1`` faz a varredura parar logo na
primeira linha que chegar lá em cima.

Cada operador também tem um ``scope``: a descrição das colunas que ele
entrega (veja ``expressions.Scope``).
"""

from itertools import islice
from operator import itemgetter

from . import nodes as n
from .datatypes import sql_literal
from .errors import TatuTypeError
from .expressions import AGGREGATES, Scope, Slot, compile_expr, truth


class Operator:
    scope: Scope
    children: tuple = ()

    def rows(self):
        raise NotImplementedError

    def describe(self) -> str:
        return type(self).__name__

    def explain(self) -> list[str]:
        """Desenha a árvore do plano (usado pelo EXPLAIN)."""
        lines = [self.describe()]
        for i, child in enumerate(self.children):
            last = i == len(self.children) - 1
            child_lines = child.explain()
            lines.append(("└── " if last else "├── ") + child_lines[0])
            lines.extend(("    " if last else "│   ") + line for line in child_lines[1:])
        return lines


def table_scope(table, ref_name: str) -> Scope:
    return Scope(Slot(ref_name, column.name) for column in table.schema.columns)


# ─────────────────────────── folhas: leitura ───────────────────────────

class SingleRow(Operator):
    """Uma única linha vazia — para SELECT sem FROM (``SELECT 1 + 1``)."""

    def __init__(self):
        self.scope = Scope([])

    def rows(self):
        yield ()


class SeqScan(Operator):
    """Varredura sequencial: lê todas as linhas da tabela."""

    def __init__(self, table, ref_name: str):
        self.table = table
        self.ref_name = ref_name
        self.scope = table_scope(table, ref_name)

    def rows(self):
        for _, row in self.table.scan():
            yield tuple(row)

    def describe(self):
        alias = f" AS {self.ref_name}" if self.ref_name != self.table.name else ""
        return f"SeqScan({self.table.name}{alias})"


class IndexScan(Operator):
    """Busca por índice: vai direto às linhas onde ``coluna = valor``."""

    def __init__(self, table, ref_name: str, index, value):
        self.table = table
        self.ref_name = ref_name
        self.index = index
        self.value = value
        self.scope = table_scope(table, ref_name)

    def rows(self):
        for rowid in sorted(self.index.lookup(self.value)):
            yield tuple(self.table.rows[rowid])

    def describe(self):
        alias = f" AS {self.ref_name}" if self.ref_name != self.table.name else ""
        return (f"IndexScan({self.table.name}{alias} usando {self.index.name}: "
                f"{self.index.column} = {sql_literal(self.value)})")


# ─────────────────────────── filtros e junções ───────────────────────────

class Filter(Operator):
    """Deixa passar só as linhas em que a condição é verdadeira (WHERE / HAVING)."""

    def __init__(self, child: Operator, condition: n.Node):
        self.children = (child,)
        self.condition = condition
        self.predicate = compile_expr(condition, child.scope)
        self.scope = child.scope

    def rows(self):
        predicate = self.predicate
        for row in self.children[0].rows():
            if truth(predicate(row)) is True:  # NULL ("não sei") não passa!
                yield row

    def describe(self):
        return f"Filter({self.condition})"


class NestedLoopJoin(Operator):
    """Junção por laços aninhados: cada linha da esquerda × todas da direita.

    É o jeito mais simples de fazer JOIN: dois ``for`` encaixados.
    No LEFT JOIN, uma linha da esquerda sem par sai com NULLs à direita.
    """

    def __init__(self, left: Operator, right: Operator, kind: str, condition: n.Node | None):
        self.children = (left, right)
        self.kind = kind
        self.condition = condition
        self.scope = left.scope + right.scope
        self.predicate = compile_expr(condition, self.scope) if condition is not None else None

    def rows(self):
        left, right = self.children
        right_rows = list(right.rows())  # lemos o lado direito uma vez só
        empty_right = (None,) * len(right.scope)
        for left_row in left.rows():
            matched = False
            for right_row in right_rows:
                row = left_row + right_row
                if self.predicate is None or truth(self.predicate(row)) is True:
                    matched = True
                    yield row
            if self.kind == "LEFT" and not matched:
                yield left_row + empty_right

    def describe(self):
        on = f" ON {self.condition}" if self.condition is not None else ""
        return f"NestedLoopJoin({self.kind}{on})"


# ─────────────────────────── agrupamento ───────────────────────────

class HashAggregate(Operator):
    """Agrupa linhas (GROUP BY) num dicionário e calcula as agregações.

    Entra:  linhas da tabela                 Sai:  uma linha por grupo
            ('Bolinha', 'tatu-bola')               ('tatu-bola', 2)
            ('Fuleco',  'tatu-bola')    ──▶        ('tatu-peba', 1)
            ('Peba',    'tatu-peba')
    """

    def __init__(self, child: Operator, group_by: list[n.Node], calls: list[n.Call]):
        self.children = (child,)
        self.group_by = group_by
        self.calls = calls
        source = child.scope
        self.group_fns = [compile_expr(g, source) for g in group_by]
        self.arg_fns = [None if c.star else compile_expr(c.args[0], source) for c in calls]

        # A saída tem: [chaves do grupo..., resultados das agregações...]
        slots = []
        for g in group_by:
            if isinstance(g, n.Column):  # mantém o nome para "SELECT nome ... GROUP BY nome"
                origin = source.slots[source.resolve(g)]
                slots.append(Slot(origin.table, origin.name, g))
            else:
                slots.append(Slot(None, None, g))
        slots.extend(Slot(None, None, call) for call in calls)
        self.scope = Scope(slots, aggregated=True)

    def rows(self):
        groups: dict[tuple, list[list]] = {}
        for row in self.children[0].rows():
            key = tuple(f(row) for f in self.group_fns)
            buckets = groups.get(key)
            if buckets is None:
                buckets = groups[key] = [[] for _ in self.calls]
            for bucket, arg in zip(buckets, self.arg_fns):
                if arg is None:
                    bucket.append(1)  # COUNT(*) conta a linha inteira
                else:
                    value = arg(row)
                    if value is not None:  # agregações ignoram NULL
                        bucket.append(value)

        if not groups and not self.group_fns:
            # SELECT COUNT(*) FROM tabela_vazia → uma linha com 0
            groups[()] = [[] for _ in self.calls]

        for key, buckets in groups.items():
            results = []
            for call, values in zip(self.calls, buckets):
                if call.distinct:
                    values = list(dict.fromkeys(values))
                results.append(AGGREGATES[call.name](values))
            yield key + tuple(results)

    def describe(self):
        parts = []
        if self.group_by:
            parts.append("por " + ", ".join(map(str, self.group_by)))
        if self.calls:
            parts.append("calcula " + ", ".join(map(str, self.calls)))
        return f"HashAggregate({'; '.join(parts)})"


# ─────────────────────────── acabamento ───────────────────────────

def _sort_key(value):
    # NULL vem antes de tudo; a tupla evita comparar None com números
    return (value is not None, value)


class Sort(Operator):
    """Ordena (ORDER BY). Precisa ver todas as linhas antes de entregar a primeira."""

    def __init__(self, child: Operator, items: list[n.OrderItem]):
        self.children = (child,)
        self.items = items
        self.keys = [(compile_expr(item.expr, child.scope), item.desc) for item in items]
        self.scope = child.scope

    def rows(self):
        rows = list(self.children[0].rows())
        # O sort do Python é estável: ordenando da última chave para a
        # primeira, o resultado fica ordenado por todas elas.
        for key_fn, desc in reversed(self.keys):
            try:
                rows.sort(key=lambda row: _sort_key(key_fn(row)), reverse=desc)
            except TypeError:
                raise TatuTypeError("ORDER BY encontrou tipos misturados na mesma coluna") from None
        yield from rows

    def describe(self):
        return f"Sort({', '.join(map(str, self.items))})"


class Project(Operator):
    """Projeção: calcula as colunas do SELECT."""

    def __init__(self, child: Operator, items: list[n.SelectItem]):
        self.children = (child,)
        names, self.fns = [], []
        for item in items:
            if isinstance(item.expr, n.Star):
                for position in child.scope.star(item.expr.table):
                    names.append(child.scope.slots[position].name)
                    self.fns.append(itemgetter(position))
            else:
                names.append(item.alias or output_name(item.expr))
                self.fns.append(compile_expr(item.expr, child.scope))
        self.names = names
        self.scope = Scope(Slot(None, name) for name in names)

    def rows(self):
        fns = self.fns
        for row in self.children[0].rows():
            yield tuple(f(row) for f in fns)

    def describe(self):
        return f"Project({', '.join(self.names)})"


def output_name(expr: n.Node) -> str:
    """Nome da coluna no resultado: ``t.nome`` vira ``nome``; o resto vira texto."""
    return expr.name if isinstance(expr, n.Column) else str(expr)


class Distinct(Operator):
    """Remove linhas repetidas (mantendo a primeira — e a ordem)."""

    def __init__(self, child: Operator):
        self.children = (child,)
        self.scope = child.scope

    def rows(self):
        seen = set()
        for row in self.children[0].rows():
            if row not in seen:
                seen.add(row)
                yield row


class Limit(Operator):
    """Entrega no máximo ``limit`` linhas, pulando as ``offset`` primeiras."""

    def __init__(self, child: Operator, limit: int | None, offset: int):
        self.children = (child,)
        self.limit = limit
        self.offset = offset
        self.scope = child.scope

    def rows(self):
        stop = None if self.limit is None else self.offset + self.limit
        yield from islice(self.children[0].rows(), self.offset, stop)

    def describe(self):
        limit = "sem limite" if self.limit is None else str(self.limit)
        return f"Limit({limit}{f', pula {self.offset}' if self.offset else ''})"
