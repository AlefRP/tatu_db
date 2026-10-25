"""
🐾 Tatu DB — um banco de dados relacional minúsculo, feito do zero em Python, para aprender.

    >>> import tatu
    >>> db = tatu.connect()
    >>> db.execute("CREATE TABLE tatus (id INTEGER PRIMARY KEY, apelido TEXT)").message
    "Tabela 'tatus' criada"
    >>> db.execute("INSERT INTO tatus (apelido) VALUES ('Bolinha'), ('Fuleco')").rowcount
    2
    >>> db.execute("SELECT apelido FROM tatus WHERE id = 2").scalar()
    'Fuleco'

A jornada de um comando:

    texto SQL ─▶ tokenizer ─▶ parser ─▶ planner ─▶ operators ─▶ storage
                 (tokens)     (AST)     (plano)    (linhas)     (toca)
"""

__version__ = "0.1.0"

from .database import Database, connect
from .errors import (
    CatalogError,
    ConstraintError,
    ExecutionError,
    TatuError,
    TatuSyntaxError,
    TatuTypeError,
    TransactionError,
)
from .result import Result

__all__ = [
    "connect", "Database", "Result",
    "TatuError", "TatuSyntaxError", "CatalogError", "ConstraintError",
    "TatuTypeError", "ExecutionError", "TransactionError",
]
