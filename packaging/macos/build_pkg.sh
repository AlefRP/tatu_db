#!/bin/sh
# 🍎 Gera o instalador .pkg do macOS a partir do executável do PyInstaller.
#
#   python packaging/build_binary.py      # primeiro, o executável
#   sh packaging/macos/build_pkg.sh       # depois, o .pkg em dist/release/
#
# Resultado: dist/release/tatu-macos-arm64.pkg (Apple Silicon) ou tatu-macos-x86_64.pkg (Intel)
# O .pkg instala o comando em /usr/local/bin/tatu.
# Desinstalar:  sudo rm /usr/local/bin/tatu && sudo pkgutil --forget io.github.alefrp.tatu-db
#
# O pacote não é assinado pela Apple: na primeira vez, clique com o botão
# direito no .pkg e escolha "Abrir" (veja docs/instalacao.md).

set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EXE="$ROOT/build/pyinstaller/dist/tatu"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/tatu/__init__.py")"
ARCH="$(uname -m)"                              # arm64 ou x86_64
PKGROOT="$ROOT/build/pkg/root"
OUT="$ROOT/dist/release"
TARGET="$OUT/tatu-macos-${ARCH}.pkg"

[ -x "$EXE" ] || { echo "Executável não encontrado: rode python packaging/build_binary.py" >&2; exit 1; }

rm -rf "$PKGROOT"
mkdir -p "$PKGROOT/usr/local/bin" "$OUT"
install -m 0755 "$EXE" "$PKGROOT/usr/local/bin/tatu"

pkgbuild \
    --root "$PKGROOT" \
    --identifier io.github.alefrp.tatu-db \
    --version "$VERSION" \
    --install-location / \
    "$TARGET"
echo "✔ pacote: dist/release/$(basename "$TARGET")"
