"""
📦 Gera executáveis e instaladores do Tatu DB e do cliente gráfico Toca.

    pip install pyinstaller
    python packaging/build_binary.py
    python packaging/build_binary.py --all
    python packaging/build_binary.py --installer  # Windows, com Inno Setup 6.3+

Resultado em ``dist/release/`` (um destes, conforme o sistema):

    tatu-linux-x86_64.tar.gz     tatu-linux-arm64.tar.gz
    tatu-macos-arm64.tar.gz      tatu-macos-x86_64.tar.gz
    tatu-windows-x86_64.zip

Os nomes não têm a versão de propósito: assim o link
``releases/latest/download/<nome>`` sempre aponta para a versão mais nova,
e os instaladores de uma linha sabem o que baixar.

O executável solto fica em ``build/pyinstaller/dist/`` — é dele que os scripts
de .deb, .rpm, .pkg e do instalador do Windows partem.
"""

import argparse
import os
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


def build(gui: bool = False) -> Path:
    name = "toca" if gui else "tatu"
    exe_name = name + ".exe" if sys.platform == "win32" else name
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed" if gui else "--console", "--clean", "--noconfirm",
        "--name", name,
        "--paths", str(ROOT),
        "--distpath", str(BUILD / "dist"),
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
    ]
    if gui:
        args += ["--add-data", f"{ROOT / 'tatu' / 'assets' / 'toca.png'}{os.pathsep}tatu/assets"]
    if sys.platform == "win32":
        args += ["--icon", str(ROOT / "packaging" / "icons" / ("toca.ico" if gui else "tatu.ico"))]
        if gui:
            args += ["--manifest", str(ROOT / "packaging" / "windows" / "toca.manifest")]
    args.append(str(ROOT / "packaging" / "pyinstaller" / ("toca_entry.py" if gui else "tatu_entry.py")))
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


def smoke_test_gui(exe: Path) -> None:
    """Abre o Tk, consulta o banco em memória e confere a grade antes de distribuir."""
    subprocess.run([str(exe), "--smoke-test"], check=True, timeout=30)
    print(f"✔ {exe.name} funciona: consulta SQL e grade verificadas", flush=True)


def archive(exe: Path, gui: bool = False, companions: tuple[Path, ...] = ()) -> Path:
    RELEASE.mkdir(parents=True, exist_ok=True)
    base = f"{'toca' if gui else 'tatu'}-{platform_name()}"
    extras = [ROOT / "README.md", ROOT / "LICENSE"]
    paths = [exe, *companions, *extras]
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Arquivo ausente no pacote: {path}. Gere os executáveis antes.")
    if sys.platform == "win32":
        target = RELEASE / f"{base}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            for path in paths:
                z.write(path, f"{base}/{path.name}")
    else:
        target = RELEASE / f"{base}.tar.gz"
        with tarfile.open(target, "w:gz") as tar:
            for path in paths:
                tar.add(path, f"{base}/{path.name}")
    print(f"✔ pacote: {target.relative_to(ROOT)}", flush=True)
    return target


def installer(compiler: str | None = None) -> Path:
    """Compila o instalador conjunto, usando a versão do próprio pacote."""
    candidates = [compiler, shutil.which("iscc")]
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        if os.environ.get(variable):
            directory = Path(os.environ[variable])
            if variable == "LOCALAPPDATA":
                directory /= "Programs"
            candidates.append(str(directory / "Inno Setup 6" / "ISCC.exe"))
    iscc = next((str(Path(path).resolve()) for path in candidates if path and Path(path).is_file()), None)
    if not iscc:
        sys.exit("Instale o Inno Setup 6.3+ ou informe --iscc caminho/ISCC.exe para gerar o instalador.")
    subprocess.run([
        iscc, "/Qp", f"/DAppVersion={__version__}", str(ROOT / "packaging" / "windows" / "tatu.iss"),
    ], check=True)
    target = RELEASE / "tatu-windows-x86_64-setup.exe"
    print(f"✔ instalador do banco e cliente: {target.relative_to(ROOT)}", flush=True)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Empacota o banco Tatu e o cliente gráfico Toca.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--gui", action="store_true", help="gera somente o executável gráfico Toca")
    mode.add_argument("--all", action="store_true", help="gera banco, cliente e portáteis conjuntos")
    mode.add_argument("--installer", action="store_true", help="gera ambos e o instalador Windows")
    parser.add_argument("--iscc", help="caminho do compilador Inno Setup (com --installer)")
    args = parser.parse_args()
    if args.installer and sys.platform != "win32":
        parser.error("--installer requer Windows; use --all e o script de pacotes do seu sistema")
    if args.iscc and not args.installer:
        parser.error("--iscc requer --installer")
    try:
        sys.stdout.reconfigure(errors="replace")  # consoles sem UTF-8 não quebram com o ✔
    except (AttributeError, ValueError):
        pass
    if shutil.which("pyinstaller") is None and subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"], capture_output=True).returncode != 0:
        sys.exit("Instale o PyInstaller antes: pip install pyinstaller")
    if args.all or args.installer:
        cli, gui = build(), build(gui=True)
        smoke_test(cli)
        smoke_test_gui(gui)
        bundles = (BUILD / "dist" / "toca.app",) if sys.platform == "darwin" else ()
        archive(cli, companions=(gui, *bundles))
        archive(gui, gui=True, companions=bundles)
        if args.installer:
            installer(args.iscc)
    else:
        exe = build(gui=args.gui)
        if not args.gui:
            smoke_test(exe)
        else:
            smoke_test_gui(exe)
        bundles = (BUILD / "dist" / "toca.app",) if args.gui and sys.platform == "darwin" else ()
        archive(exe, gui=args.gui, companions=bundles)


if __name__ == "__main__":
    main()
