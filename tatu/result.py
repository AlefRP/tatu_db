"""
📋 Resultado de um comando — e o desenho bonito da tabela.

    ╭────┬──────────────┬───────╮
    │ id │ apelido      │ idade │
    ├────┼──────────────┼───────┤
    │  1 │ Bolinha      │     3 │
    │  2 │ Canastrão    │     7 │
    ╰────┴──────────────┴───────╯
"""

from dataclasses import dataclass, field

UNICODE_BOX = {"top": ("╭", "┬", "╮"), "mid": ("├", "┼", "┤"), "bottom": ("╰", "┴", "╯"),
               "line": "─", "wall": "│"}
ASCII_BOX = {"top": ("+", "+", "+"), "mid": ("+", "+", "+"), "bottom": ("+", "+", "+"),
             "line": "-", "wall": "|"}


@dataclass
class Result:
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    message: str | None = None  # "3 linha(s) inserida(s)", "Tabela criada"...
    rowcount: int = 0           # linhas afetadas por INSERT / UPDATE / DELETE

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        return self.rows[i]

    def scalar(self):
        """O primeiro valor da primeira linha (ótimo para ``SELECT COUNT(*)``)."""
        return self.rows[0][0] if self.rows else None

    def as_dicts(self) -> list[dict]:
        return [dict(zip(self.columns, row)) for row in self.rows]

    def __str__(self):
        if self.columns:
            return format_table(self.columns, self.rows)
        return self.message or ""


def format_cell(value) -> str:
    if value is None:
        return "NULL"
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    if isinstance(value, float):
        return f"{value:.1f}" if value.is_integer() else f"{value:.10g}"
    return str(value)


def format_table(columns, rows, unicode: bool = True, paint=None) -> str:
    """Desenha a tabela com bordas. ``paint`` (opcional) pinta partes do texto."""
    box = UNICODE_BOX if unicode else ASCII_BOX
    paint = paint or (lambda text, *styles: text)
    cells = [[format_cell(v) for v in row] for row in rows]
    widths = [max([len(name)] + [len(row[i]) for row in cells]) for i, name in enumerate(columns)]
    numeric = [bool(rows) and all(isinstance(row[i], (int, float)) and not isinstance(row[i], bool)
                                  or row[i] is None for row in rows)
               for i in range(len(columns))]

    def border(kind):
        left, cross, right = box[kind]
        return paint(left + cross.join(box["line"] * (w + 2) for w in widths) + right, "dim")

    def line(values, styler):
        wall = paint(box["wall"], "dim")
        parts = [styler(i, v, v.rjust(w) if numeric[i] else v.ljust(w))
                 for i, (v, w) in enumerate(zip(values, widths))]
        return wall + wall.join(f" {p} " for p in parts) + wall

    def header_style(i, value, padded):
        return paint(padded, "bold", "cyan")

    def cell_style(raw_row):
        return lambda i, value, padded: paint(padded, "dim") if raw_row[i] is None else padded

    out = [border("top"), line(list(columns), header_style), border("mid")]
    out += [line(row, cell_style(raw)) for row, raw in zip(cells, rows)]
    out.append(border("bottom"))
    return "\n".join(out)
