"""
🔖 Monta as notas de uma versão a partir do CHANGELOG.md (usado pelo workflow de release).

    python scripts/release_notes.py 0.1.0
    python scripts/release_notes.py 0.1.0 --assets dist    # + tabela de downloads

Com ``--assets``, olha os arquivos da pasta e acrescenta uma tabela com o link
de download de cada instalador, por sistema.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
REPO = "https://github.com/AlefRP/tatu_db"
RAW = "https://raw.githubusercontent.com/AlefRP/tatu_db/main"

# (sistema, [(rótulo, arquivo)] dos instaladores, [(rótulo, arquivo)] dos portáteis)
PLATFORMS = [
    ("🪟 Windows (x64)", [("setup.exe", "tatu-windows-x86_64-setup.exe")],
     [(".zip", "tatu-windows-x86_64.zip")]),
    ("🍎 macOS (Apple Silicon)", [(".pkg", "tatu-macos-arm64.pkg")],
     [(".tar.gz", "tatu-macos-arm64.tar.gz")]),
    ("🍎 macOS (Intel)", [(".pkg", "tatu-macos-x86_64.pkg")],
     [(".tar.gz", "tatu-macos-x86_64.tar.gz")]),
    ("🐧 Linux (x64)", [(".deb", "tatu-linux-x86_64.deb"), (".rpm", "tatu-linux-x86_64.rpm")],
     [(".tar.gz", "tatu-linux-x86_64.tar.gz")]),
    ("🐧 Linux (ARM64)", [(".deb", "tatu-linux-arm64.deb"), (".rpm", "tatu-linux-arm64.rpm")],
     [(".tar.gz", "tatu-linux-arm64.tar.gz")]),
]


def notes_for(version: str) -> str | None:
    text = CHANGELOG.read_text(encoding="utf-8")
    pattern = rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else None


def downloads_table(version: str, folder: Path) -> str:
    present = {path.name for path in folder.iterdir()} if folder.is_dir() else set()
    base = f"{REPO}/releases/download/v{version}"

    def links(items):
        return " · ".join(f"[{label}]({base}/{name})" for label, name in items if name in present) or "—"

    rows = [f"| {system} | {links(installers)} | {links(portables)} |"
            for system, installers, portables in PLATFORMS
            if any(name in present for _, name in installers + portables)]
    lines = [
        "## 📦 Downloads",
        "",
        "| Sistema | Instalador | Portátil (sem instalar) |",
        "|---|---|---|",
        *rows,
    ]
    wheels = sorted(name for name in present if name.endswith(".whl"))
    if wheels:
        lines += ["", f"🐍 **Python:** [{wheels[0]}]({base}/{wheels[0]}) — `pip install {wheels[0]}`"]
    lines += [
        "",
        "**Em uma linha** (usa o seu Python, se houver; senão, baixa o executável pronto):",
        "",
        "```powershell",
        f"irm {RAW}/scripts/install.ps1 | iex          # Windows",
        "```",
        "",
        "```bash",
        f"curl -fsSL {RAW}/scripts/install.sh | sh     # macOS e Linux",
        "```",
    ]
    if "SHA256SUMS.txt" in present:
        lines += ["", "🔐 Confira a integridade dos downloads com o "
                      f"[SHA256SUMS.txt]({base}/SHA256SUMS.txt)."]
    lines += ["", "> Os instaladores não são assinados: na primeira vez, o Windows e o macOS vão pedir uma "
              f"confirmação. Veja o [guia de instalação]({REPO}/blob/main/docs/instalacao.md)."]
    return "\n".join(lines)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("versao")
    parser.add_argument("--assets", type=Path, help="pasta com os arquivos que serão publicados")
    args = parser.parse_args()

    version = args.versao.removeprefix("v")
    notes = notes_for(version)
    if notes is None:
        print(f"CHANGELOG.md não tem a seção ## [{version}]", file=sys.stderr)
        return 1
    print(notes)
    if args.assets:
        print("\n" + downloads_table(version, args.assets))
    else:
        guide = f"{REPO}/blob/main/docs/instalacao.md"
        print(f"\n---\n📦 **Como instalar:** veja o [guia de instalação]({guide}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
