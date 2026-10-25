"""
📚 Confere a documentação — roda no CI e antes de cada commit que mexa em docs.

    python scripts/check_docs.py

Verifica:
  • links relativos em Markdown e HTML (`[texto](caminho)`, `src="..."`, `href="..."`);
  • âncoras (`arquivo.md#titulo`), usando o mesmo algoritmo do GitHub;
  • se cada SVG em docs/ e packaging/ é XML válido;
  • se o número de testes citado no README bate com o número real.
"""

import re
import sys
import unicodedata
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "build", "dist", ".venv", "venv", "__pycache__", "node_modules"}

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|!\[[^\]]*\]\(([^)\s]+)\)")
HTML_ATTR = re.compile(r"""(?:src|href)=["']([^"']+)["']""")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


def markdown_files():
    for path in sorted(ROOT.rglob("*.md")):
        if not SKIP_DIRS.intersection(path.relative_to(ROOT).parts):
            yield path


def _is_word_char(ch: str) -> bool:
    # O GitHub mantém o que o Ruby chama de \p{Word}: letras, marcas, dígitos e "_".
    # Atenção: "marcas" inclui o seletor invisível U+FE0F que vem depois de emojis
    # como 🗣️ — ele SOBREVIVE na âncora, ao contrário do \w do Python.
    category = unicodedata.category(ch)
    return category[0] in "LM" or category in ("Nd", "Nl", "Pc")


def github_slug(text: str) -> str:
    """Como o GitHub transforma um título em âncora: '## 🚀 Começando' → '-começando'."""
    text = re.sub(r"`([^`]*)`", r"\1", text)                 # tira a crase de `código`
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)      # [link](url) → link
    text = re.sub(r"<[^>]+>", "", text)                       # tags HTML
    kept = "".join(ch for ch in text.lower() if ch in "- " or _is_word_char(ch))
    return kept.replace(" ", "-")


def outside_code(lines):
    """Linhas fora de blocos de código (onde links e títulos valem).

    Um bloco aberto com ``` só fecha com ``` (e ~~~ com ~~~) — senão o rabo
    do tatu em ASCII (~~~~~) fecharia o bloco antes da hora!
    """
    opened_with = None
    for number, line in enumerate(lines, 1):
        fence = FENCE.match(line)
        if fence:
            if opened_with is None:
                opened_with = fence.group(1)
                continue
            if fence.group(1) == opened_with:
                opened_with = None
                continue
        if opened_with is None:
            yield number, re.sub(r"`[^`]*`", "", line)  # ignora `código em linha`


_anchor_cache: dict[Path, set[str]] = {}


def anchors_of(path: Path) -> set[str]:
    if path not in _anchor_cache:
        slugs, seen = set(), {}
        for _, line in outside_code(path.read_text(encoding="utf-8").splitlines()):
            match = HEADING.match(line)
            if match:
                slug = github_slug(match.group(2))
                count = seen.get(slug, 0)
                seen[slug] = count + 1
                slugs.add(slug if count == 0 else f"{slug}-{count}")
        _anchor_cache[path] = slugs
    return _anchor_cache[path]


def check_links(problems: list[str]) -> int:
    checked = 0
    for md in markdown_files():
        lines = md.read_text(encoding="utf-8").splitlines()
        for number, line in outside_code(lines):
            targets = [a or b for a, b in LINK.findall(line)] + HTML_ATTR.findall(line)
            for target in targets:
                if re.match(r"^[a-z][a-z0-9+.-]*:", target):  # http:, https:, mailto:...
                    continue
                checked += 1
                where = f"{md.relative_to(ROOT)}:{number}"
                path_part, _, anchor = target.partition("#")
                file = (md.parent / unquote(path_part)).resolve() if path_part else md
                if not file.exists():
                    problems.append(f"{where}: link quebrado → {target}")
                    continue
                if anchor and file.suffix == ".md" and unquote(anchor) not in anchors_of(file):
                    problems.append(f"{where}: âncora inexistente → {target}")
    return checked


def check_svgs(problems: list[str]) -> int:
    svgs = sorted(ROOT.glob("docs/**/*.svg")) + sorted(ROOT.glob("packaging/**/*.svg"))
    for svg in svgs:
        try:
            ET.parse(svg)
        except ET.ParseError as error:
            problems.append(f"{svg.relative_to(ROOT)}: SVG inválido ({error})")
    return len(svgs)


def check_test_count(problems: list[str]) -> int:
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    real = suite.countTestCases()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for cited in re.findall(r"testes-(\d+)%20passando", readme):
        if int(cited) != real:
            problems.append(f"README.md: o selo diz {cited} testes, mas existem {real}")
    for md in markdown_files():
        for cited in re.findall(r"\b(\d+) testes\b", md.read_text(encoding="utf-8")):
            if int(cited) != real:
                problems.append(f"{md.relative_to(ROOT)}: cita {cited} testes, mas existem {real}")
    return real


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    problems: list[str] = []
    links = check_links(problems)
    svgs = check_svgs(problems)
    tests = check_test_count(problems)
    if problems:
        print(f"✖ {len(problems)} problema(s) na documentação:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"✔ documentação ok: {links} links, {svgs} SVGs, {tests} testes citados corretamente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
