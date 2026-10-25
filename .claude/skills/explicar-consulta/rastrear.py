"""
🔬 Rastreia uma consulta pelo Tatu DB: tokens → AST → plano → resultado.

    python .claude/skills/explicar-consulta/rastrear.py "SELECT apelido FROM tatus WHERE idade > 3"
    python .claude/skills/explicar-consulta/rastrear.py --sem-demo "SELECT 1 + 2 * 3"
"""

import argparse
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import tatu  # noqa: E402
from tatu.demo import DEMO_SQL  # noqa: E402
from tatu.nodes import Node, Select  # noqa: E402
from tatu.parser import parse  # noqa: E402
from tatu.tokenizer import tokenize  # noqa: E402


def tree(value, indent: str = "") -> list[str]:
    """Desenha a AST com indentação, mostrando só os campos preenchidos."""
    if isinstance(value, Node) and is_dataclass(value):
        lines = [f"{type(value).__name__}"]
        for f in fields(value):
            child = getattr(value, f.name)
            if child in (None, (), False):
                continue
            sub = tree(child, indent + "    ")
            lines.append(f"{indent}  {f.name}: {sub[0]}")
            lines.extend(sub[1:])
        return lines
    if isinstance(value, tuple):
        if not value:
            return ["()"]
        lines = [f"[{len(value)} item(ns)]"]
        for item in value:
            sub = tree(item, indent + "    ")
            lines.append(f"{indent}  - {sub[0]}")
            lines.extend(sub[1:])
        return lines
    return [repr(value)]


def section(title: str) -> None:
    print(f"\n{'═' * 70}\n{title}\n{'═' * 70}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sql", help="a consulta a rastrear")
    parser.add_argument("--sem-demo", action="store_true", help="não carrega os dados de exemplo")
    args = parser.parse_args()

    db = tatu.connect()
    if not args.sem_demo:
        db.executescript(DEMO_SQL)

    section("1. 🔤 TOKENIZER (tatu/tokenizer.py) — texto → tokens")
    try:
        tokens = tokenize(args.sql)
    except tatu.TatuError as error:
        print(f"Erro já no tokenizer:\n{error}")
        return 1
    for token in tokens:
        print(f"  {token.kind:<8} {token.value!r:<30} (posição {token.pos})")

    section("2. 🌳 PARSER (tatu/parser.py + nodes.py) — tokens → árvore (AST)")
    try:
        statements = parse(args.sql)
    except tatu.TatuError as error:
        print(f"Erro de sintaxe:\n{error}")
        return 1
    for stmt in statements:
        print("\n".join(tree(stmt)))

    for stmt in statements:
        if isinstance(stmt, Select):
            section("3. 🧭 PLANEJADOR (tatu/planner.py) — AST → plano (leia de baixo para cima)")
            try:
                print(db.execute("EXPLAIN " + args.sql.strip().rstrip(";")))
            except tatu.TatuError as error:
                print(f"Erro ao planejar:\n{error}")
                return 1

    section("4. 📋 RESULTADO")
    try:
        for result in db.executescript(args.sql):
            print(result)
    except tatu.TatuError as error:
        print(f"{type(error).__name__}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
