"""
🖥️ O shell interativo do Tatu DB.

    python -m tatu                          # banco só na memória
    python -m tatu zoo.tatu                 # abre (ou cria) um arquivo
    python -m tatu zoo.tatu -c "SELECT 1"   # roda um comando e sai
    python -m tatu zoo.tatu < script.sql    # roda um script
"""

import argparse
import os
import sys
import time

from . import __version__
from .database import Database
from .demo import DEMO_QUERIES, DEMO_SQL
from .errors import (
    CatalogError,
    ConstraintError,
    ExecutionError,
    TatuError,
    TatuSyntaxError,
    TatuTypeError,
    TransactionError,
)
from .result import Result, format_table
from .tokenizer import tokenize

ARMADILLO = r"""
                 _.-''''''''-._
            _.-''  |  |  |  |  ''-._      __
         .-'   |   |  |  |  |   |   '-.  / /
       .'   |  |   |  |  |  |   |  |   './ /____
      (_____|__|___|__|__|__|___|__|_____)  o   ''-._
  ~~~~~   \__\  \__\          /__/  /__/ '-._______.-'
"""

ERROR_LABELS = [
    (TatuSyntaxError, "Erro de sintaxe"),
    (CatalogError, "Erro de catálogo"),
    (ConstraintError, "Restrição violada"),
    (TatuTypeError, "Erro de tipo"),
    (ExecutionError, "Erro de execução"),
    (TransactionError, "Erro de transação"),
    (TatuError, "Erro"),
]

HELP = """
  Comandos do shell (começam com ponto):

    .help             mostra esta ajuda
    .tables           lista as tabelas
    .schema [tabela]  mostra o CREATE TABLE (de todas ou de uma)
    .demo             carrega dados de exemplo (espécies de tatu 🌵)
    .read ARQUIVO     executa um arquivo .sql
    .quit             sai (Ctrl+D ou Ctrl+Z também)

  SQL: termine cada comando com ; — ele pode ocupar várias linhas.
  Experimente:  EXPLAIN SELECT * FROM tatus WHERE id = 1;
"""

STYLES = {"bold": "1", "dim": "2", "italic": "3", "red": "31", "green": "32",
          "yellow": "33", "cyan": "36", "brown": "38;5;137", "sand": "38;5;180"}


