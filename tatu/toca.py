"""Toca: cliente gráfico do Tatu DB, feito apenas com a biblioteca padrão.

O motor continua independente da interface. A sessão traduz suas operações;
o Tk cuida das janelas, e uma única tarefa de trabalho executa o SQL sem
interromper a edição. Nenhum widget é acessado fora da thread principal.
"""

from __future__ import annotations

import argparse
import queue
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter import font as tkfont
except ImportError:
    tk = filedialog = tkfont = messagebox = ttk = None

from .errors import TatuError
from .result import format_cell
from .toca_session import Session, export_csv, read_sql, write_sql
from .tokenizer import KEYWORDS

FIRST_QUERY = "SELECT nome, nome_cientifico, peso_kg, ameacada\nFROM especies\nORDER BY peso_kg DESC;"
EMPTY_QUERY = "-- Escreva sua consulta aqui.\nSELECT 1 AS inicio;"
EXAMPLES = (
    ("Explorar as espécies", FIRST_QUERY),
    (
        "Cruzar tabelas",
        "SELECT t.apelido, e.nome AS especie\nFROM tatus t LEFT JOIN especies e\n"
        "  ON t.especie_id = e.id\nORDER BY t.apelido;",
    ),
    (
        "Agrupar e contar",
        "SELECT bioma, COUNT(*) AS vezes\nFROM avistamentos\nGROUP BY bioma\nORDER BY vezes DESC, bioma;",
    ),
    ("Entender o plano", "EXPLAIN SELECT apelido\nFROM tatus\nWHERE especie_id = 2;"),
    (
        "Experimentar uma transação",
        "BEGIN;\nUPDATE tatus SET idade = idade + 1 WHERE id = 1;\n"
        "SELECT * FROM tatus WHERE id = 1;\nROLLBACK;",
    ),
)
COLORS = {
    "light": {
        "bg": "#f5f6f3",
        "surface": "#ffffff",
        "sidebar": "#edf3ee",
        "editor": "#fbfdfa",
        "text": "#243c34",
        "muted": "#6c7d75",
        "border": "#dce5dd",
        "accent": "#247b64",
        "accent_hover": "#1a6651",
        "accent_text": "#ffffff",
        "selected": "#dbece1",
        "stripe": "#f4f7f3",
        "keyword": "#126faa",
        "string": "#a15d29",
        "number": "#7d5b9a",
        "comment": "#829086",
        "error": "#ae403b",
        "error_bg": "#fff0eb",
        "gutter": "#f0f5ef",
        "current": "#eef6f0",
    },
    "dark": {
        "bg": "#202725",
        "surface": "#252f2b",
        "sidebar": "#1b2b25",
        "editor": "#15231d",
        "text": "#e6eee7",
        "muted": "#a1b3a6",
        "border": "#35473d",
        "accent": "#86d2ad",
        "accent_hover": "#a1e0bd",
        "accent_text": "#153a2b",
        "selected": "#2e5140",
        "stripe": "#29372e",
        "keyword": "#85c5ed",
        "string": "#e5bd86",
        "number": "#c2a4de",
        "comment": "#7c9a87",
        "error": "#ffaaa0",
        "error_bg": "#462b28",
        "gutter": "#1c2e24",
        "current": "#1e3427",
    },
}
TOKEN_PATTERN = re.compile(
    r"(?P<comment>--[^\n]*|/\*[\s\S]*?\*/)"
    r"|(?P<string>'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")"
    r"|(?P<number>\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)"
    r"|(?P<word>\b[A-Za-z_][A-Za-z_0-9]*\b)",
)


