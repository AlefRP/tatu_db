"""
🔖 Sobe a versão do Tatu DB e fecha a seção "Não lançado" do CHANGELOG.

Usado pelo workflow "Nova versão" (.github/workflows/versao.yml), mas roda em
qualquer lugar:

    python scripts/bump_version.py --tipo patch              # 0.1.0 → 0.1.1
    python scripts/bump_version.py --tipo minor              # 0.1.0 → 0.2.0
    python scripts/bump_version.py --versao 1.0.0            # versão exata
    python scripts/bump_version.py --tipo patch --dry-run    # só mostra o que faria

Se "## [Não lançado]" estiver vazio, as notas são montadas a partir dos commits
desde a última tag, agrupados pelo prefixo (Conventional Commits: feat:, fix:...).

Na saída padrão imprime ``versao=X.Y.Z`` e ``tag=vX.Y.Z`` — o formato que o
GitHub Actions espera em $GITHUB_OUTPUT. O resto vai para a saída de erro.
"""

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "tatu" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
REPO = "https://github.com/AlefRP/tatu_db"
VERSION_LINE = re.compile(r'^__version__ = "(\d+)\.(\d+)\.(\d+)"$', re.MULTILINE)
UNRELEASED = re.compile(r"^## \[Não lançado\][^\n]*\n(.*?)(?=^## \[|^\[Não lançado\]:|\Z)",
                        re.MULTILINE | re.DOTALL)

# prefixo do commit → título da seção nas notas (na ordem em que aparecem)
SECTIONS = [
    ("feat", "✨ Novidades"),
    ("fix", "🐛 Correções"),
    ("perf", "⚡ Desempenho"),
    ("refactor", "🔧 Por dentro"),
    ("docs", "📚 Documentação"),
    ("test", "🧪 Testes"),
    ("build", "📦 Pacotes e instaladores"),
    ("ci", "🤖 Automação"),
]


def log(message: str) -> None:
    print(message, file=sys.stderr)


def current_version() -> tuple[int, int, int]:
    match = VERSION_LINE.search(INIT.read_text(encoding="utf-8"))
    if not match:
        sys.exit("Não achei a linha __version__ = \"X.Y.Z\" em tatu/__init__.py")
    return tuple(int(part) for part in match.groups())


def next_version(current: tuple[int, int, int], kind: str) -> str:
    major, minor, patch = current
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip() if result.returncode == 0 else ""


def notes_from_commits() -> str:
    """Monta as notas a partir dos assuntos dos commits desde a última tag."""
    last_tag = git("describe", "--tags", "--abbrev=0", "--match", "v*")
    log(f"Última tag: {last_tag or '(nenhuma)'}")
    subjects = git("log", "--format=%s", f"{last_tag}..HEAD" if last_tag else "HEAD").splitlines()
    titles = dict(SECTIONS)
    groups: dict[str, list[str]] = {}
    for subject in subjects:
        match = re.match(r"^(\w+)(?:\([^)]*\))?(!)?:\s*(.+)$", subject)
        if not match or match.group(1) not in titles:
            continue  # chore:, merges e mensagens fora do padrão ficam de fora
        kind, breaking, text = match.groups()
        item = text[0].upper() + text[1:]
        if breaking:
            item += " — ⚠️ **muda o comportamento antigo**"
        groups.setdefault(titles[kind], []).append(item)
    return "\n\n".join(
        f"### {title}\n\n" + "\n".join(f"- {item}" for item in groups[title])
        for _, title in SECTIONS if title in groups
    )


def close_changelog(text: str, version: str, today: str, generated: str) -> str:
    match = UNRELEASED.search(text)
    if not match:
        sys.exit("O CHANGELOG.md não tem a seção ## [Não lançado]")
    body = match.group(1).strip() or generated
    if not body:
        sys.exit("Nada para lançar: a seção ## [Não lançado] está vazia e não há commits "
                 "feat:/fix:/docs:... desde a última tag.")
    new_sections = f"## [Não lançado]\n\n## [{version}] - {today}\n\n{body}\n\n"
    text = text[:match.start()] + new_sections + text[match.end():]
    footer = (f"[Não lançado]: {REPO}/compare/v{version}...HEAD\n"
              f"[{version}]: {REPO}/releases/tag/v{version}")
    if re.search(r"^\[Não lançado\]: .*$", text, re.MULTILINE):
        text = re.sub(r"^\[Não lançado\]: .*$", lambda _: footer, text, count=1, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + "\n\n" + footer + "\n"
    return text


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tipo", choices=["patch", "minor", "major"], default="patch")
    parser.add_argument("--versao", default="", help="versão exata (X.Y.Z); tem prioridade sobre --tipo")
    parser.add_argument("--dry-run", action="store_true", help="mostra o resultado sem gravar nada")
    args = parser.parse_args()

    current = current_version()
    version = args.versao.strip().removeprefix("v") or next_version(current, args.tipo)
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit(f"Versão inválida: {version!r} (use o formato X.Y.Z)")
    if tuple(int(p) for p in version.split(".")) <= current:
        sys.exit(f"A versão nova ({version}) precisa ser maior que a atual ({'.'.join(map(str, current))})")
    if git("tag", "--list", f"v{version}"):
        sys.exit(f"A tag v{version} já existe")

    today = datetime.date.today().isoformat()
    changelog = CHANGELOG.read_text(encoding="utf-8")
    try:
        new_changelog = close_changelog(changelog, version, today, notes_from_commits())
    except SystemExit as error:
        if not args.dry_run:
            raise
        log(f"(aviso no dry-run) {error}")
        new_changelog = changelog

    log(f"Versão: {'.'.join(map(str, current))} → {version}")
    if args.dry_run:
        section = UNRELEASED.search(new_changelog)
        after = new_changelog[section.end():] if section else ""
        log("── CHANGELOG (prévia) ──\n" + after.split("\n## [", 1)[0][:2000])
    else:
        INIT.write_text(VERSION_LINE.sub(f'__version__ = "{version}"', INIT.read_text(encoding="utf-8")),
                        encoding="utf-8", newline="\n")
        CHANGELOG.write_text(new_changelog, encoding="utf-8", newline="\n")
        log("✔ tatu/__init__.py e CHANGELOG.md atualizados")

    print(f"versao={version}")
    print(f"tag=v{version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
