"""
🧮 Avaliação de expressões.

Antes de executar, cada expressão da AST é *compilada* numa função
Python ``f(linha) -> valor``. A compilação resolve os nomes das colunas
para posições na linha: durante a execução, ``idade`` já virou
``linha[2]`` e ninguém precisa procurar nada.

    compile_expr(Binary('>', Column('idade'), Literal(3)), escopo)
        ≈  lambda linha: maior_que(linha[2], 3)

O NULL segue a lógica de três valores do SQL: quase toda conta com NULL
dá NULL, e ``NULL = NULL`` não é verdadeiro — é NULL ("não sei").
"""

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from operator import itemgetter

from . import nodes as n
from .datatypes import family, sql_literal, type_of
from .errors import CatalogError, ExecutionError, TatuTypeError

# ═════════════════════════════ Escopo ═════════════════════════════

@dataclass(frozen=True)
class Slot:
    """Uma posição da linha que circula entre os operadores.

    Colunas de tabela têm ``table`` e ``name``. Valores calculados por
    um GROUP BY ou por uma agregação guardam a expressão em ``expr``.
    """
    table: str | None
    name: str | None
    expr: n.Node | None = None


class Scope:
    """Descreve o "formato" das linhas: o que há em cada posição."""

    def __init__(self, slots, aggregated: bool = False):
        self.slots = list(slots)
        self.aggregated = aggregated  # True depois de um GROUP BY

    def __add__(self, other: "Scope") -> "Scope":
        return Scope(self.slots + other.slots)

    def __len__(self) -> int:
        return len(self.slots)

    def find_expr(self, expr: n.Node) -> int | None:
        """Posição de um valor já calculado (ex.: o ``COUNT(*)`` do GROUP BY)."""
        for i, slot in enumerate(self.slots):
            if slot.expr is not None and slot.expr == expr:
                return i
        return None

    def resolve(self, column: n.Column) -> int:
        """Transforma ``tabela.coluna`` (ou só ``coluna``) numa posição."""
        if column.table and not any(s.table == column.table for s in self.slots):
            if self.aggregated:
                raise CatalogError(
                    f"A coluna '{column}' precisa estar no GROUP BY ou dentro de uma agregação")
            raise CatalogError(f"Tabela ou apelido desconhecido: '{column.table}'")
        matches = [i for i, s in enumerate(self.slots)
                   if s.name == column.name and column.table in (None, s.table)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise CatalogError(
                f"A coluna '{column.name}' é ambígua — diga de qual tabela: "
                f"{', '.join(f'{self.slots[i].table}.{column.name}' for i in matches)}")
        if self.aggregated:
            raise CatalogError(
                f"A coluna '{column}' precisa estar no GROUP BY ou dentro de uma agregação")
        raise CatalogError(f"Coluna desconhecida: '{column}'")

    def star(self, table: str | None = None) -> list[int]:
        """Posições que um ``*`` (ou ``tabela.*``) expande."""
        positions = [i for i, s in enumerate(self.slots)
                     if s.name is not None and table in (None, s.table)]
        if table and not positions:
            raise CatalogError(f"Tabela ou apelido desconhecido: '{table}'")
        return positions


# ═══════════════════ Lógica de três valores ═══════════════════

def truth(value):
    """Converte para TRUE / FALSE / NULL (None)."""
    return None if value is None else bool(value)


def logic_and(a, b):
    a, b = truth(a), truth(b)
    if a is False or b is False:
        return False  # FALSE AND "não sei" = FALSE
    if a is None or b is None:
        return None
    return True


def logic_or(a, b):
    a, b = truth(a), truth(b)
    if a is True or b is True:
        return True   # TRUE OR "não sei" = TRUE
    if a is None or b is None:
        return None
    return False


def logic_not(a):
    a = truth(a)
    return None if a is None else not a


# ═══════════════════════ Operadores ═══════════════════════

def _require_numbers(op, *values):
    for v in values:
        if family(v) != "número":
            raise TatuTypeError(
                f"'{op}' espera números, mas recebeu {type_of(v)} ({sql_literal(v)})")


def _arithmetic(op, fn):
    def apply(a, b):
        if a is None or b is None:
            return None
        _require_numbers(op, a, b)
        return fn(a, b)
    return apply


def _trunc_div(a, b):
    """Divisão inteira que trunca em direção ao zero, como no SQL (-7 / 2 = -3)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def _divide(a, b):
    if b == 0:
        raise ExecutionError("Divisão por zero")
    if isinstance(a, int) and isinstance(b, int):
        return _trunc_div(a, b)
    return a / b


def _modulo(a, b):
    if b == 0:
        raise ExecutionError("Divisão por zero (no %)")
    if isinstance(a, int) and isinstance(b, int):
        return a - b * _trunc_div(a, b)
    return math.fmod(a, b)


def _comparison(op, fn):
    def apply(a, b):
        if a is None or b is None:
            return None  # comparar com NULL dá "não sei"
        if family(a) != family(b):
            raise TatuTypeError(
                f"Não dá para comparar {type_of(a)} com {type_of(b)} "
                f"({sql_literal(a)} {op} {sql_literal(b)})")
        return fn(a, b)
    return apply


def _as_text(value) -> str:
    return value if isinstance(value, str) else sql_literal(value)


def _concat(a, b):
    if a is None or b is None:
        return None
    return _as_text(a) + _as_text(b)


BINARY_OPS = {
    "+": _arithmetic("+", lambda a, b: a + b),
    "-": _arithmetic("-", lambda a, b: a - b),
    "*": _arithmetic("*", lambda a, b: a * b),
    "/": _arithmetic("/", _divide),
    "%": _arithmetic("%", _modulo),
    "=": _comparison("=", lambda a, b: a == b),
    "!=": _comparison("!=", lambda a, b: a != b),
    "<": _comparison("<", lambda a, b: a < b),
    "<=": _comparison("<=", lambda a, b: a <= b),
    ">": _comparison(">", lambda a, b: a > b),
    ">=": _comparison(">=", lambda a, b: a >= b),
    "||": _concat,
    "AND": logic_and,
    "OR": logic_or,
}


def _negate(value):
    if value is None:
        return None
    _require_numbers("-", value)
    return -value


@lru_cache(maxsize=256)
def _like_regex(pattern: str):
    # % = qualquer sequência, _ = um caractere; o resto é literal
    parts = (".*" if ch == "%" else "." if ch == "_" else re.escape(ch) for ch in pattern)
    return re.compile("".join(parts), re.DOTALL)


def like(value, pattern):
    if value is None or pattern is None:
        return None
    if not isinstance(value, str) or not isinstance(pattern, str):
        raise TatuTypeError("LIKE só funciona com TEXT")
    return _like_regex(pattern).fullmatch(value) is not None


# ═══════════════════════ Funções ═══════════════════════

def _null_in_null_out(fn):
    """A maioria das funções devolve NULL se receber NULL."""
    def wrapper(*args):
        return None if any(a is None for a in args) else fn(*args)
    return wrapper


def _text_fn(name, fn):
    def apply(value):
        if not isinstance(value, str):
            raise TatuTypeError(f"{name}() espera TEXT, mas recebeu {type_of(value)}")
        return fn(value)
    return _null_in_null_out(apply)


def _abs(value):
    _require_numbers("ABS", value)
    return abs(value)


def _round(value, digits=0):
    _require_numbers("ROUND", value, digits)
    return float(round(value, int(digits)))


# nome → (mínimo de argumentos, máximo de argumentos, função)
SCALAR_FUNCTIONS = {
    "UPPER": (1, 1, _text_fn("UPPER", str.upper)),
    "LOWER": (1, 1, _text_fn("LOWER", str.lower)),
    "LENGTH": (1, 1, _text_fn("LENGTH", len)),
    "TRIM": (1, 1, _text_fn("TRIM", str.strip)),
    "ABS": (1, 1, _null_in_null_out(_abs)),
    "ROUND": (1, 2, _null_in_null_out(_round)),
    "COALESCE": (1, None, lambda *args: next((a for a in args if a is not None), None)),
    "TYPEOF": (1, 1, type_of),
}


def _require_aggregate_numbers(name, values):
    for v in values:
        if family(v) != "número":
            raise TatuTypeError(f"{name}() espera números, mas recebeu {type_of(v)} ({sql_literal(v)})")


def _sum(values):
    _require_aggregate_numbers("SUM", values)
    return sum(values) if values else None


def _avg(values):
    _require_aggregate_numbers("AVG", values)
    return sum(values) / len(values) if values else None


# Agregações recebem a lista de valores (sem NULLs) de um grupo inteiro.
AGGREGATES = {
    "COUNT": len,
    "SUM": _sum,
    "AVG": _avg,
    "MIN": lambda values: min(values) if values else None,
    "MAX": lambda values: max(values) if values else None,
}


def is_aggregate(node) -> bool:
    return isinstance(node, n.Call) and node.name in AGGREGATES


# ═══════════════════════ Compilação ═══════════════════════

def compile_expr(expr: n.Node, scope: Scope):
    """Transforma uma expressão da AST numa função ``f(linha) -> valor``."""

    # Valor já calculado por um operador abaixo (GROUP BY / agregação)?
    position = scope.find_expr(expr)
    if position is not None:
        return itemgetter(position)

    match expr:
        case n.Literal(value=value):
            return lambda row: value

        case n.Column():
            return itemgetter(scope.resolve(expr))

        case n.Unary(op="NOT", operand=operand):
            f = compile_expr(operand, scope)
            return lambda row: logic_not(f(row))

        case n.Unary(op="-", operand=operand):
            f = compile_expr(operand, scope)
            return lambda row: _negate(f(row))

        case n.Binary(op=op, left=left, right=right):
            fn = BINARY_OPS[op]
            fl, fr = compile_expr(left, scope), compile_expr(right, scope)
            return lambda row: fn(fl(row), fr(row))

        case n.IsNull(operand=operand, negated=negated):
            f = compile_expr(operand, scope)
            return lambda row: (f(row) is None) != negated

        case n.InList(operand=operand, items=items, negated=negated):
            f = compile_expr(operand, scope)
            item_fns = [compile_expr(item, scope) for item in items]
            equals = BINARY_OPS["="]

            def in_list(row):
                value = f(row)
                if value is None:
                    return None
                results = [equals(value, g(row)) for g in item_fns]
                if True in results:
                    found = True
                elif None in results:
                    return None  # 5 IN (1, NULL): "não sei"
                else:
                    found = False
                return found != negated
            return in_list

        case n.Between(operand=operand, low=low, high=high, negated=negated):
            f, f_low, f_high = (compile_expr(e, scope) for e in (operand, low, high))
            ge, le = BINARY_OPS[">="], BINARY_OPS["<="]

            def between(row):
                value = f(row)
                result = logic_and(ge(value, f_low(row)), le(value, f_high(row)))
                return logic_not(result) if negated else result
            return between

        case n.Like(operand=operand, pattern=pattern, negated=negated):
            f, fp = compile_expr(operand, scope), compile_expr(pattern, scope)

            def like_fn(row):
                result = like(f(row), fp(row))
                return logic_not(result) if negated else result
            return like_fn

        case n.Call(name=name) if name in AGGREGATES:
            raise ExecutionError(
                f"{expr} não pode ser usado aqui — agregações só valem no SELECT, "
                f"no HAVING e no ORDER BY (para filtrar grupos, use HAVING)")

        case n.Call(name=name, args=args):
            if name not in SCALAR_FUNCTIONS:
                raise CatalogError(f"Função desconhecida: {name}()")
            low, high, fn = SCALAR_FUNCTIONS[name]
            if len(args) < low or (high is not None and len(args) > high):
                expected = str(low) if low == high else f"de {low} a {high or 'vários'}"
                raise ExecutionError(f"{name}() recebe {expected} argumento(s), mas recebeu {len(args)}")
            arg_fns = [compile_expr(a, scope) for a in args]
            return lambda row: fn(*(g(row) for g in arg_fns))

        case n.Star():
            raise ExecutionError("'*' só pode ser usado direto no SELECT ou em COUNT(*)")

        case n.Param():
            raise ExecutionError("Há um '?' sem valor — passe os parâmetros no execute()")

    raise ExecutionError(f"Expressão não suportada: {expr}")


def evaluate_constant(expr: n.Node):
    """Avalia uma expressão que não depende de nenhuma linha (ex.: VALUES)."""
    return compile_expr(expr, Scope([]))(())


def bind_params(stmt: n.Node, params) -> n.Node:
    """Troca cada ``?`` pelo valor correspondente (protege contra SQL injection!)."""
    params = tuple(params)
    count = sum(isinstance(node, n.Param) for node in n.walk(stmt))
    if count != len(params):
        raise ExecutionError(
            f"O comando tem {count} parâmetro(s) '?', mas recebeu {len(params)} valor(es)")
    for value in params:
        type_of(value)  # rejeita tipos que o Tatu não conhece

    def substitute(node):
        return n.Literal(params[node.index]) if isinstance(node, n.Param) else node
    return n.transform(stmt, substitute)