class TocaApp:
    """Janela principal; os widgets nomeados também facilitam testes visuais."""

    def __init__(self, root=None, session=None):
        if tk is None:
            raise RuntimeError("O Python não inclui Tkinter. Instale o suporte Tk para abrir a Toca.")
        self.root = root or tk.Tk()
        self.session = session or Session()
        self.query_path = None
        self._saved_sql = ""
        self._setting_text = False
        self._busy = False
        self._closed = False
        self._highlight_job = None
        self._results = []
        self._result_index = 0
        self._displayed_rows = []
        self._selected_cell = (None, None)
        self._table_names = {}
        self._history_entries = {}
        self._styled_frames = []
        self._styled_labels = []
        self._menus = []
        self._controls = []
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="toca-sql")
        self._mailbox = queue.Queue()
        self.theme_name = tk.StringVar(self.root, "light")
        self.status_var = tk.StringVar(self.root, "Pronto para explorar.")
        self.cursor_var = tk.StringVar(self.root, "Ln 1, Col 1")
        self.connection_var = tk.StringVar(self.root)
        self.location_var = tk.StringVar(self.root)
        self.table_count_var = tk.StringVar(self.root)
        self.transaction_var = tk.StringVar(self.root)
        self.result_summary_var = tk.StringVar(self.root, "Resultados da consulta")
        self.query_name_var = tk.StringVar(self.root, "Consulta sem título")
        self.result_choice_var = tk.StringVar(self.root)
        self._choose_fonts()
        self._build_window()
        self._build_menu()
        self._bind_keys()
        self.apply_theme()
        self._refresh_catalog()
        self.set_sql(FIRST_QUERY if "especies" in self.session.tables() else EMPTY_QUERY)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_job = self.root.after(60, self._drain_mailbox)
        self._startup_job = self.root.after(100, self.run_query)

    def _choose_fonts(self):
        families = set(tkfont.families(self.root))
        self.body_family = next(
            (x for x in ("Segoe UI", "Helvetica", "DejaVu Sans") if x in families), "TkDefaultFont"
        )
        self.mono_family = next(
            (x for x in ("Cascadia Code", "Consolas", "DejaVu Sans Mono") if x in families), "TkFixedFont"
        )
        self.body_font = (self.body_family, 10)
        self.small_font = (self.body_family, 9)
        self.mono_font = (self.mono_family, 11)

    def _frame(self, parent, role="bg", **kwargs):
        frame = tk.Frame(parent, borderwidth=0, **kwargs)
        self._styled_frames.append((frame, role))
        return frame

    def _label(self, parent, text=None, role="bg", tone="text", **kwargs):
        kwargs.setdefault("font", self.body_font)
        kwargs.setdefault("anchor", "w")
        label = tk.Label(parent, text=text, borderwidth=0, **kwargs)
        self._styled_labels.append((label, role, tone))
        return label

    def _button(self, parent, text, command, accent=False, **kwargs):
        button = ttk.Button(
            parent, text=text, command=command, style="Accent.TButton" if accent else "TButton", **kwargs
        )
        self._controls.append(button)
        return button

    def _build_window(self):
        root = self.root
        root.title("Toca · Tatu DB")
        root.geometry("1220x800")
        root.minsize(920, 640)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.sidebar = self._frame(root, "sidebar", width=236)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.columnconfigure(0, weight=1)
        self.sidebar.rowconfigure(4, weight=1)
        branding = self._frame(self.sidebar, "sidebar")
        branding.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 25))
        icon_path = Path(__file__).with_name("assets") / "toca.png"
        self.icon = None
        if icon_path.is_file():
            try:
                full_icon = tk.PhotoImage(master=root, file=str(icon_path))
                root.iconphoto(True, full_icon)
                self.full_icon = full_icon
                self.icon = full_icon.subsample(max(1, full_icon.width() // 48))
                self._label(branding, image=self.icon, role="sidebar").pack(side="left", padx=(0, 12))
            except tk.TclError:
                pass
        brand_text = self._frame(branding, "sidebar")
        brand_text.pack(side="left")
        self._label(brand_text, "Toca", role="sidebar", font=(self.body_family, 25, "bold")).pack(anchor="w")
        self._label(brand_text, "TATU DB", role="sidebar", tone="accent", font=self.small_font).pack(
            anchor="w"
        )
        connection = self._frame(self.sidebar, "sidebar")
        connection.grid(row=1, column=0, sticky="ew", padx=22)
        self._label(
            connection, "●  CONEXÃO LOCAL", role="sidebar", tone="accent", font=(self.body_family, 9, "bold")
        ).pack(anchor="w", pady=(0, 12))
        self._label(
            connection,
            textvariable=self.connection_var,
            role="sidebar",
            font=(self.body_family, 12, "bold"),
            wraplength=190,
        ).pack(anchor="w")
        self._label(
            connection,
            textvariable=self.location_var,
            role="sidebar",
            tone="muted",
            font=self.small_font,
            wraplength=190,
        ).pack(anchor="w", pady=(7, 0))
        ttk.Separator(self.sidebar).grid(row=2, column=0, sticky="ew", padx=22, pady=22)
        self._label(
            self.sidebar,
            textvariable=self.table_count_var,
            role="sidebar",
            tone="muted",
            font=(self.body_family, 9, "bold"),
        ).grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 10))
        table_area = self._frame(self.sidebar, "sidebar")
        table_area.grid(row=4, column=0, sticky="nsew", padx=(12, 6))
        table_area.rowconfigure(0, weight=1)
        table_area.columnconfigure(0, weight=1)
        self.table_tree = ttk.Treeview(
            table_area, show="tree", columns=("rows",), selectmode="browse", style="Catalog.Treeview"
        )
        self.table_tree.column("#0", width=152, minwidth=90, stretch=True)
        self.table_tree.column("rows", width=40, minwidth=35, anchor="e", stretch=False)
        self.table_tree.grid(row=0, column=0, sticky="nsew")
        catalog_scroll = ttk.Scrollbar(table_area, orient="vertical", command=self.table_tree.yview)
        catalog_scroll.grid(row=0, column=1, sticky="ns")
        self.table_tree.configure(yscrollcommand=catalog_scroll.set)
        self.table_tree.bind("<<TreeviewSelect>>", self._table_selected)
        self.table_tree.bind("<Double-1>", self.query_selected_table)
        self.table_tree.bind("<Return>", self.query_selected_table)
        self._button(self.sidebar, "Consultar tabela", self.query_selected_table).grid(
            row=5, column=0, sticky="ew", padx=20, pady=(14, 18)
        )
        self.persistence_card = self._frame(self.sidebar, "surface", padx=14, pady=13)
        self.persistence_card.grid(row=6, column=0, sticky="ew", padx=18, pady=(0, 16))
        self._label(
            self.persistence_card,
            "DO SEU JEITO",
            role="surface",
            tone="accent",
            font=(self.body_family, 9, "bold"),
        ).pack(anchor="w")
        self.persistence_label = self._label(
            self.persistence_card,
            role="surface",
            tone="muted",
            wraplength=172,
            font=self.small_font,
            justify="left",
        )
        self.persistence_label.pack(anchor="w", pady=(7, 0))
        side_actions = self._frame(self.sidebar, "sidebar")
        side_actions.grid(row=7, column=0, sticky="ew", padx=18, pady=(0, 20))
        side_actions.columnconfigure((0, 1), weight=1)
        self._button(side_actions, "Novo", self.new_database).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._button(side_actions, "Abrir", self.open_database).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        self.main = self._frame(root)
        self.main.grid(row=0, column=1, sticky="nsew", padx=26, pady=(22, 16))
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(3, weight=1)
        header = self._frame(self.main)
        header.grid(row=0, column=0, sticky="ew")
        self._label(header, "Seu banco, por dentro.", font=(self.body_family, 19, "bold")).pack(anchor="w")
        self._label(header, "Explore os dados. Escreva SQL. Entenda o caminho.", tone="muted").pack(
            anchor="w", pady=(6, 0)
        )
        ttk.Separator(self.main).grid(row=1, column=0, sticky="ew", pady=(18, 16))
        toolbar = self._frame(self.main)
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        toolbar.columnconfigure(0, weight=1)
        query_title = self._frame(toolbar)
        query_title.grid(row=0, column=0, sticky="w")
        self._label(query_title, "Consulta SQL", font=(self.body_family, 11, "bold")).pack(anchor="w")
        self._label(query_title, textvariable=self.query_name_var, tone="muted", font=self.small_font).pack(
            anchor="w", pady=(2, 0)
        )
        self.examples_button = ttk.Menubutton(toolbar, text="Exemplos", style="TMenubutton")
        self.examples_button.grid(row=0, column=1, padx=(10, 7))
        self.examples_menu = tk.Menu(self.examples_button, tearoff=False)
        self.examples_button.configure(menu=self.examples_menu)
        for label, sql in EXAMPLES:
            self.examples_menu.add_command(label=label, command=lambda value=sql: self.use_example(value))
        self._menus.append(self.examples_menu)
        self._controls.append(self.examples_button)
        self._button(toolbar, "Salvar SQL", self.save_query).grid(row=0, column=2, padx=(0, 7))
        self.run_button = self._button(toolbar, "▶  Executar", self.run_query, accent=True)
        self.run_button.grid(row=0, column=3)

        self.splitter = ttk.Panedwindow(self.main, orient="vertical")
        self.splitter.grid(row=3, column=0, sticky="nsew")
        self.editor_frame = self._frame(self.splitter, "editor")
        self.editor_frame.columnconfigure(1, weight=1)
        self.editor_frame.rowconfigure(0, weight=1)
        self.line_numbers = tk.Canvas(self.editor_frame, width=43, highlightthickness=0)
        self.line_numbers.grid(row=0, column=0, sticky="ns")
        self.editor = tk.Text(
            self.editor_frame,
            font=self.mono_font,
            wrap="none",
            undo=True,
            maxundo=200,
            borderwidth=0,
            highlightthickness=0,
            padx=13,
            pady=12,
            spacing1=2,
            spacing3=2,
            height=11,
            tabs=("4c",),
        )
        self.editor.grid(row=0, column=1, sticky="nsew")
        editor_y = ttk.Scrollbar(self.editor_frame, orient="vertical", command=self._scroll_editor)
        editor_y.grid(row=0, column=2, sticky="ns")
        self.editor.configure(yscrollcommand=lambda a, b: self._editor_yview(editor_y, a, b))
        editor_x = ttk.Scrollbar(self.editor_frame, orient="horizontal", command=self.editor.xview)
        editor_x.grid(row=1, column=1, sticky="ew")
        self.editor.configure(xscrollcommand=editor_x.set)
        self.editor.bind("<<Modified>>", self._editor_modified)
        self.editor.bind("<KeyRelease>", self._cursor_changed, add=True)
        self.editor.bind("<ButtonRelease-1>", self._cursor_changed, add=True)
        self.editor.bind("<Configure>", self._redraw_lines, add=True)
        self.editor.bind("<Tab>", self._insert_indent)
        self.splitter.add(self.editor_frame, weight=2)
        output = self._frame(self.splitter)
        output.columnconfigure(0, weight=1)
        output.rowconfigure(0, weight=1)
        self.notebook = ttk.Notebook(output)
        self.notebook.grid(row=0, column=0, sticky="nsew", pady=(14, 0))
        self.data_tab = self._frame(self.notebook, "surface")
        self.schema_tab = self._frame(self.notebook, "surface")
        self.history_tab = self._frame(self.notebook, "surface")
        self.messages_tab = self._frame(self.notebook, "surface")
        for frame, name in (
            (self.data_tab, "Resultados"),
            (self.schema_tab, "Estrutura"),
            (self.history_tab, "Histórico"),
            (self.messages_tab, "Mensagens"),
        ):
            self.notebook.add(frame, text=name)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
        self._build_results()
        self._build_schema()
        self._build_history()
        self.messages = tk.Text(
            self.messages_tab,
            state="disabled",
            font=self.mono_font,
            wrap="word",
            borderwidth=0,
            padx=18,
            pady=16,
            height=7,
        )
        self.messages.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.splitter.add(output, weight=3)
        footer = self._frame(root, "sidebar", padx=18, pady=7)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self._label(
            footer, textvariable=self.status_var, role="sidebar", tone="muted", font=self.small_font
        ).grid(row=0, column=0, sticky="w")
        self._label(
            footer, textvariable=self.transaction_var, role="sidebar", tone="accent", font=self.small_font
        ).grid(row=0, column=1, sticky="e", padx=(12, 18))
        self._label(
            footer, textvariable=self.cursor_var, role="sidebar", tone="muted", font=self.small_font
        ).grid(row=0, column=2, sticky="e")

    def _tree(self, parent, columns, headings, widths):
        frame = self._frame(parent, "surface")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        for col, label, width in zip(columns, headings, widths):
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, minwidth=65, stretch=True)
        tree.grid(row=0, column=0, sticky="nsew")
        y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        y.grid(row=0, column=1, sticky="ns")
        x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        x.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        return frame, tree

    def _build_results(self):
        bar = self._frame(self.data_tab, "surface", padx=12, pady=10)
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)
        self._label(
            bar, textvariable=self.result_summary_var, role="surface", tone="muted", font=self.small_font
        ).grid(row=0, column=0, sticky="w")
        self.result_choice = ttk.Combobox(
            bar, textvariable=self.result_choice_var, width=18, state="readonly", style="TCombobox"
        )
        self.result_choice.grid(row=0, column=1, padx=(12, 5))
        self.result_choice.bind("<<ComboboxSelected>>", self._result_selected)
        self._button(bar, "←", lambda: self._move_result(-1), width=3).grid(row=0, column=2, padx=2)
        self._button(bar, "→", lambda: self._move_result(1), width=3).grid(row=0, column=3, padx=2)
        tree_frame, self.result_tree = self._tree(self.data_tab, (), (), ())
        tree_frame.grid(row=1, column=0, sticky="nsew")
        self.result_tree.bind("<ButtonRelease-1>", self._select_cell)
        self.result_tree.bind("<Control-c>", self.copy_result)
        self.result_tree.bind("<Double-1>", self._inspect_cell)
        self.result_tree.bind("<Button-3>", self._result_context)
        self.empty_label = self._label(
            tree_frame,
            "Execute uma consulta para explorar os resultados.",
            role="surface",
            tone="muted",
            justify="center",
        )
        self.empty_label.place(relx=0.5, rely=0.45, anchor="center")

    def _build_schema(self):
        self.schema_title_var = tk.StringVar(self.root, "Selecione uma tabela na lateral.")
        self._label(
            self.schema_tab,
            textvariable=self.schema_title_var,
            role="surface",
            font=(self.body_family, 10, "bold"),
            padx=15,
            pady=12,
        ).grid(row=0, column=0, sticky="ew")
        schema_frame, self.schema_tree = self._tree(
            self.schema_tab,
            ("name", "type", "rules", "default", "reference"),
            ("Coluna / índice", "Tipo", "Restrições", "Padrão", "Referência"),
            (170, 95, 200, 90, 150),
        )
        schema_frame.grid(row=1, column=0, sticky="nsew")

    def _build_history(self):
        self._label(
            self.history_tab,
            "Duplo clique para recuperar uma consulta no editor.",
            role="surface",
            tone="muted",
            padx=14,
            pady=12,
            font=self.small_font,
        ).grid(row=0, column=0, sticky="ew")
        history_frame, self.history_tree = self._tree(
            self.history_tab,
            ("state", "sql", "rows", "time"),
            ("Estado", "Consulta SQL", "Linhas", "Tempo"),
            (75, 560, 70, 85),
        )
        history_frame.grid(row=1, column=0, sticky="nsew")
        self.history_tree.bind("<Double-1>", self._recover_history)
        self.history_tree.bind("<Return>", self._recover_history)

    def _build_menu(self):
        menu = tk.Menu(self.root)
        self.root.configure(menu=menu)
        self._menus.append(menu)
        file_menu = tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Arquivo", menu=file_menu)
        file_menu.add_command(label="Novo banco…", accelerator="Ctrl+N", command=self.new_database)
        file_menu.add_command(label="Abrir banco…", accelerator="Ctrl+O", command=self.open_database)
        file_menu.add_command(
            label="Salvar banco como…", accelerator="Ctrl+Shift+S", command=self.save_database
        )
        file_menu.add_command(label="Novo laboratório de exemplo", command=self.new_demo)
        file_menu.add_separator()
        file_menu.add_command(
            label="Abrir consulta SQL…", accelerator="Ctrl+Shift+O", command=self.load_query
        )
        file_menu.add_command(label="Salvar consulta SQL…", accelerator="Ctrl+S", command=self.save_query)
        file_menu.add_command(label="Salvar consulta como…", command=lambda: self.save_query(save_as=True))
        file_menu.add_command(label="Exportar resultado CSV…", command=self.export_result)
        file_menu.add_separator()
        file_menu.add_command(label="Fechar", command=self.close)
        edit_menu = tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Editar", menu=edit_menu)
        for text, key, virtual in (
            ("Desfazer", "Ctrl+Z", "<<Undo>>"),
            ("Refazer", "Ctrl+Y", "<<Redo>>"),
            ("Recortar", "Ctrl+X", "<<Cut>>"),
            ("Copiar", "Ctrl+C", "<<Copy>>"),
            ("Colar", "Ctrl+V", "<<Paste>>"),
        ):
            edit_menu.add_command(
                label=text, accelerator=key, command=lambda value=virtual: self._edit_command(value)
            )
        edit_menu.add_separator()
        edit_menu.add_command(label="Selecionar todo o SQL", accelerator="Ctrl+A", command=self.select_all)
        edit_menu.add_command(label="Copiar célula do resultado", command=self.copy_result)
        query_menu = tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Consulta", menu=query_menu)
        query_menu.add_command(
            label="Executar SQL / seleção", accelerator="Ctrl+Enter / F5", command=self.run_query
        )
        query_menu.add_separator()
        query_menu.add_command(label="Iniciar transação", command=lambda: self.run_sql("BEGIN;"))
        query_menu.add_command(label="Confirmar transação", command=lambda: self.run_sql("COMMIT;"))
        query_menu.add_command(label="Desfazer transação", command=lambda: self.run_sql("ROLLBACK;"))
        view_menu = tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Exibir", menu=view_menu)
        view_menu.add_radiobutton(
            label="Tema claro", variable=self.theme_name, value="light", command=self.apply_theme
        )
        view_menu.add_radiobutton(
            label="Tema escuro", variable=self.theme_name, value="dark", command=self.apply_theme
        )
        view_menu.add_separator()
        view_menu.add_command(label="Atualizar tabelas", accelerator="F6", command=self.refresh_catalog)
        help_menu = tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Ajuda", menu=help_menu)
        help_menu.add_command(label="Sobre a Toca", command=self.about)
        self._menus.extend((file_menu, edit_menu, query_menu, view_menu, help_menu))

    def _bind_keys(self):
        for key, handler in (
            ("<Control-Return>", self.run_query),
            ("<F5>", self.run_query),
            ("<F6>", self.refresh_catalog),
            ("<Control-n>", self.new_database),
            ("<Control-o>", self.open_database),
            ("<Control-s>", self.save_query),
            ("<Control-Shift-S>", self.save_database),
            ("<Control-Shift-O>", self.load_query),
        ):
            self.root.bind(key, handler)
        self.editor.bind("<Control-a>", self.select_all)

    def apply_theme(self):
        p = COLORS[self.theme_name.get()]
        self.palette = p
        self.root.configure(background=p["bg"])
        for frame, role in self._styled_frames:
            frame.configure(background=p[role])
        for label, role, tone in self._styled_labels:
            label.configure(background=p[role], foreground=p[tone])
        s = self.style
        s.configure(
            ".",
            font=self.body_font,
            background=p["bg"],
            foreground=p["text"],
            bordercolor=p["border"],
            lightcolor=p["border"],
            darkcolor=p["border"],
            troughcolor=p["sidebar"],
            focuscolor=p["accent"],
        )
        s.configure("TButton", background=p["surface"], padding=(12, 8), borderwidth=1, relief="flat")
        s.map(
            "TButton",
            background=[("active", p["selected"]), ("pressed", p["selected"])],
            foreground=[("disabled", p["muted"])],
        )
        s.configure(
            "Accent.TButton",
            background=p["accent"],
            foreground=p["accent_text"],
            font=(self.body_family, 10, "bold"),
            padding=(17, 9),
        )
        s.map(
            "Accent.TButton",
            background=[("active", p["accent_hover"]), ("disabled", p["muted"])],
            foreground=[("active", p["accent_text"]), ("disabled", p["bg"])],
        )
        s.configure("TMenubutton", background=p["surface"], padding=(12, 8), relief="flat")
        s.map("TMenubutton", background=[("active", p["selected"])])
        s.configure("TCombobox", fieldbackground=p["surface"], background=p["surface"], arrowcolor=p["muted"])
        s.map(
            "TCombobox",
            fieldbackground=[("readonly", p["surface"])],
            foreground=[("readonly", p["text"])],
            selectbackground=[("readonly", p["selected"])],
        )
        s.configure("TNotebook", background=p["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure(
            "TNotebook.Tab", background=p["bg"], foreground=p["muted"], padding=(17, 10), borderwidth=0
        )
        s.map(
            "TNotebook.Tab", background=[("selected", p["surface"])], foreground=[("selected", p["accent"])]
        )
        s.configure("TPanedwindow", background=p["bg"])
        s.configure(
            "Treeview",
            background=p["surface"],
            fieldbackground=p["surface"],
            foreground=p["text"],
            rowheight=31,
            borderwidth=0,
            font=self.body_font,
        )
        s.configure(
            "Treeview.Heading",
            background=p["sidebar"],
            foreground=p["text"],
            font=(self.body_family, 9, "bold"),
            padding=(10, 9),
            relief="flat",
        )
        s.map("Treeview", background=[("selected", p["selected"])], foreground=[("selected", p["accent"])])
        s.configure(
            "Catalog.Treeview",
            background=p["sidebar"],
            fieldbackground=p["sidebar"],
            rowheight=37,
            font=self.body_font,
        )
        for tree in (self.result_tree, self.schema_tree, self.history_tree):
            tree.tag_configure("even", background=p["surface"])
            tree.tag_configure("odd", background=p["stripe"])
            tree.tag_configure("error", foreground=p["error"])
        self.editor.configure(
            background=p["editor"],
            foreground=p["text"],
            insertbackground=p["accent"],
            selectbackground=p["selected"],
            selectforeground=p["text"],
        )
        for tag in ("keyword", "string", "number", "comment"):
            self.editor.tag_configure(tag, foreground=p[tag])
        self.editor.tag_configure("current_line", background=p["current"])
        self.editor.tag_lower("current_line")
        self.line_numbers.configure(background=p["gutter"])
        self.messages.configure(
            background=p["surface"],
            foreground=p["text"],
            selectbackground=p["selected"],
            selectforeground=p["text"],
        )
        self.messages.tag_configure("error", foreground=p["error"])
        for menu in self._menus:
            menu.configure(
                background=p["surface"],
                foreground=p["text"],
                activebackground=p["selected"],
                activeforeground=p["accent"],
                selectcolor=p["accent"],
                borderwidth=0,
            )
        self.root.option_add("*TCombobox*Listbox.background", p["surface"])
        self.root.option_add("*TCombobox*Listbox.foreground", p["text"])
        self._redraw_lines()

    def set_sql(self, sql, path=None):
        self._setting_text = True
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", sql)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self._saved_sql = sql
        self.query_path = Path(path) if path else None
        self._setting_text = False
        self._highlight()
        self._cursor_changed()
        self._update_title()

    def _editor_modified(self, _event=None):
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        if not self._setting_text:
            if self._highlight_job:
                self.root.after_cancel(self._highlight_job)
            self._highlight_job = self.root.after(130, self._highlight)
            self._update_title()
        self._redraw_lines()

    def _highlight(self):
        self._highlight_job = None
        sql = self.editor.get("1.0", "end-1c")
        for tag in ("keyword", "string", "number", "comment"):
            self.editor.tag_remove(tag, "1.0", "end")
        # Colorir é uma ajuda visual; o tokenizer do motor continua sendo a
        # autoridade. Em arquivos grandes, limitar o realce mantém o editor ágil.
        for match in TOKEN_PATTERN.finditer(sql[:250000]):
            tag = match.lastgroup
            if tag == "word":
                if match.group().upper() not in KEYWORDS:
                    continue
                tag = "keyword"
            self.editor.tag_add(tag, f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        self._cursor_changed()

    def _cursor_changed(self, _event=None):
        line, col = self.editor.index("insert").split(".")
        self.cursor_var.set(f"Ln {line}, Col {int(col) + 1}  ·  UTF-8")
        self.editor.tag_remove("current_line", "1.0", "end")
        self.editor.tag_add("current_line", "insert linestart", "insert lineend+1c")
        self._redraw_lines()

    def _redraw_lines(self, _event=None):
        self.line_numbers.delete("all")
        index = self.editor.index("@0,0")
        while True:
            info = self.editor.dlineinfo(index)
            if info is None:
                break
            self.line_numbers.create_text(
                31,
                info[1] + 2,
                anchor="ne",
                text=index.split(".")[0],
                font=(self.mono_family, 9),
                fill=self.palette["muted"],
            )
            index = self.editor.index(f"{index}+1line")

    def _scroll_editor(self, *args):
        self.editor.yview(*args)
        self._redraw_lines()

    def _editor_yview(self, scrollbar, first, last):
        scrollbar.set(first, last)
        self._redraw_lines()

    def _insert_indent(self, _event=None):
        self.editor.insert("insert", "    ")
        return "break"

    def select_all(self, _event=None):
        self.editor.focus_set()
        self.editor.tag_add("sel", "1.0", "end-1c")
        self.editor.mark_set("insert", "end-1c")
        return "break"

    def _edit_command(self, virtual):
        if virtual == "<<Copy>>" and self.root.focus_get() == self.result_tree:
            return self.copy_result()
        self.editor.focus_set()
        try:
            self.editor.event_generate(virtual)
        except tk.TclError:
            pass
        return "break"

    def _update_title(self):
        dirty = self.editor.get("1.0", "end-1c") != self._saved_sql
        query = self.query_path.name if self.query_path else "Consulta sem título"
        self.query_name_var.set(f"{query}{'  •' if dirty else ''}")
        name = Path(self.session.path).name if self.session.path else "Laboratório em memória"
        self.root.title(f"{'● ' if dirty else ''}{name} — Toca")

    def _refresh_catalog(self):
        selected = self._selected_table()
        self.table_tree.delete(*self.table_tree.get_children())
        self._table_names.clear()
        names = self.session.tables()
        for i, name in enumerate(names):
            info = self.session.table_info(name)
            item = self.table_tree.insert(
                "", "end", iid=f"table-{i}", text=f"▦  {name}", values=(info.row_count,)
            )
            self._table_names[item] = name
            if name == selected:
                self.table_tree.selection_set(item)
        if not self.table_tree.selection() and names:
            desired = "especies" if "especies" in names else names[0]
            item = next(key for key, value in self._table_names.items() if value == desired)
            self.table_tree.selection_set(item)
        self.table_count_var.set(f"TABELAS  ·  {len(names)}")
        self.connection_var.set(Path(self.session.path).name if self.session.path else "Laboratório")
        self.location_var.set("Arquivo no disco · autocommit" if self.session.path else "Banco em memória")
        self.persistence_label.configure(
            text=(
                "Alterações confirmadas são salvas no arquivo deste computador."
                if self.session.path
                else "Um laboratório seguro. Salve como .tatu para continuar depois."
            )
        )
        self.transaction_var.set("● Transação aberta" if self.session.in_transaction else "● Autocommit")
        self._show_schema()
        self._update_title()

    def refresh_catalog(self, _event=None):
        if not self._busy:
            self._refresh_catalog()
            self.status_var.set("Catálogo atualizado a partir da conexão atual.")
        return "break"

    def _selected_table(self):
        selection = self.table_tree.selection()
        return self._table_names.get(selection[0]) if selection else None

    def _table_selected(self, _event=None):
        if not self._busy:
            self._show_schema()

    def _show_schema(self):
        self.schema_tree.delete(*self.schema_tree.get_children())
        name = self._selected_table()
        if not name:
            self.schema_title_var.set("Selecione uma tabela na lateral.")
            return
        info = self.session.table_info(name)
        self.schema_title_var.set(
            f"{name}  ·  {len(info.columns)} colunas  ·  {info.row_count} linhas  ·  "
            f"{len(info.indexes)} índices"
        )
        for i, col in enumerate(info.columns):
            rules = [
                label
                for active, label in (
                    (col.primary_key, "CHAVE PRIMÁRIA"),
                    (col.not_null and not col.primary_key, "OBRIGATÓRIO"),
                    (col.unique, "ÚNICO"),
                )
                if active
            ]
            reference = ".".join(col.references) if col.references else "—"
            self.schema_tree.insert(
                "",
                "end",
                values=(
                    col.name,
                    col.type,
                    ", ".join(rules) or "ACEITA NULL",
                    format_cell(col.default),
                    reference,
                ),
                tags=("odd" if i % 2 else "even",),
            )
        for i, index in enumerate(info.indexes, start=len(info.columns)):
            rules = "ÍNDICE ÚNICO" if index.unique else "ÍNDICE HASH"
            self.schema_tree.insert(
                "",
                "end",
                values=(
                    index.name,
                    "ÍNDICE",
                    rules,
                    "AUTOMÁTICO" if index.automatic else "MANUAL",
                    index.column,
                ),
                tags=("odd" if i % 2 else "even",),
            )

    def query_selected_table(self, _event=None):
        if self._busy:
            return "break"
        name = self._selected_table()
        if name and self._keep_query():
            self.set_sql(self.session.table_query(name))
            self.run_query()
        return "break"

    def use_example(self, sql):
        if not self._busy and self._keep_query():
            self.set_sql(sql)
            self.editor.focus_set()
            self.status_var.set("Exemplo no editor. Ctrl+Enter executa no banco atual.")

    def run_query(self, _event=None):
        if self._busy:
            return "break"
        try:
            sql = self.editor.get("sel.first", "sel.last")
        except tk.TclError:
            sql = self.editor.get("1.0", "end-1c")
        if sql.strip():
            self.run_sql(sql)
        return "break"

    def run_sql(self, sql):
        if self._busy:
            return "break"
        self._busy = True
        self.status_var.set("Executando consulta…")
        for control in self._controls:
            control.configure(state="disabled")
        self.result_choice.configure(state="disabled")
        future = self._worker.submit(self.session.run, sql)
        future.add_done_callback(lambda item: self._mailbox.put(item))
        return "break"

    def _drain_mailbox(self):
        if self._closed:
            return
        try:
            future = self._mailbox.get_nowait()
        except queue.Empty:
            pass
        else:
            self._busy = False
            for control in self._controls:
                control.configure(state="normal")
            self.result_choice.configure(state="readonly")
            try:
                self._show_report(future.result())
            except Exception as error:
                self._show_error("Não foi possível concluir a consulta", error)
            self._refresh_catalog()
            self._refresh_history()
        self._poll_job = self.root.after(60, self._drain_mailbox)

    def _show_report(self, report):
        self._results = report.results
        self._result_index = max(0, len(self._results) - 1)
        choices = [f"Resultado {i + 1} de {len(self._results)}" for i in range(len(self._results))]
        self.result_choice.configure(values=choices)
        self._show_result()
        lines = []
        for i, result in enumerate(report.results, 1):
            count = len(result.rows) if result.columns else result.rowcount
            text = result.message or f"{count} linha(s), {len(result.columns)} coluna(s)"
            lines.append(f"{i:02d}  {text}")
        lines.append(f"\nTempo total: {report.elapsed_ms:.2f} ms")
        if report.error:
            lines.extend(("", f"{type(report.error).__name__}: {report.error}"))
            self._set_messages("\n".join(lines), error=True)
            self.notebook.select(self.messages_tab)
            self.status_var.set("Erro na consulta. Veja a mensagem; resultados anteriores foram preservados.")
        else:
            self._set_messages("\n".join(lines))
            self.notebook.select(self.data_tab)
            last = report.results[-1] if report.results else None
            if last and last.columns:
                self.status_var.set(
                    f"{len(last.rows)} linha(s)  ·  {len(last.columns)} coluna(s)  ·  "
                    f"{report.elapsed_ms:.2f} ms"
                )
            else:
                self.status_var.set(last.message if last and last.message else "Consulta concluída.")

    def _show_result(self):
        tree = self.result_tree
        tree.delete(*tree.get_children())
        self._displayed_rows = []
        self._selected_cell = (None, None)
        if not self._results:
            tree.configure(columns=())
            self.result_choice_var.set("Sem resultados")
            self.result_summary_var.set("Nenhum resultado disponível")
            self.empty_label.configure(text="Escreva SQL e pressione Ctrl+Enter para executar.")
            self.empty_label.place(relx=0.5, rely=0.45, anchor="center")
            return
        result = self._results[self._result_index]
        self.result_choice_var.set(f"Resultado {self._result_index + 1} de {len(self._results)}")
        columns = [f"col-{i}" for i in range(len(result.columns))]
        tree.configure(columns=columns)
        for i, (column, title) in enumerate(zip(columns, result.columns)):
            values = [len(str(title))] + [min(100, len(format_cell(row[i]))) for row in result.rows[:80]]
            width = max(105, min(340, max(values) * 8 + 26))
            tree.heading(column, text=title, anchor="w")
            tree.column(column, width=width, minwidth=80, stretch=True, anchor="w")
        # O resultado completo continua disponível no motor e na exportação.
        # Limitar widgets evita milhares de objetos Tcl congelando a janela.
        self._displayed_rows = result.rows[:5000]
        for i, row in enumerate(self._displayed_rows):
            tree.insert(
                "",
                "end",
                iid=f"row-{i}",
                values=tuple(format_cell(value) for value in row),
                tags=("odd" if i % 2 else "even",),
            )
        if result.columns:
            self.result_summary_var.set(
                f"{len(result.rows)} linha(s) · {len(result.columns)} coluna(s)"
                + (" · mostrando as primeiras 5.000" if len(result.rows) > 5000 else "")
            )
            if result.rows:
                self.empty_label.place_forget()
            else:
                self.empty_label.configure(text="Nenhuma linha corresponde à consulta.")
                self.empty_label.place(relx=0.5, rely=0.45, anchor="center")
        else:
            self.result_summary_var.set("Comando concluído")
            self.empty_label.configure(
                text=f"✓  {result.message or 'Comando concluído.'}\n\n"
                "Escreva outra consulta para continuar explorando."
            )
            self.empty_label.place(relx=0.5, rely=0.45, anchor="center")

    def _move_result(self, delta):
        if self._results and not self._busy:
            self._result_index = max(0, min(len(self._results) - 1, self._result_index + delta))
            self._show_result()

    def _result_selected(self, _event=None):
        index = self.result_choice.current()
        if 0 <= index < len(self._results):
            self._result_index = index
            self._show_result()

    def _select_cell(self, event):
        row = self.result_tree.identify_row(event.y)
        column = self.result_tree.identify_column(event.x)
        if row and column:
            self.result_tree.selection_set(row)
            self.result_tree.focus(row)
            self._selected_cell = (int(row.removeprefix("row-")), int(column.removeprefix("#")) - 1)

    def copy_result(self, _event=None):
        row, column = self._selected_cell
        if not self._results:
            return "break"
        selection = self.result_tree.selection()
        if selection:
            row = int(selection[0].removeprefix("row-"))
        if row is None:
            self.status_var.set("Selecione uma célula do resultado para copiar.")
            return "break"
        if column is None:
            column = 0
        result = self._results[self._result_index]
        if row < len(result.rows) and 0 <= column < len(result.columns):
            value = result.rows[row][column]
            text = value if isinstance(value, str) else format_cell(value)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_var.set("Célula copiada para a área de transferência.")
        return "break"

    def _inspect_cell(self, event):
        self._select_cell(event)
        row, column = self._selected_cell
        if row is not None and column is not None and self._results:
            result = self._results[self._result_index]
            if 0 <= column < len(result.columns):
                messagebox.showinfo(
                    result.columns[column], format_cell(result.rows[row][column]), parent=self.root
                )

    def _result_context(self, event):
        self._select_cell(event)
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Copiar célula", command=self.copy_result)
        menu.add_command(label="Exportar resultado CSV…", command=self.export_result)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            menu.destroy()

    def _refresh_history(self):
        self.history_tree.delete(*self.history_tree.get_children())
        self._history_entries.clear()
        for i, entry in enumerate(self.session.history):
            item = self.history_tree.insert(
                "",
                "end",
                iid=f"history-{i}",
                values=(
                    "OK" if entry.ok else "ERRO",
                    " ".join(entry.sql.split()),
                    entry.rows,
                    f"{entry.elapsed_ms:.2f} ms",
                ),
                tags=("odd" if i % 2 else "even",) + (() if entry.ok else ("error",)),
            )
            self._history_entries[item] = entry

    def _recover_history(self, _event=None):
        selected = self.history_tree.selection()
        if selected and not self._busy and self._keep_query():
            self.set_sql(self._history_entries[selected[0]].sql)
            self.editor.focus_set()
            self.status_var.set("Consulta recuperada. Ctrl+Enter executa novamente.")
        return "break"

    def _set_messages(self, text, error=False):
        self.messages.configure(state="normal")
        self.messages.delete("1.0", "end")
        self.messages.insert("1.0", text, "error" if error else ())
        self.messages.configure(state="disabled")

    def _show_error(self, title, error):
        self._set_messages(f"{title}\n\n{error}", error=True)
        self.notebook.select(self.messages_tab)
        self.status_var.set(title)

    def _keep_query(self):
        if self.editor.get("1.0", "end-1c") == self._saved_sql:
            return True
        choice = messagebox.askyesnocancel(
            "Consulta não salva", "Deseja salvar o texto da consulta antes de continuar?", parent=self.root
        )
        if choice is None:
            return False
        return self.save_query() if choice else True

    def _keep_connection(self):
        if self._busy:
            self.status_var.set("Aguarde a consulta terminar antes de trocar ou fechar o banco.")
            return False
        if not self._keep_query():
            return False
        if self.session.in_transaction:
            choice = messagebox.askyesnocancel(
                "Transação aberta",
                "Deseja confirmar as alterações antes de continuar?\n\n"
                "Sim: COMMIT. Não: ROLLBACK. Cancelar: continuar nesta conexão.",
                parent=self.root,
            )
            if choice is None:
                return False
            report = self.session.commit() if choice else self.session.rollback()
            if report.error:
                self._show_report(report)
                return False
        if self.session.is_memory and self.session.dirty:
            choice = messagebox.askyesnocancel(
                "Banco em memória",
                "Deseja salvar este banco em um arquivo .tatu antes de continuar?",
                parent=self.root,
            )
            if choice is None:
                return False
            if choice and not self.save_database():
                return False
        return True

    def _connection_changed(self, sql=EMPTY_QUERY):
        self._results = []
        self._result_index = 0
        self.set_sql(sql)
        self._show_result()
        self._set_messages("Conexão pronta. As alterações confirmadas em arquivos são gravadas no disco.")
        self._refresh_catalog()
        self._refresh_history()
        self.notebook.select(self.data_tab)
        self.status_var.set("Banco conectado. Escreva SQL ou escolha uma tabela na lateral.")

    def new_database(self, _event=None):
        if not self._keep_connection():
            return "break"
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Criar banco Tatu DB",
            defaultextension=".tatu",
            initialfile="meu-banco.tatu",
            confirmoverwrite=False,
            filetypes=(("Banco Tatu DB", "*.tatu"), ("Todos os arquivos", "*")),
        )
        if path:
            try:
                self.session.new(path)
                self._connection_changed()
            except (TatuError, OSError, ValueError) as error:
                self._show_error("Não foi possível criar o banco", error)
        return "break"

    def open_database(self, _event=None):
        if not self._keep_connection():
            return "break"
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Abrir banco Tatu DB",
            filetypes=(("Banco Tatu DB", "*.tatu"), ("Todos os arquivos", "*")),
        )
        if path:
            try:
                self.session.open(path)
                self._connection_changed()
            except (TatuError, OSError, ValueError) as error:
                self._show_error("Não foi possível abrir o banco", error)
        return "break"

    def save_database(self, _event=None):
        if self._busy:
            return False
        if self.session.in_transaction:
            messagebox.showinfo(
                "Transação aberta", "Confirme ou desfaça a transação antes de salvar como.", parent=self.root
            )
            return False
        initial = Path(self.session.path).name if self.session.path else "laboratorio.tatu"
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Salvar banco como",
            defaultextension=".tatu",
            initialfile=initial,
            confirmoverwrite=False,
            filetypes=(("Banco Tatu DB", "*.tatu"), ("Todos os arquivos", "*")),
        )
        if not path:
            return False
        overwrite = False
        if Path(path).exists():
            overwrite = messagebox.askyesno(
                "Substituir banco?",
                f"Substituir o banco existente?\n\n{path}",
                parent=self.root,
                default="no",
            )
            if not overwrite:
                return False
        try:
            self.session.save_as(path, overwrite=overwrite)
        except (TatuError, OSError, ValueError) as error:
            self._show_error("Não foi possível salvar o banco", error)
            return False
        self._refresh_catalog()
        self.status_var.set(f"Banco salvo no disco: {path}")
        return True

    def new_demo(self):
        if self._keep_connection():
            try:
                self.session.load_demo()
                self._connection_changed(FIRST_QUERY)
                self.run_query()
            except (TatuError, OSError, ValueError) as error:
                self._show_error("Não foi possível preparar os exemplos", error)

    def load_query(self, _event=None):
        if self._busy or not self._keep_query():
            return "break"
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Abrir consulta SQL",
            filetypes=(("Consulta SQL", "*.sql"), ("Todos os arquivos", "*")),
        )
        if path:
            try:
                self.set_sql(read_sql(path), path)
                self.status_var.set(f"Consulta aberta: {path}")
            except (TatuError, OSError, UnicodeError, ValueError) as error:
                self._show_error("Não foi possível abrir a consulta", error)
        return "break"

    def save_query(self, _event=None, *, save_as=False):
        path = self.query_path
        if save_as or path is None:
            selected = filedialog.asksaveasfilename(
                parent=self.root,
                title="Salvar consulta SQL",
                defaultextension=".sql",
                initialfile=path.name if path else "consulta.sql",
                filetypes=(("Consulta SQL", "*.sql"), ("Todos os arquivos", "*")),
            )
            if not selected:
                return False
            path = Path(selected)
        sql = self.editor.get("1.0", "end-1c")
        try:
            write_sql(path, sql)
        except (TatuError, OSError, UnicodeError, ValueError) as error:
            self._show_error("Não foi possível salvar a consulta", error)
            return False
        self.query_path = path
        self._saved_sql = sql
        self._update_title()
        self.status_var.set(f"Consulta salva: {path}")
        return True

    def export_result(self):
        if self._busy or not self._results or not self._results[self._result_index].columns:
            self.status_var.set("Execute uma consulta com colunas antes de exportar.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Exportar resultado CSV",
            defaultextension=".csv",
            initialfile="resultado.csv",
            filetypes=(("Arquivo CSV", "*.csv"),),
        )
        if path:
            try:
                export_csv(path, self._results[self._result_index])
                self.status_var.set(f"Resultado completo exportado: {path}")
            except (TatuError, OSError, UnicodeError, ValueError) as error:
                self._show_error("Não foi possível exportar o resultado", error)

    def about(self):
        messagebox.showinfo(
            "Sobre a Toca",
            "Toca · seu banco, por dentro.\n\n"
            "Cliente gráfico próprio do Tatu DB, em Python e Tkinter.\n"
            "Editor SQL, catálogo, resultados e transações em uma bancada didática.\n\n"
            "Bancos .tatu são gravados no disco deste computador.\n"
            "O motor continua educacional e deve ser usado por um escritor de cada vez.",
            parent=self.root,
        )

    def close(self):
        if self._closed or not self._keep_connection():
            return
        self._closed = True
        for job in (self._poll_job, self._startup_job, self._highlight_job):
            if job is not None:
                self.root.after_cancel(job)
        self._worker.shutdown(wait=False, cancel_futures=True)
        self.session.close()
        self.root.destroy()


