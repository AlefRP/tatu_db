"""
🧱 Tipos de dados.

O Tatu DB conhece quatro tipos — o suficiente para aprender:

    INTEGER   números inteiros       42
    REAL      números com vírgula    3.14
    TEXT      textos                 'tatu-bola'
    BOOLEAN   verdadeiro / falso     TRUE

``NULL`` (``None`` em Python) representa "valor ausente" e cabe em
qualquer tipo, a menos que a coluna seja ``NOT NULL``.
"""

from .errors import TatuTypeError

# Apelidos aceitos no CREATE TABLE → tipo de verdade
TYPE_ALIASES = {
    "INTEGER": "INTEGER", "INT": "INTEGER", "BIGINT": "INTEGER", "SMALLINT": "INTEGER",
    "REAL": "REAL", "FLOAT": "REAL", "DOUBLE": "REAL", "NUMERIC": "REAL", "DECIMAL": "REAL",
    "TEXT": "TEXT", "VARCHAR": "TEXT", "CHAR": "TEXT", "STRING": "TEXT",
    "BOOLEAN": "BOOLEAN", "BOOL": "BOOLEAN",
}

# Famílias de valores que podem ser comparados entre si
_FAMILY = {"INTEGER": "número", "REAL": "número", "TEXT": "texto", "BOOLEAN": "booleano"}


def normalize_type(name: str) -> str | None:
    """``'varchar'`` → ``'TEXT'``; devolve ``None`` se o tipo não existe."""
    return TYPE_ALIASES.get(name.upper())


def type_of(value) -> str:
    """Nome do tipo SQL de um valor Python."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):  # cuidado: em Python, bool é subclasse de int!
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    if isinstance(value, str):
        return "TEXT"
    raise TatuTypeError(f"Tipo Python não suportado pelo Tatu DB: {type(value).__name__}")


def family(value) -> str | None:
    """Família do valor: 'número', 'texto' ou 'booleano' (None para NULL)."""
    return None if value is None else _FAMILY[type_of(value)]


def type_family(type_name: str) -> str:
    return _FAMILY[type_name]


def coerce(value, type_name: str, column_name: str):
    """Converte ``value`` para o tipo da coluna, ou reclama.

    Só fazemos conversões sem perda: INTEGER → REAL (3 → 3.0) e
    REAL inteiro → INTEGER (3.0 → 3). Texto nunca vira número sozinho.
    """
    if value is None:
        return None
    actual = type_of(value)
    if actual == type_name:
        return value
    if type_name == "REAL" and actual == "INTEGER":
        return float(value)
    if type_name == "INTEGER" and actual == "REAL" and value.is_integer():
        return int(value)
    raise TatuTypeError(
        f"A coluna '{column_name}' é {type_name}, mas recebeu {actual} ({sql_literal(value)})"
    )


def sql_literal(value) -> str:
    """Escreve um valor Python como literal SQL: None → NULL, 'a' → 'a'."""
    if value is None:
        return "NULL"
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return repr(value)
