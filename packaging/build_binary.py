"""
📦 Gera o executável `tatu` (sem precisar de Python instalado) para o sistema atual.

    pip install pyinstaller
    python packaging/build_binary.py

Resultado em ``dist/release/``:

    tatu-<versão>-linux-x86_64.tar.gz
    tatu-<versão>-macos-arm64.tar.gz
    tatu-<versão>-windows-x86_64.zip

O executável solto fica em ``build/pyinstaller/dist/`` — é dele que os scripts
de .deb, .pkg e do instalador do Windows partem.
"""

import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "pyinstaller"
RELEASE = ROOT / "dist" / "release"

sys.path.insert(0, str(ROOT))
from tatu import __version__  # noqa: E402


def platform_name() -> str:
    system = {"Darwin": "macos", "Windows": "windows"}.get(platform.system(), platform.system().lower())
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
    return f"{system}-{machine}"


def build() -> Path:
    exe_name = "tatu.exe" if sys.platform == "win32" else "tatu"
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--console", "--clean", "--noconfirm",
        "--name", "tatu",
        "--paths", str(ROOT),
        "--distpath", str(BUILD / "dist"),
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
    ]
    if sys.platform == "win32":
        args += ["--icon", str(ROOT / "packaging" / "icons" / "tatu.ico")]
    args.append(str(ROOT / "packaging" / "pyinstaller" / "tatu_entry.py"))
    print("→", " ".join(args), flush=True)
    subprocess.run(args, check=True)
    return BUILD / "dist" / exe_name


def smoke_test(exe: Path) -> None:
    """Confere se o executável roda de verdade antes de empacotar."""
    version = subprocess.run([str(exe), "--version"], capture_output=True, text=True, check=True)
    assert __version__ in version.stdout, version.stdout
    query = subprocess.run([str(exe), "-c", "SELECT 6 * 7 AS resposta"],
                           capture_output=True, check=True)
    assert b"42" in query.stdout, query.stdout
    print(f"✔ {exe.name} funciona: {version.stdout.strip()}", flush=True)


def archive(exe: Path) -> Path:
    RELEASE.mkdir(parents=True, exist_ok=True)
    base = f"tatu-{__version__}-{platform_name()}"
    extras = [ROOT / "README.md", ROOT / "LICENSE"]
    if sys.platform == "win32":
        target = RELEASE / f"{base}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            for path in [exe, *extras]:
                z.write(path, f"{base}/{path.name}")
    else:
        target = RELEASE / f"{base}.tar.gz"
        with tarfile.open(target, "w:gz") as tar:
            for path in [exe, *extras]:
                tar.add(path, f"{base}/{path.name}")
    print(f"✔ pacote: {target.relative_to(ROOT)}", flush=True)
    return target


def main() -> None:
    try:
        sys.stdout.reconfigure(errors="replace")  # consoles sem UTF-8 não quebram com o ✔
    except (AttributeError, ValueError):
        pass
    if shutil.which("pyinstaller") is None and subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"], capture_output=True).returncode != 0:
        sys.exit("Instale o PyInstaller antes: pip install pyinstaller")
    exe = build()
    smoke_test(exe)
    archive(exe)


if __name__ == "__main__":
    main()
