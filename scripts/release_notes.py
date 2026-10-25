"""
🔖 Extrai do CHANGELOG.md as notas de uma versão (usado pelo workflow de release).

    python scripts/release_notes.py 0.1.0
"""

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def notes_for(version: str) -> str | None:
    text = CHANGELOG.read_text(encoding="utf-8")
    pattern = rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else None


def main() -> int:
    if len(sys.argv) != 2:
        print("uso: python scripts/release_notes.py <versão>", file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    version = sys.argv[1].removeprefix("v")
    notes = notes_for(version)
    if notes is None:
        print(f"CHANGELOG.md não tem a seção ## [{version}]", file=sys.stderr)
        return 1
    print(notes)
    print("\n---\n📦 **Como instalar:** veja [docs/instalacao.md]"
          "(https://github.com/AlefRP/tatu_db/blob/main/docs/instalacao.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