def main(argv=None):
    """Entrada de ``toca`` ou ``python -m tatu.toca [banco.tatu]``."""
    parser = argparse.ArgumentParser(description="Toca: cliente gráfico do Tatu DB.")
    parser.add_argument("arquivo", nargs="?", help="arquivo .tatu para abrir ou criar")
    parser.add_argument("--demo", action="store_true", help="começa no laboratório de demonstração")
    args = parser.parse_args(argv)
    if args.arquivo and args.demo:
        parser.error("escolha um arquivo ou --demo")
    if tk is None:
        print(
            "A Toca precisa de Tkinter. No Linux, instale o pacote python3-tk da sua distribuição.\n"
            "No Windows/macOS, use uma instalação do Python com Tcl/Tk.",
            file=sys.stderr,
        )
        return 2
    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f"Não foi possível abrir a interface gráfica: {error}", file=sys.stderr)
        return 2
    try:
        session = Session(demo=not args.arquivo)
        if args.arquivo:
            if Path(args.arquivo).exists():
                session.open(args.arquivo)
            else:
                session.new(args.arquivo)
    except (TatuError, OSError, ValueError) as error:
        messagebox.showerror("Abrir Tatu DB", str(error), parent=root)
        root.destroy()
        return 1
    TocaApp(root, session)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
