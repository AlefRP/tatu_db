"""
💾 Armazenamento: onde os dados moram — a toca do tatu.

Cada tabela guarda:

* um **heap** — dicionário ``rowid → linha`` (a linha é uma lista de valores);
* zero ou mais **índices hash** — dicionário ``valor → {rowids}``, que
  acha linhas sem varrer a tabela inteira.

Toda modificação passa por aqui e é anotada no **diário** (``Journal``),
que sabe desfazê-la. É assim que o ROLLBACK funciona.

No disco, o banco inteiro é um único arquivo JSON (``.tatu``) gravado de
forma *atômica*: escrevemos um arquivo temporário e depois o renomeamos
por cima do original. Se a luz acabar no meio, sobra o arquivo antigo
ou o novo — nunca um pedaço de cada.
"""

import json
import os

from .datatypes import sql_literal
from .errors import CatalogError, ConstraintError, TatuError
from .schema import TableSchema

FILE_FORMAT_VERSION = 1


class Journal:
    """📓 Diário de desfazer (*undo log*).

    Para cada mudança guardamos uma função que a desfaz. Desfazer uma
    transação é só chamar essas funções em ordem inversa — da mais nova
    para a mais antiga.
    """

    def __init__(self):
        self._undo = []

    def record(self, undo) -> None:
        self._undo.append(undo)

    def mark(self) -> int:
        """Um "marcador de página": até onde desfazer depois."""
        return len(self._undo)

    def rollback_to(self, mark: int = 0) -> None:
        while len(self._undo) > mark:
            self._undo.pop()()

    def clear(self) -> None:
        self._undo.clear()

    def __len__(self) -> int:
        return len(self._undo)


class Index:
    """🔎 Índice hash de uma coluna: ``valor → conjunto de rowids``.

    NULL nunca entra no índice: ``x = NULL`` nunca é verdadeiro, então
    ninguém procura por ele (e várias linhas podem ter NULL num UNIQUE).
    """

    def __init__(self, name: str, column: str, position: int,
                 unique: bool = False, automatic: bool = False):
        self.name = name
        self.column = column
        self.position = position    # posição da coluna dentro da linha
        self.unique = unique
        self.automatic = automatic  # criado sozinho por PRIMARY KEY / UNIQUE
        self.entries: dict[object, set[int]] = {}

    def add(self, value, rowid: int) -> None:
        if value is not None:
            self.entries.setdefault(value, set()).add(rowid)

    def remove(self, value, rowid: int) -> None:
        rowids = self.entries.get(value)
        if rowids is not None:
            rowids.discard(rowid)
            if not rowids:
                del self.entries[value]

    def lookup(self, value) -> set[int]:
        if value is None:
            return set()
        return self.entries.get(value, set())


class Table:
    """📋 Uma tabela: esquema + heap de linhas + índices."""

    def __init__(self, schema: TableSchema, journal: Journal):
        self.schema = schema
        self.journal = journal
        self.rows: dict[int, list] = {}
        self.next_rowid = 1
        self.indexes: dict[str, Index] = {}
        # PRIMARY KEY e UNIQUE ganham um índice automático: é ele que
        # impede valores repetidos sem precisar varrer a tabela.
        for position, column in enumerate(schema.columns):
            if column.primary_key or column.unique:
                prefix = "pk" if column.primary_key else "uq"
                name = f"{prefix}_{schema.name}_{column.name}"
                self.indexes[name] = Index(name, column.name, position,
                                           unique=True, automatic=True)

    @property
    def name(self) -> str:
        return self.schema.name

    def index_for(self, column: str) -> Index | None:
        """O melhor índice para a coluna (um único, se houver)."""
        found = [ix for ix in self.indexes.values() if ix.column == column]
        found.sort(key=lambda ix: not ix.unique)
        return found[0] if found else None

    def scan(self):
        """Varredura sequencial: entrega ``(rowid, linha)`` de todas as linhas.

        Tiramos uma "foto" da lista antes, para que um UPDATE ou DELETE
        possa mexer na tabela enquanto a percorre.
        """
        yield from list(self.rows.items())

    def next_key(self) -> int:
        """Próximo valor livre para uma PRIMARY KEY inteira (auto-incremento)."""
        index = self.index_for(self.schema.primary_key.name)
        return max(index.entries, default=0) + 1

    # ───────────── mudanças (todas anotadas no diário) ─────────────

    def insert(self, row: list) -> int:
        self._check_unique(row)
        rowid = self.next_rowid
        self.next_rowid += 1
        self._put(rowid, row)
        self.journal.record(lambda: self._remove(rowid))
        return rowid

    def update(self, rowid: int, new_row: list) -> None:
        self._check_unique(new_row, ignore=rowid)
        old_row = self._remove(rowid)
        self._put(rowid, new_row)

        def undo():
            self._remove(rowid)
            self._put(rowid, old_row)
        self.journal.record(undo)

    def delete(self, rowid: int) -> None:
        old_row = self._remove(rowid)
        self.journal.record(lambda: self._put(rowid, old_row))

    def create_index(self, name: str, column: str, unique: bool = False) -> Index:
        position = self.schema.index_of(column)
        index = Index(name, column, position, unique)
        for rowid, row in self.rows.items():
            if unique and index.lookup(row[position]):
                raise ConstraintError(
                    f"Não dá para criar o índice único '{name}': "
                    f"{self.name}.{column} tem valores repetidos ({sql_literal(row[position])})")
            index.add(row[position], rowid)
        self.indexes[name] = index
        self.journal.record(lambda: self.indexes.pop(name))
        return index

    # ───────────── operações "cruas" (sem diário) ─────────────

    def _put(self, rowid: int, row: list) -> None:
        self.rows[rowid] = row
        for index in self.indexes.values():
            index.add(row[index.position], rowid)

    def _remove(self, rowid: int) -> list:
        row = self.rows.pop(rowid)
        for index in self.indexes.values():
            index.remove(row[index.position], rowid)
        return row

    def _check_unique(self, row: list, ignore: int | None = None) -> None:
        for index in self.indexes.values():
            if not index.unique:
                continue
            value = row[index.position]
            if any(rowid != ignore for rowid in index.lookup(value)):
                kind = "PRIMARY KEY" if self.schema.column(index.column).primary_key else "UNIQUE"
                raise ConstraintError(
                    f"{kind} violada: já existe {self.name}.{index.column} = {sql_literal(value)}")


