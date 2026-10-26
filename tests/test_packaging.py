"""Os portáteis entregam banco, cliente e recursos sem depender do código-fonte."""

import importlib.util
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("tatu_build_binary", ROOT / "packaging" / "build_binary.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class PackagingTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.release = self.root / "dist" / "release"
        for name in ("tatu.exe", "toca.exe", "README.md", "LICENSE"):
            (self.root / name).write_text(name, encoding="utf-8")
        for name, value in (("ROOT", self.root), ("RELEASE", self.release)):
            patcher = patch.object(builder, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_portatil_windows_inclui_banco_e_cliente(self):
        with patch.object(builder.sys, "platform", "win32"), \
                patch.object(builder, "platform_name", return_value="windows-x86_64"):
            package = builder.archive(self.root / "tatu.exe", companions=(self.root / "toca.exe",))
        with zipfile.ZipFile(package) as archive:
            self.assertEqual(set(archive.namelist()), {
                f"tatu-windows-x86_64/{name}" for name in ("tatu.exe", "toca.exe", "README.md", "LICENSE")
            })
            self.assertEqual(archive.read("tatu-windows-x86_64/toca.exe"), b"toca.exe")

    def test_portatil_macos_preserva_conteudo_do_aplicativo(self):
        app = self.root / "toca.app"
        executable = app / "Contents" / "MacOS" / "toca"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"cliente grafico")
        with patch.object(builder.sys, "platform", "darwin"), \
                patch.object(builder, "platform_name", return_value="macos-arm64"):
            package = builder.archive(self.root / "toca.exe", gui=True, companions=(app,))
        with tarfile.open(package) as archive:
            bundled = archive.extractfile("toca-macos-arm64/toca.app/Contents/MacOS/toca")
            self.assertEqual(bundled.read(), b"cliente grafico")

    def test_cliente_ausente_nao_sobrescreve_pacote_valido(self):
        self.release.mkdir(parents=True)
        package = self.release / "tatu-windows-x86_64.zip"
        package.write_bytes(b"pacote anterior")
        with patch.object(builder.sys, "platform", "win32"), \
                patch.object(builder, "platform_name", return_value="windows-x86_64"), \
                self.assertRaises(FileNotFoundError):
            builder.archive(self.root / "tatu.exe", companions=(self.root / "ausente.exe",))
        self.assertEqual(package.read_bytes(), b"pacote anterior")
