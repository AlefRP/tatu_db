"""
🪝 Hook do Claude Code: roda os testes sempre que um .py do banco ou dos testes é editado.

Recebe o evento PostToolUse em JSON pela entrada padrão. Se os testes falharem, sai com
código 2: o Claude Code mostra a saída para o Claude, que corrige na hora.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def edited_file() -> Path | None:
    try:
        event = json.load(sys.stdin)
    except ValueError:  # JSON inválido (json.JSONDecodeError é um ValueError)
        return None
    path = (event.get("tool_input") or {}).get("file_path")
    return Path(path) if path else None


def main() -> int:
    path = edited_file()
    if path is None or path.suffix != ".py":
        return 0
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        return 0  # arquivo fora do repositório
    if relative.parts[0] not in ("tatu", "tests"):
        return 0

    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    if result.returncode == 0:
        return 0
    output = (result.stdout + result.stderr).strip().splitlines()
    print(f"🧪 Os testes falharam depois de editar {relative}:", file=sys.stderr)
    print("\n".join(output[-40:]), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
