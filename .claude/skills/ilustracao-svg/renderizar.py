"""
🖼️ Renderiza um SVG num navegador headless (Chrome, Edge ou Chromium) e salva um PNG
com a ilustração sobre fundo claro e sobre fundo escuro — para conferir os dois temas.

    python .claude/skills/ilustracao-svg/renderizar.py docs/assets/toca.svg
    python .claude/skills/ilustracao-svg/renderizar.py docs/assets/toca.svg --largura 800 --saida /tmp/toca.png
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
ON_PATH = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge"]


def find_browser() -> str | None:
    for candidate in CANDIDATES:
        if Path(candidate).exists():
            return candidate
    for name in ON_PATH:
        found = shutil.which(name)
        if found:
            return found
    return None


def svg_size(svg: Path) -> tuple[float, float]:
    text = svg.read_text(encoding="utf-8")
    match = re.search(r'viewBox="\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)"', text)
    if not match:
        return 1000.0, 600.0
    return float(match.group(1)), float(match.group(2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("svg", type=Path)
    parser.add_argument("--largura", type=int, default=1000, help="largura da imagem em pixels")
    parser.add_argument("--saida", type=Path, help="onde salvar o PNG (padrão: pasta temporária)")
    args = parser.parse_args()

    svg = args.svg.resolve()
    if not svg.exists():
        sys.exit(f"Arquivo não encontrado: {svg}")
    browser = find_browser()
    if browser is None:
        sys.exit("Não encontrei Chrome, Edge ou Chromium para renderizar.")

    width = args.largura
    w, h = svg_size(svg)
    height = int(width * h / w)
    workdir = Path(tempfile.mkdtemp(prefix="tatu-svg-"))
    html = workdir / "view.html"
    html.write_text(
        "<html><body style='margin:0'>"
        f"<div style='background:#ffffff;padding:12px'><img src='{svg.as_uri()}' style='width:{width}px;display:block'></div>"
        f"<div style='background:#0d1117;padding:12px'><img src='{svg.as_uri()}' style='width:{width}px;display:block'></div>"
        "</body></html>",
        encoding="utf-8",
    )
    output = (args.saida or workdir / f"{svg.stem}.png").resolve()
    subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
         f"--screenshot={output}", f"--window-size={width + 24},{2 * (height + 24)}", html.as_uri()],
        check=True, capture_output=True,
    )
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
