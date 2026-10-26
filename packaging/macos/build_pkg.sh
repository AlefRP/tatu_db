#!/bin/sh
# 🍎 Gera o instalador .pkg do macOS a partir do executável do PyInstaller.
#
#   python packaging/build_binary.py --all # primeiro, o shell e o cliente gráfico
#   sh packaging/macos/build_pkg.sh       # depois, o .pkg em dist/release/
#
# Resultado: dist/release/tatu-macos-arm64.pkg (Apple Silicon) ou tatu-macos-x86_64.pkg (Intel)
# O .pkg instala os comandos em /usr/local/bin e o Toca em /Applications/Toca.app.
#
# O pacote não é assinado pela Apple: na primeira vez, clique com o botão
# direito no .pkg e escolha "Abrir" (veja docs/instalacao.md).

set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EXE="$ROOT/build/pyinstaller/dist/tatu"
GUI="$ROOT/build/pyinstaller/dist/toca"
APP="$ROOT/build/pyinstaller/dist/toca.app"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/tatu/__init__.py")"
ARCH="$(uname -m)"                              # arm64 ou x86_64
PKGROOT="$ROOT/build/pkg/root"
OUT="$ROOT/dist/release"
TARGET="$OUT/tatu-macos-${ARCH}.pkg"

[ -x "$EXE" ] || { echo "Executável não encontrado: rode python packaging/build_binary.py" >&2; exit 1; }
[ -x "$GUI" ] && [ -d "$APP" ] || {
    echo "Toca não encontrado: rode python packaging/build_binary.py --all no macOS" >&2; exit 1;
}

rm -rf "$PKGROOT"
mkdir -p "$PKGROOT/usr/local/bin" "$PKGROOT/Applications" "$OUT"
install -m 0755 "$EXE" "$PKGROOT/usr/local/bin/tatu"
install -m 0755 "$GUI" "$PKGROOT/usr/local/bin/toca"
ditto "$APP" "$PKGROOT/Applications/Toca.app"

pkgbuild \
    --root "$PKGROOT" \
    --identifier io.github.alefrp.tatu-db \
    --version "$VERSION" \
    --install-location / \
    "$TARGET"
echo "✔ pacote: dist/release/$(basename "$TARGET")"
