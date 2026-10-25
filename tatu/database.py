"""
🐾 Conexão: a porta de entrada do Tatu DB.

    import tatu

    db = tatu.connect("zoo.tatu")      # ou tatu.connect() para um banco em memória
    db.execute("CREATE TABLE tatus (id INTEGER PRIMARY KEY, apelido TEXT)")
    db.execute("INSERT INTO tatus (apelido) VALUES (?)", ("Bolinha",))
    for linha in db.execute("SELECT * FROM tatus"):
        print(linha)

Aqui também mora o controle de transações. Por padrão cada comando é
gravado sozinho (*autocommit*). Entre ``BEGIN`` e ``COMMIT``, as mudanças
ficam só na memória até o ``COMMIT`` — ou somem no ``ROLLBACK``.
"""

from . import nodes as n
from .errors import TatuError, TransactionError
from .executor import Executor
from .expressions import bind_params
from .parser import parse
from .result import Result
from .storage import Storage


def connect(path: str | None = None) -> "Database":
    """Abre (ou cria) um banco. Sem caminho (ou ``":memory:"``), fica só na memória."""
    return Database(path)


class Database:
    def __init__(self, path: str | None = None):
        self.path = None if path in (None, ":memory:") else str(path)
        self.storage = Storage(self.path)
        self.executor = Executor(self.storage)
        self.in_transaction = False
        self.closed = False

    # ─────────────────────────── API pública ───────────────────────────

    def execute(self, sql: str, params=()) -> Result:
        """Executa **um** comando SQL. Use ``?`` para os valores vindos de fora."""
        statements = parse(sql)
        if len(statements) != 1:
            raise TatuError("execute() roda um comando por vez — para vários, use executescript()")
        stmt = statements[0]
        if params or any(isinstance(node, n.Param) for node in n.walk(stmt)):
            stmt = bind_params(stmt, params)
        return self._run(stmt)

    def executescript(self, sql: str) -> list[Result]:
        """Executa vários comandos separados por ``;``.

        Tudo é analisado antes: se houver erro de sintaxe, nada roda.
        """
        return list(self.iterscript(sql))

    def iterscript(self, sql: str):
        """Como ``executescript``, mas entrega cada resultado assim que fica pronto."""
        for stmt in parse(sql):
            yield self._run(stmt)

    def tables(self) -> list[str]:
        return sorted(self.storage.tables)

    def schema(self, table: str) -> str:
        return self.storage.get_table(table).schema.to_sql()

    def close(self) -> None:
        """Fecha o banco. Uma transação aberta é desfeita (como no SQLite)."""
        if self.in_transaction:
            self.storage.journal.rollback_to(0)
            self.in_transaction = False
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    # ─────────────────────────── por dentro ───────────────────────────

    def _run(self, stmt: n.Node) -> Result:
        if self.closed:
            raise TatuError("O banco está fechado")

        match stmt:
            case n.Begin():
                return self._begin()
            case n.Commit():
                return self._commit_transaction()
            case n.Rollback():
                return self._rollback_transaction()

        journal = self.storage.journal
        mark = journal.mark()
        try:
            result = self.executor.execute(stmt)
        except Exception:
            # Atomicidade por comando: se o 3º de 5 INSERTs falhar,
            # desfazemos os 2 primeiros. Ou vai tudo, ou nada.
            journal.rollback_to(mark)
            raise

        if not self.in_transaction and len(journal):  # autocommit
            self._persist()
        return result

    def _persist(self) -> None:
        """Grava no disco e esquece o diário. Se a gravação falhar, desfaz tudo."""
        try:
            self.storage.save()
        except OSError as error:
            self.storage.journal.rollback_to(0)
            self.in_transaction = False
            raise TatuError(f"Não consegui gravar o banco em disco: {error}") from None
        self.storage.journal.clear()

    def _begin(self) -> Result:
        if self.in_transaction:
            raise TransactionError("Já existe uma transação em andamento (faltou um COMMIT ou ROLLBACK?)")
        self.in_transaction = True
        return Result(message="Transação iniciada — as mudanças ficam na toca até o COMMIT")

    def _commit_transaction(self) -> Result:
        if not self.in_transaction:
            raise TransactionError("Não há transação para confirmar (use BEGIN antes)")
        changes = len(self.storage.journal)
        self._persist()
        self.in_transaction = False
        return Result(message=f"Transação confirmada ✔ ({changes} mudança(s) gravada(s))")

    def _rollback_transaction(self) -> Result:
        if not self.in_transaction:
            raise TransactionError("Não há transação para desfazer (use BEGIN antes)")
        changes = len(self.storage.journal)
        self.storage.journal.rollback_to(0)
        self.in_transaction = False
        return Result(message=f"Transação desfeita ↩ ({changes} mudança(s) descartada(s))")