class Paint:
    """Pinta texto com cores ANSI (ou não faz nada, se o terminal não suporta)."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def __call__(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        return f"\033[{';'.join(STYLES[s] for s in styles)}m{text}\033[0m"


class Shell:
    def __init__(self, db: Database, paint: Paint, unicode: bool, out=None):
        self.db = db
        self.paint = paint
        self.unicode = unicode
        self.out = out or sys.stdout
        self.buffer: list[str] = []
        self.failures = 0

    def say(self, text: str = "") -> None:
        print(text, file=self.out)

    # ─────────────────────────── laço principal ───────────────────────────

    def interactive(self) -> None:
        self.banner()
        self.buffer = []  # linhas de um comando que ainda não terminou
        while True:
            try:
                line = input(self.paint("  ..> " if self.buffer else "tatu> ", "sand", "bold"))
            except EOFError:
                self.say()
                break
            except KeyboardInterrupt:  # Ctrl+C descarta o comando pela metade
                self.say(self.paint("  (comando descartado)", "dim"))
                self.buffer.clear()
                continue
            if not self.feed(line):
                break
        self.goodbye()

    def script(self, lines) -> bool:
        """Modo não interativo (pipe). Devolve False se algum comando falhou."""
        self.buffer = []
        self.failures = 0
        for line in lines:
            if not self.feed(line.rstrip("\n")):
                break
        if self.buffer:
            self.run_sql("\n".join(self.buffer))  # último comando sem ';'
        self.db.close()
        return self.failures == 0

    def feed(self, line: str) -> bool:
        """Recebe uma linha digitada. Devolve False quando é hora de sair."""
        if not self.buffer and line.lstrip().startswith("."):
            return self.meta(line.strip())
        if self.buffer or line.strip():
            self.buffer.append(line)
        if self.buffer and is_complete("\n".join(self.buffer)):
            self.run_sql("\n".join(self.buffer))
            self.buffer.clear()
        return True

    def run_sql(self, sql: str) -> bool:
        """Executa e mostra cada resultado. Devolve False se deu erro."""
        try:
            start = time.perf_counter()
            for result in self.db.iterscript(sql):
                elapsed = time.perf_counter() - start
                self.show(result, elapsed)
                start = time.perf_counter()
        except TatuError as error:
            self.show_error(error)
            self.failures += 1
            return False
        return True

    # ─────────────────────────── exibição ───────────────────────────

    def banner(self) -> None:
        self.say(self.paint(ARMADILLO.rstrip("\n"), "brown"))
        title = self.paint(f"  Tatu DB {__version__}", "bold", "sand")
        tagline = self.paint("— um banco de dados relacional feito do zero, para aprender.", "dim")
        self.say(f"{title} {tagline}")
        where = self.db.path or "em memória (nada será gravado)"
        self.say(self.paint(f"  Banco: {where}", "dim"))
        self.say(self.paint("  Digite .help para ajuda ou .demo para carregar dados de exemplo.", "dim"))
        self.say()

    def show(self, result: Result, elapsed: float) -> None:
        timing = self.paint(f"({elapsed * 1000:.2f} ms)", "dim")
        if result.columns:
            self.say(format_table(result.columns, result.rows, self.unicode, self.paint))
            count = len(result.rows)
            self.say(self.paint(f"{count} linha{'s' if count != 1 else ''} ", "dim") + timing)
        else:
            check = "✔" if self.unicode else "OK"
            self.say(f"{self.paint(check, 'green', 'bold')} {result.message} {timing}")

    def show_error(self, error: TatuError) -> None:
        label = next(text for cls, text in ERROR_LABELS if isinstance(error, cls))
        cross = "✖" if self.unicode else "X"
        lines = str(error).split("\n")
        self.say(f"{self.paint(cross + ' ' + label + ':', 'red', 'bold')} {lines[0]}")
        for line in lines[1:]:
            self.say(self.paint(line, "yellow"))

    def goodbye(self) -> None:
        if self.db.in_transaction:
            self.say(self.paint("  Havia uma transação aberta — ela foi desfeita (ROLLBACK).", "yellow"))
        self.db.close()
        paw = " 🐾" if self.unicode else ""
        self.say(self.paint(f"  Até mais! O tatu voltou para a toca.{paw}", "sand"))

    # ─────────────────────────── comandos com ponto ───────────────────────────

    def meta(self, line: str) -> bool:
        """Executa um comando do shell. Devolve False para sair."""
        command, _, argument = line.partition(" ")
        argument = argument.strip()
        if command in (".quit", ".exit", ".q"):
            return False
        if command == ".help":
            self.say(HELP)
        elif command == ".tables":
            self.show_tables()
        elif command == ".schema":
            self.show_schema(argument or None)
        elif command == ".demo":
            self.load_demo()
        elif command == ".read":
            self.read_file(argument)
        else:
            self.say(self.paint(f"Comando desconhecido: {command} — digite .help", "yellow"))
        return True

    def show_tables(self) -> None:
        names = self.db.tables()
        if not names:
            self.say(self.paint("  Nenhuma tabela ainda. Que tal um CREATE TABLE? (ou .demo)", "dim"))
            return
        rows = []
        for name in names:
            table = self.db.storage.get_table(name)
            rows.append((name, len(table.schema.columns), len(table.rows)))
        self.say(format_table(["tabela", "colunas", "linhas"], rows, self.unicode, self.paint))

    def show_schema(self, name: str | None) -> None:
        try:
            names = [name] if name else self.db.tables()
            for table_name in names:
                table = self.db.storage.get_table(table_name)
                self.say(self.paint(table.schema.to_sql(), "cyan"))
                for index in table.indexes.values():
                    if not index.automatic:
                        unique = "UNIQUE " if index.unique else ""
                        self.say(self.paint(
                            f"CREATE {unique}INDEX {index.name} ON {table_name} ({index.column});", "cyan"))
        except TatuError as error:
            self.show_error(error)

    def load_demo(self) -> None:
        if self.run_sql_quietly(DEMO_SQL):
            self.say(f"{self.paint('🌵 Pronto!' if self.unicode else 'Pronto!', 'green', 'bold')} "
                     "Tabelas criadas: especies, tatus, avistamentos. Experimente:")
            for query in DEMO_QUERIES:
                self.say(self.paint(f"    {query}", "cyan"))

    def run_sql_quietly(self, sql: str) -> bool:
        try:
            self.db.executescript(sql)
            return True
        except TatuError as error:
            self.show_error(error)
            return False

    def read_file(self, path: str) -> None:
        if not path:
            self.say(self.paint("Uso: .read arquivo.sql", "yellow"))
            return
        try:
            with open(path, encoding="utf-8") as f:
                sql = f.read()
        except OSError as error:
            self.say(self.paint(f"Não consegui abrir '{path}': {error.strerror}", "red"))
            return
        self.run_sql(sql)


def is_complete(sql: str) -> bool:
    """O comando acabou? (termina com ';' fora de um texto entre aspas)."""
    try:
        tokens = tokenize(sql)
    except TatuSyntaxError as error:
        # aspas abertas: o usuário ainda está digitando o texto
        return "sem aspa" not in error.message
    meaningful = [t for t in tokens if t.kind != "EOF"]
    return bool(meaningful) and meaningful[-1].kind == "SYMBOL" and meaningful[-1].value == ";"


# ─────────────────────────── terminal ───────────────────────────

def _enable_windows_ansi() -> bool:
    """No Windows, liga o modo de cores ANSI do console."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))  # VIRTUAL_TERMINAL_PROCESSING
    except (AttributeError, OSError):
        return False


def _supports_color(stream) -> bool:
    if os.environ.get("NO_COLOR") or not hasattr(stream, "isatty") or not stream.isatty():
        return False
    return _enable_windows_ansi() if os.name == "nt" else True


def _supports_unicode(stream) -> bool:
    try:
        "╭─│✔🐾".encode(stream.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="tatu", description="Tatu DB — um banco de dados relacional feito do zero, para aprender.")
    parser.add_argument("arquivo", nargs="?",
                        help="arquivo do banco (.tatu); sem ele, o banco fica na memória")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-c", "--comando", help="executa este SQL e sai")
    mode.add_argument("--gui", action="store_true", help="abre o cliente gráfico Toca")
    parser.add_argument("--version", action="version", version=f"Tatu DB {__version__}")
    args = parser.parse_args(argv)

    if args.gui:
        from .toca import main as gui_main
        return gui_main([args.arquivo] if args.arquivo else [])

    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    try:
        db = Database(args.arquivo)
    except TatuError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    shell = Shell(db, Paint(_supports_color(sys.stdout)), _supports_unicode(sys.stdout))
    if args.comando is not None:
        ok = shell.run_sql(args.comando)
        db.close()
        return 0 if ok else 1
    if not sys.stdin.isatty():  # script vindo de um "pipe": python -m tatu < script.sql
        return 0 if shell.script(sys.stdin) else 1

    try:
        import readline  # noqa: F401 — histórico com as setas (Linux/macOS)
    except ImportError:
        pass
    shell.interactive()
    return 0
