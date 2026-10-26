"""Sessão do Toca, separada dos widgets para ser fácil de estudar e testar.

O motor continua sendo ``Database``. Esta camada cuida dos arquivos, do
histórico e da troca segura de banco; não reimplementa o SQL.
"""

import copy
import csv
import json
import os
import tempfile
import threading
import time
import weakref
from dataclasses import dataclass, field
from pathlib import Path

from . import nodes
from .database import Database
from .datatypes import sql_literal
from .demo import DEMO_SQL
from .errors import TatuError, TransactionError
from .parser import parse
from .result import Result
from .schema import Column
from .storage import FILE_FORMAT_VERSION

MAX_SQL_BYTES = 8 * 1024 * 1024


@dataclass
class RunReport:
    results: list[Result] = field(default_factory=list)
    elapsed_ms: float = 0.0
    error: TatuError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def last(self) -> Result | None:
        return self.results[-1] if self.results else None


@dataclass
class HistoryEntry:
    sql: str
    elapsed_ms: float
    rows: int
    ok: bool


@dataclass
class IndexInfo:
    name: str
    column: str
    unique: bool
    automatic: bool


@dataclass
class TableInfo:
    name: str
    columns: list[Column]
    indexes: list[IndexInfo]
    row_count: int
    sql: str


def quote_identifier(name: str) -> str:
    """Nomes do catálogo são identificadores, nunca trechos de SQL."""
    return '"' + name.replace('"', '""') + '"'


def _path(path: str | os.PathLike) -> str:
    if not str(path).strip():
        raise TatuError("Escolha um caminho de arquivo.")
    return str(Path(path).expanduser().resolve())


def _read_database(path: str) -> Database:
    """Erros de estrutura do arquivo devem aparecer como mensagens no cliente."""
    try:
        if not Path(path).is_file():
            raise TatuError("O banco não existe. Use Novo banco para criar um arquivo.")
        with open(path, encoding="utf-8") as source:
            data = json.load(source)
        if not isinstance(data, dict) or data.get("formato") != "tatu-db":
            raise TatuError("O arquivo não é um banco do Tatu DB.")
        if data.get("versao") != FILE_FORMAT_VERSION:
            raise TatuError("Versão de arquivo não suportada pelo Tatu DB instalado.")
        if not isinstance(data.get("tabelas"), list):
            raise TatuError("O arquivo do banco está incompleto: faltam as tabelas.")
        return Database(path)
    except TatuError:
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        raise TatuError(f"Não consegui abrir o banco: {error}") from None


def read_sql(path: str | os.PathLike) -> str:
    try:
        with open(path, "rb") as source:
            data = source.read(MAX_SQL_BYTES + 1)
        if len(data) > MAX_SQL_BYTES:
            raise TatuError("O arquivo SQL ultrapassa o limite de 8 MiB.")
        return data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, UnicodeError) as error:
        raise TatuError(f"Não consegui ler a consulta em UTF-8: {error}") from None


def _atomic_text(path: str | os.PathLike, write, encoding: str = "utf-8") -> None:
    destination = _path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding=encoding, newline="", delete=False,
            dir=Path(destination).parent, prefix=".toca-", suffix=".tmp",
        ) as target:
            temporary = target.name
            write(target)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
    except (OSError, UnicodeError, ValueError) as error:
        raise TatuError(f"Não consegui gravar o arquivo: {error}") from None
    finally:
        if temporary and os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                # Uma falha ao limpar o temporário não deve esconder o erro
                # que impediu a gravação; o arquivo anterior foi preservado.
                pass


def write_sql(path: str | os.PathLike, text: str) -> None:
    _atomic_text(path, lambda target: target.write(text))


def export_csv(path: str | os.PathLike, result: Result) -> None:
    """O CSV leva os valores completos; NULL vira campo vazio, como no csv do Python."""
    if not result.columns:
        raise TatuError("Execute uma consulta com colunas antes de exportar CSV.")

    def write(target):
        writer = csv.writer(target)
        writer.writerow(result.columns)
        writer.writerows(result.rows)

    _atomic_text(path, write, encoding="utf-8-sig")