class Storage:
    """🏠 A toca: todas as tabelas + gravação em disco."""

    def __init__(self, path: str | None = None):
        self.path = path
        self.journal = Journal()
        self.tables: dict[str, Table] = {}
        if path and os.path.exists(path):
            self._load()

    def get_table(self, name: str) -> Table:
        try:
            return self.tables[name]
        except KeyError:
            raise CatalogError(f"A tabela '{name}' não existe") from None

    def create_table(self, schema: TableSchema) -> Table:
        if schema.name in self.tables:
            raise CatalogError(f"A tabela '{schema.name}' já existe")
        table = Table(schema, self.journal)
        self.tables[schema.name] = table
        self.journal.record(lambda: self.tables.pop(schema.name))
        return table

    def drop_table(self, name: str) -> None:
        table = self.get_table(name)
        del self.tables[name]
        self.journal.record(lambda: self.tables.__setitem__(name, table))

    def find_index(self, name: str) -> Index | None:
        for table in self.tables.values():
            if name in table.indexes:
                return table.indexes[name]
        return None

    # ───────────────────────── disco ─────────────────────────

    def save(self) -> None:
        """Grava a toca inteira no arquivo — de forma atômica."""
        if not self.path:
            return  # banco em memória: nada a gravar
        data = {
            "formato": "tatu-db",
            "versao": FILE_FORMAT_VERSION,
            "tabelas": [
                {
                    "esquema": table.schema.to_dict(),
                    "proximo_rowid": table.next_rowid,
                    "indices": [
                        {"nome": ix.name, "coluna": ix.column, "unico": ix.unique}
                        for ix in table.indexes.values() if not ix.automatic
                    ],
                    # cada linha vira [rowid, valor1, valor2, ...]
                    "linhas": [[rowid, *row] for rowid, row in table.rows.items()],
                }
                for table in self.tables.values()
            ],
        }
        temp_path = self.path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(_to_json(data) + "\n")
            f.flush()
            os.fsync(f.fileno())       # garante que os bytes chegaram ao disco...
        os.replace(temp_path, self.path)  # ...e só então troca o arquivo, de uma vez

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as error:
            raise TatuError(f"Não consegui ler '{self.path}': {error}") from None
        if not isinstance(data, dict) or data.get("formato") != "tatu-db":
            raise TatuError(f"'{self.path}' não é um arquivo do Tatu DB")

        for item in data["tabelas"]:
            table = Table(TableSchema.from_dict(item["esquema"]), self.journal)
            for rowid, *row in item["linhas"]:
                table._put(rowid, row)
            table.next_rowid = item["proximo_rowid"]
            for ix in item["indices"]:
                table.create_index(ix["nome"], ix["coluna"], ix["unico"])
            self.tables[table.name] = table
        self.journal.clear()  # carregar do disco não é uma mudança a desfazer


def _to_json(value, level: int = 0) -> str:
    """JSON fácil de ler: uma linha da tabela por linha do arquivo.

    Listas de valores simples e objetos pequenos ficam numa linha só;
    o resto é indentado.
    """
    compact = json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        if not any(isinstance(item, (list, dict)) for item in value):
            return compact
    elif not isinstance(value, dict) or len(compact) <= 80:
        return compact
    pad, end = "  " * (level + 1), "  " * level
    if isinstance(value, dict):
        items = [f"{pad}{json.dumps(k, ensure_ascii=False)}: {_to_json(v, level + 1)}"
                 for k, v in value.items()]
        return "{\n" + ",\n".join(items) + f"\n{end}}}"
    items = [pad + _to_json(item, level + 1) for item in value]
    return "[\n" + ",\n".join(items) + f"\n{end}]"
