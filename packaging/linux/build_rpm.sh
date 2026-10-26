#!/bin/sh
# 🎩 Gera o pacote .rpm (Fedora, RHEL, Rocky, AlmaLinux, openSUSE...) a partir do
# executável do PyInstaller. Precisa do rpmbuild (no Ubuntu: sudo apt install rpm).
#
#   python packaging/build_binary.py --all # primeiro, o shell e o cliente gráfico
#   sh packaging/linux/build_rpm.sh       # depois, o .rpm em dist/release/
#
# Resultado: dist/release/tatu-linux-x86_64.rpm (ou -arm64.rpm)
# Instalar:     sudo dnf install ./tatu-linux-x86_64.rpm
# Desinstalar:  sudo dnf remove tatu-db

set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EXE="$ROOT/build/pyinstaller/dist/tatu"
GUI="$ROOT/build/pyinstaller/dist/toca"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/tatu/__init__.py")"
case "$(uname -m)" in
    aarch64|arm64) RPM_ARCH="aarch64"; ARCH_NAME="arm64" ;;
    *)             RPM_ARCH="x86_64";  ARCH_NAME="x86_64" ;;
esac
TOP="$ROOT/build/rpm"
OUT="$ROOT/dist/release"
TARGET="$OUT/tatu-linux-${ARCH_NAME}.rpm"

[ -x "$EXE" ] || { echo "Executável não encontrado: rode python packaging/build_binary.py" >&2; exit 1; }
[ -x "$GUI" ] || { echo "Toca não encontrado: rode python packaging/build_binary.py --all" >&2; exit 1; }
command -v rpmbuild >/dev/null 2>&1 || { echo "Preciso do rpmbuild (Ubuntu: sudo apt install rpm)" >&2; exit 1; }

rm -rf "$TOP"
mkdir -p "$TOP/SPECS" "$OUT"
cat > "$TOP/SPECS/tatu-db.spec" <<EOF
Name:           tatu-db
Version:        $VERSION
Release:        1
Summary:        Banco de dados relacional educacional, feito do zero em Python
License:        MIT
URL:            https://github.com/AlefRP/tatu_db
AutoReqProv:    no
Requires:       glibc >= 2.35, libX11, libXext, libXrender, libXft, libXScrnSaver, fontconfig

# O executável do PyInstaller carrega um arquivo compactado colado no fim.
# Se o rpmbuild fizer o "strip" de sempre, o executável quebra — então desligamos.
%global debug_package %{nil}
%global __os_install_post %{nil}
%global _build_id_links none

%description
O Tatu DB é um banco de dados relacional minúsculo, escrito para ensinar
como um banco funciona por dentro: tokenizer, parser, planejador,
operadores, índices e transações. Rode "tatu" e digite ".demo", ou abra
o Toca pelo menu de aplicativos para usar o editor SQL e explorar tabelas.

%install
mkdir -p %{buildroot}%{_bindir} %{buildroot}%{_docdir}/%{name} %{buildroot}%{_licensedir}/%{name}
mkdir -p %{buildroot}%{_datadir}/applications %{buildroot}%{_datadir}/icons/hicolor/128x128/apps
install -m 0755 "$EXE" %{buildroot}%{_bindir}/tatu
install -m 0755 "$GUI" %{buildroot}%{_bindir}/toca
install -m 0644 "$ROOT/packaging/linux/toca.desktop" %{buildroot}%{_datadir}/applications/toca.desktop
install -m 0644 "$ROOT/tatu/assets/toca.png" %{buildroot}%{_datadir}/icons/hicolor/128x128/apps/toca.png
install -m 0644 "$ROOT/README.md" %{buildroot}%{_docdir}/%{name}/README.md
install -m 0644 "$ROOT/LICENSE" %{buildroot}%{_licensedir}/%{name}/LICENSE

%files
%{_bindir}/tatu
%{_bindir}/toca
%{_datadir}/applications/toca.desktop
%{_datadir}/icons/hicolor/128x128/apps/toca.png
%{_docdir}/%{name}
%{_licensedir}/%{name}
EOF

rpmbuild -bb --quiet --define "_topdir $TOP" --target "$RPM_ARCH" "$TOP/SPECS/tatu-db.spec"
cp "$TOP/RPMS/$RPM_ARCH/tatu-db-$VERSION-1.$RPM_ARCH.rpm" "$TARGET"
echo "✔ pacote: dist/release/$(basename "$TARGET")"