class Session:
    # Evita que duas janelas deste processo substituam mudanças uma da outra.
    # O motor educacional não coordena escritores de processos diferentes.
    _paths: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
    _paths_lock = threading.RLock()

    def __init__(self, path: str | os.PathLike | None = None, demo: bool = True):
        self._lock = threading.RLock()
        self.db = Database()
        self.history: list[HistoryEntry] = []
        self.dirty = False
        self._transaction_dirty = False
        if path is not None:
            self.open(path)
        elif demo:
            self.load_demo()

    @property
    def path(self) -> str | None:
        return self.db.path

    @property
    def is_memory(self) -> bool:
        return self.path is None

    @property
    def in_transaction(self) -> bool:
        return self.db.in_transaction

    def _ready(self) -> None:
        if self.db.closed:
            raise TatuError("A sessão do Toca está fechada.")

    def _can_replace(self) -> None:
        self._ready()
        if self.in_transaction:
            raise TransactionError("Confirme ou desfaça a transação antes de trocar de banco.")

    def _claim(self, path: str) -> bool:
        key = os.path.normcase(path)
        with self._paths_lock:
            owner = self._paths.get(key)
            if owner is not None and owner is not self:
                raise TatuError("Esse banco já está aberto em outra janela do Toca. Feche-a primeiro.")
            if owner is self:
                return False
            self._paths[key] = self
            return True

    def _release(self, path: str | None) -> None:
        if path is not None:
            key = os.path.normcase(path)
            with self._paths_lock:
                if self._paths.get(key) is self:
                    self._paths.pop(key, None)

    def _replace(self, candidate: Database) -> None:
        previous = self.db
        self.db = candidate
        if previous.path != candidate.path:
            self._release(previous.path)
        previous.close()
        self.history.clear()
        self.dirty = False
        self._transaction_dirty = False

    def open(self, path: str | os.PathLike) -> None:
        with self._lock:
            self._can_replace()
            destination = _path(path)
            claimed = self._claim(destination)
            try:
                candidate = _read_database(destination)
            except Exception:
                if claimed:
                    self._release(destination)
                raise
            self._replace(candidate)

    def new(self, path: str | os.PathLike | None = None) -> None:
        with self._lock:
            self._can_replace()
            if path is None:
                self._replace(Database())
                return
            destination = _path(path)
            claimed = self._claim(destination)
            candidate = Database()
            try:
                if os.path.exists(destination):
                    raise TatuError("Esse arquivo já existe. Use Abrir banco ou escolha outro nome.")
                candidate.path = candidate.storage.path = destination
                candidate.storage.save()
            except OSError as error:
                if claimed:
                    self._release(destination)
                candidate.close()
                raise TatuError(f"Não consegui criar o banco: {error}") from None
            except Exception:
                if claimed:
                    self._release(destination)
                candidate.close()
                raise
            self._replace(candidate)

    def load_demo(self) -> None:
        with self._lock:
            self._can_replace()
            candidate = Database()
            try:
                candidate.executescript(DEMO_SQL)
            except Exception:
                candidate.close()
                raise
            self._replace(candidate)

    def save_as(self, path: str | os.PathLike, overwrite: bool = False) -> None:
        with self._lock:
            self._can_replace()
            destination = _path(path)
            claimed = self._claim(destination)
            try:
                if destination != self.path and os.path.exists(destination):
                    if not overwrite:
                        raise TatuError("O arquivo já existe. Confirme a substituição ou escolha outro nome.")
                    existing = _read_database(destination)
                    existing.close()
                # Só o caminho da cópia muda. Se a escrita falhar, a conexão
                # e o destino anterior continuam exatamente como estavam.
                snapshot = copy.copy(self.db.storage)
                snapshot.path = destination
                snapshot.save()
            except OSError as error:
                if claimed:
                    self._release(destination)
                raise TatuError(f"Não consegui salvar o banco: {error}") from None
            except Exception:
                if claimed:
                    self._release(destination)
                raise
            previous = self.path
            self.db.path = self.db.storage.path = destination
            if previous != destination:
                self._release(previous)
            self.dirty = False

    def run(self, sql: str) -> RunReport:
        with self._lock:
            report = RunReport()
            start = time.perf_counter()
            try:
                self._ready()
                statements = parse(sql)
                for statement, result in zip(statements, self.db.iterscript(sql)):
                    report.results.append(result)
                    if isinstance(statement, nodes.Begin):
                        self._transaction_dirty = self.dirty
                    elif isinstance(statement, nodes.Rollback):
                        self.dirty = self._transaction_dirty
                    elif self.is_memory and not isinstance(
                        statement, (nodes.Select, nodes.Explain, nodes.Commit),
                    ):
                        self.dirty = True
            except TatuError as error:
                report.error = error
            except (OSError, ValueError, OverflowError) as error:
                report.error = TatuError(f"Não foi possível executar a consulta: {error}")
            report.elapsed_ms = (time.perf_counter() - start) * 1000
            if sql.strip():
                self.history.insert(0, HistoryEntry(
                    sql, report.elapsed_ms, sum(len(result.rows) for result in report.results), report.ok,
                ))
                del self.history[100:]
            return report

    def begin(self) -> RunReport:
        return self.run("BEGIN;")

    def commit(self) -> RunReport:
        return self.run("COMMIT;")

    def rollback(self) -> RunReport:
        return self.run("ROLLBACK;")

    def tables(self) -> list[str]:
        with self._lock:
            self._ready()
            return self.db.tables()

    def table_info(self, name: str) -> TableInfo:
        with self._lock:
            self._ready()
            table = self.db.storage.get_table(name)
            columns = [copy.copy(column) for column in table.schema.columns]
            indexes = [IndexInfo(index.name, index.column, index.unique, index.automatic)
                       for index in table.indexes.values()]
            lines = []
            for column in columns:
                parts = [quote_identifier(column.name), column.type]
                if column.primary_key:
                    parts.append("PRIMARY KEY")
                elif column.not_null:
                    parts.append("NOT NULL")
                if column.unique:
                    parts.append("UNIQUE")
                if column.default is not None:
                    parts.append(f"DEFAULT {sql_literal(column.default)}")
                if column.references:
                    parent, key = column.references
                    parts.append(f"REFERENCES {quote_identifier(parent)}({quote_identifier(key)})")
                lines.append("  " + " ".join(parts))
            sql = f"CREATE TABLE {quote_identifier(name)} (\n" + ",\n".join(lines) + "\n);"
            for index in indexes:
                if not index.automatic:
                    unique = "UNIQUE " if index.unique else ""
                    sql += (f"\nCREATE {unique}INDEX {quote_identifier(index.name)} ON "
                            f"{quote_identifier(name)} ({quote_identifier(index.column)});")
            return TableInfo(name, columns, indexes, len(table.rows), sql)

    def table_query(self, name: str, limit: int = 200) -> str:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise TatuError("O limite da consulta precisa ser um inteiro positivo.")
        self.table_info(name)
        return f"SELECT * FROM {quote_identifier(name)} LIMIT {limit};"

    def close(self) -> None:
        with self._lock:
            self._release(self.path)
            self.db.close()
