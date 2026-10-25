"""
📐 Esquema: a "planta" de cada tabela.

O esquema diz quais colunas a tabela tem, de que tipo e com quais
restrições. Ele não guarda dados — isso é trabalho do ``storage.py``.
"""

from dataclasses import dataclass

from .datatypes import sql_literal
from .errors import CatalogError


@dataclass
class Column:
    name: str
    type: str                       # INTEGER, REAL, TEXT ou BOOLEAN
    primary_key: bool = False
    not_null: bool = False
    unique: bool = False
    default: object = None          # valor já calculado (não uma expressão)
    references: tuple | None = None  # (tabela, coluna) da chave estrangeira

    def to_sql(self) -> str:
        parts = [self.name, self.type]
        if self.primary_key:
            parts.append("PRIMARY KEY")
        elif self.not_null:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            parts.append(f"DEFAULT {sql_literal(self.default)}")
        if self.references:
            parts.append(f"REFERENCES {self.references[0]}({self.references[1]})")
        return " ".join(parts)


@dataclass
class TableSchema:
    name: str
    columns: list[Column]

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    @property
    def primary_key(self) -> Column | None:
        return next((c for c in self.columns if c.primary_key), None)

    def index_of(self, column_name: str) -> int:
        """Posição da coluna na linha (``linha[posição]``)."""
        for i, column in enumerate(self.columns):
            if column.name == column_name:
                return i
        raise CatalogError(f"A tabela '{self.name}' não tem a coluna '{column_name}'")

    def column(self, column_name: str) -> Column:
        return self.columns[self.index_of(column_name)]

    def to_sql(self) -> str:
        body = ",\n".join(f"  {c.to_sql()}" for c in self.columns)
        return f"CREATE TABLE {self.name} (\n{body}\n);"

    # ── ida e volta para o arquivo .tatu (só guardamos o que não é padrão) ──

    def to_dict(self) -> dict:
        return {"nome": self.name, "colunas": [_column_to_dict(c) for c in self.columns]}

    @classmethod
    def from_dict(cls, data: dict) -> "TableSchema":
        return cls(data["nome"], [_column_from_dict(c) for c in data["colunas"]])


def _column_to_dict(column: Column) -> dict:
    data = {"nome": column.name, "tipo": column.type}
    if column.primary_key:
        data["chave_primaria"] = True
    elif column.not_null:
        data["nao_nulo"] = True
    if column.unique:
        data["unico"] = True
    if column.default is not None:
        data["padrao"] = column.default
    if column.references:
        data["referencia"] = list(column.references)
    return data


def _column_from_dict(data: dict) -> Column:
    primary_key = data.get("chave_primaria", False)
    references = data.get("referencia")
    return Column(
        name=data["nome"],
        type=data["tipo"],
        primary_key=primary_key,
        not_null=primary_key or data.get("nao_nulo", False),
        unique=data.get("unico", False),
        default=data.get("padrao"),
        references=tuple(references) if references else None,
    )
