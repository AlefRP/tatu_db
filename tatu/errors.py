"""
🚨 Exceções do Tatu DB.

Todas herdam de ``TatuError``: quem usa o banco pode capturar qualquer
erro do Tatu com um único ``except tatu.TatuError``.
"""


class TatuError(Exception):
    """Erro base do Tatu DB."""


class TatuSyntaxError(TatuError):
    """O SQL não pôde ser lido (erro do tokenizer ou do parser).

    Guarda o texto e a posição do problema para desenhar uma setinha
    apontando onde o tatu tropeçou::

        Esperava ')', mas encontrei 'FROM' (linha 1, coluna 18)
          SELECT COUNT(* FROM tatus
                         ^
    """

    def __init__(self, message: str, sql: str | None = None, pos: int | None = None):
        self.message = message
        self.sql = sql
        self.pos = pos
        super().__init__(self._render())

    def _render(self) -> str:
        if self.sql is None or self.pos is None:
            return self.message
        line_start = self.sql.rfind("\n", 0, self.pos) + 1
        line_end = self.sql.find("\n", self.pos)
        if line_end == -1:
            line_end = len(self.sql)
        line_no = self.sql.count("\n", 0, self.pos) + 1
        col = self.pos - line_start
        line = self.sql[line_start:line_end].replace("\t", " ")
        return f"{self.message} (linha {line_no}, coluna {col + 1})\n  {line}\n  {' ' * col}^"


class CatalogError(TatuError):
    """Tabela, coluna, índice ou função inexistente (ou duplicado)."""


class ConstraintError(TatuError):
    """Violação de restrição: PRIMARY KEY, NOT NULL, UNIQUE ou REFERENCES."""


class TatuTypeError(TatuError):
    """Valor incompatível com o tipo da coluna ou da operação."""


class ExecutionError(TatuError):
    """Erro durante a execução (ex.: divisão por zero)."""


class TransactionError(TatuError):
    """Uso incorreto de BEGIN / COMMIT / ROLLBACK."""
