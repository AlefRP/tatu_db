#!/bin/sh
# 🐧 Gera o pacote .deb (Debian, Ubuntu, Mint...) a partir do executável do PyInstaller.
#
#   python packaging/build_binary.py      # primeiro, o executável
#   sh packaging/linux/build_deb.sh       # depois, o .deb em dist/release/
#
# Resultado: dist/release/tatu-linux-x86_64.deb (ou -arm64.deb)
# Instalar:     sudo apt install ./tatu-linux-x86_64.deb
# Desinstalar:  sudo apt remove tatu-db

set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EXE="$ROOT/build/pyinstaller/dist/tatu"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/tatu/__init__.py")"
ARCH="$(dpkg --print-architecture)"            # amd64 ou arm64 (nomes do Debian)
case "$ARCH" in
    amd64) ARCH_NAME="x86_64" ;;
    *)     ARCH_NAME="$ARCH" ;;
esac
PKG="$ROOT/build/deb/tatu-db_${VERSION}_${ARCH}"
OUT="$ROOT/dist/release"
TARGET="$OUT/tatu-linux-${ARCH_NAME}.deb"

[ -x "$EXE" ] || { echo "Executável não encontrado: rode python packaging/build_binary.py" >&2; exit 1; }

rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/usr/bin" "$PKG/usr/share/doc/tatu-db" "$OUT"
install -m 0755 "$EXE" "$PKG/usr/bin/tatu"
install -m 0644 "$ROOT/README.md" "$PKG/usr/share/doc/tatu-db/README.md"
install -m 0644 "$ROOT/LICENSE" "$PKG/usr/share/doc/tatu-db/copyright"

cat > "$PKG/DEBIAN/control" <<EOF
Package: tatu-db
Version: $VERSION
Section: database
Priority: optional
Architecture: $ARCH
Maintainer: AlefRP <93484657+AlefRP@users.noreply.github.com>
Homepage: https://github.com/AlefRP/tatu_db
Description: banco de dados relacional educacional, feito do zero em Python
 O Tatu DB é um banco de dados relacional minúsculo, escrito para ensinar
 como um banco funciona por dentro: tokenizer, parser, planejador,
 operadores, índices e transações. Rode "tatu" e digite ".demo".
EOF

dpkg-deb --build --root-owner-group "$PKG" "$TARGET"
echo "✔ pacote: dist/release/$(basename "$TARGET")"
