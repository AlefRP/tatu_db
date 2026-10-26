#!/bin/sh
# 🐾 Instalador do Tatu DB para Linux e macOS
#
# Cria os comandos `tatu` e `toca` sem precisar de sudo. Dois modos:
#   • python   — se houver Python 3.10+, instala num ambiente virtual só do Tatu;
#   • binario  — sem Python, baixa o executável pronto do último Release.
# Por padrão o modo é escolhido sozinho.
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.sh | sh
#   curl -fsSL .../install.sh | sh -s -- --binario     # força o executável pronto
#   sh scripts/install.sh               # de dentro do repositório: instala a cópia local
#   sh scripts/install.sh --uninstall   # remove tudo
#
# Variáveis opcionais:
#   TATU_REF       versão (tag, ex.: v0.1.0) ou branch a instalar (padrão: main / último Release)
#   TATU_HOME      onde ficam os arquivos       (padrão: ~/.local/share/tatu-db)
#   TATU_BIN_DIR   onde fica o comando `tatu`   (padrão: ~/.local/bin)
#   TATU_PYTHON    qual Python usar              (padrão: o primeiro >= 3.10 encontrado)

set -eu

REPO_URL="https://github.com/AlefRP/tatu_db"
REF="${TATU_REF:-main}"
TATU_HOME="${TATU_HOME:-$HOME/.local/share/tatu-db}"
BIN_DIR="${TATU_BIN_DIR:-$HOME/.local/bin}"
VENV="$TATU_HOME/venv"
BINARY="$TATU_HOME/tatu"
GUI_BINARY="$TATU_HOME/toca"
GUI_TARGET=""

# ─────────────────────────── aparência ───────────────────────────

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    SAND="$(printf '\033[38;5;180m')"; RED="$(printf '\033[31m')"
    GREEN="$(printf '\033[32m')"; DIM="$(printf '\033[2m')"; RESET="$(printf '\033[0m')"
else
    SAND=""; RED=""; GREEN=""; DIM=""; RESET=""
fi

step() { printf '%s==>%s %s\n' "$SAND" "$RESET" "$*"; }
ok()   { printf '%s✔%s %s\n' "$GREEN" "$RESET" "$*"; }
die()  { printf '%s✖ %s%s\n' "$RED" "$*" "$RESET" >&2; exit 1; }

armadillo() {
    printf '%s' "$SAND"
    cat <<'EOF'
                 _.-''''''''-._
            _.-''  |  |  |  |  ''-._      __
         .-'   |   |  |  |  |   |   '-.  / /
       .'   |  |   |  |  |  |   |  |   './ /____
      (_____|__|___|__|__|__|___|__|_____)  o   ''-._
  ~~~~~   \__\  \__\          /__/  /__/ '-._______.-'
EOF
    printf '%s\n' "$RESET"
}

usage() {
    sed -n '2,20p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'
}

# Apaga só o que é do Tatu (nunca a pasta inteira: TATU_HOME pode ter outras coisas).
remove_installation() {
    rm -rf "$VENV" "$BINARY" "$GUI_BINARY"
    rmdir "$TATU_HOME" 2>/dev/null || true
}

# ─────────────────────────── desinstalar ───────────────────────────

uninstall() {
    step "Removendo o Tatu DB de $TATU_HOME"
    remove_installation
    for command in tatu toca; do
        if [ -L "$BIN_DIR/$command" ]; then
            case "$(readlink "$BIN_DIR/$command")" in
                "$TATU_HOME"/*) rm -f "$BIN_DIR/$command" ;;  # só se o link for nosso
            esac
        fi
    done
    ok "Tatu DB removido. Seus arquivos .tatu continuam onde estavam."
    exit 0
}

# ─────────────────────────── modo python ───────────────────────────

find_python() {
    for candidate in ${TATU_PYTHON:-} python3 python3.14 python3.13 python3.12 python3.11 python3.10 python; do
        if command -v "$candidate" >/dev/null 2>&1 &&
           "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

python_is_usable() {  # tem Python 3.10+ com o módulo venv completo?
    PYTHON="$(find_python)" || return 1
    "$PYTHON" -c 'import venv, ensurepip' >/dev/null 2>&1
}

find_source() {
    # Rodando de dentro de um clone do repositório? Então instala a cópia local.
    here="$(cd "$(dirname "$0")" 2>/dev/null && pwd || true)"
    if [ -n "$here" ] && [ -f "$here/../pyproject.toml" ] &&
       grep -q 'name = "tatu-db"' "$here/../pyproject.toml" 2>/dev/null; then
        (cd "$here/.." && pwd)
    else
        echo "$REPO_URL/archive/$REF.tar.gz"
    fi
}

install_with_python() {
    ok "Usando $PYTHON ($("$PYTHON" -c 'import platform; print(platform.python_version())'))"
    SOURCE="$(find_source)"
    step "Criando o ambiente virtual em $VENV"
    remove_installation
    mkdir -p "$TATU_HOME"
    "$PYTHON" -m venv "$VENV" || die "Não consegui criar o ambiente virtual."

    step "Instalando o Tatu DB ${DIM}($SOURCE)${RESET}"
    "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade "$SOURCE" ||
        die "A instalação falhou. Verifique sua conexão com a internet e tente de novo."
    TARGET="$VENV/bin/tatu"
    if [ -x "$VENV/bin/toca" ]; then
        GUI_TARGET="$VENV/bin/toca"
    fi
}

# ─────────────────────────── modo binário ───────────────────────────

asset_name() {
    case "$(uname -s)" in
        Linux)  os="linux" ;;
        Darwin) os="macos" ;;
        *)      return 1 ;;
    esac
    case "$(uname -m)" in
        x86_64|amd64)  arch="x86_64" ;;
        aarch64|arm64) arch="arm64" ;;
        *)             return 1 ;;
    esac
    echo "tatu-$os-$arch"
}

release_url() {  # versão fixa (vX.Y.Z) ou o último Release
    case "$REF" in
        v[0-9]*) echo "$REPO_URL/releases/download/$REF/$1" ;;
        *)       echo "$REPO_URL/releases/latest/download/$1" ;;
    esac
}

download() {  # url destino
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$1" -o "$2"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$1" -O "$2"
    else
        die "Preciso do curl ou do wget para baixar o executável."
    fi
}

install_binary() {
    NAME="$(asset_name)" || die "Não há executável pronto para $(uname -s) $(uname -m). \
Instale o Python 3.10+ e rode este instalador de novo."
    URL="$(release_url "$NAME.tar.gz")"
    step "Baixando o executável ${DIM}($URL)${RESET}"
    TMP="$(mktemp -d)"
    download "$URL" "$TMP/tatu.tar.gz" || { rm -rf "$TMP"; die "Não consegui baixar $URL"; }
    tar -xzf "$TMP/tatu.tar.gz" -C "$TMP" || { rm -rf "$TMP"; die "O arquivo baixado veio corrompido."; }
    remove_installation
    mkdir -p "$TATU_HOME"
    cp "$TMP/$NAME/tatu" "$BINARY"
    chmod 0755 "$BINARY"
    # Releases antigos trazem só o shell; o cliente passa a acompanhar os novos portáteis.
    if [ -f "$TMP/$NAME/toca" ]; then
        cp "$TMP/$NAME/toca" "$GUI_BINARY"
        chmod 0755 "$GUI_BINARY"
        GUI_TARGET="$GUI_BINARY"
    fi
    rm -rf "$TMP"
    TARGET="$BINARY"
}

# ─────────────────────────── instalar ───────────────────────────

install() {
    armadillo
    case "$MODE" in
        python)
            step "Procurando Python 3.10 ou mais novo (com venv)"
            python_is_usable || die "Não encontrei Python 3.10+ com o módulo venv. \
(macOS: brew install python · Ubuntu/Debian: sudo apt install python3 python3-venv) \
— ou rode com --binario para usar o executável pronto."
            install_with_python
            ;;
        binario)
            install_binary
            ;;
        *)
            step "Procurando Python 3.10 ou mais novo (com venv)"
            if python_is_usable; then
                install_with_python
            else
                step "Python 3.10+ não encontrado: vou instalar o executável pronto (não precisa de Python)"
                install_binary
            fi
            ;;
    esac

    mkdir -p "$BIN_DIR"
    ln -sf "$TARGET" "$BIN_DIR/tatu"
    if [ -n "$GUI_TARGET" ]; then
        ln -sf "$GUI_TARGET" "$BIN_DIR/toca"
        ok "Cliente gráfico Toca instalado em $BIN_DIR/toca"
    elif [ -L "$BIN_DIR/toca" ]; then
        # Ao voltar a uma versão antiga, não deixe um atalho nosso apontando para um arquivo removido.
        case "$(readlink "$BIN_DIR/toca")" in
            "$TATU_HOME"/*) rm -f "$BIN_DIR/toca" ;;
        esac
    fi
    VERSION="$("$BIN_DIR/tatu" --version)" || die "O comando tatu não funcionou depois de instalado."
    ok "$VERSION instalado em $BIN_DIR/tatu"

    case ":$PATH:" in
        *":$BIN_DIR:"*)
            printf '\nPronto! Abra o shell com:  %statu%s   (e digite .demo)\n' "$SAND" "$RESET"
            ;;
        *)
            case "${SHELL:-}" in
                */zsh)  RC="~/.zshrc" ;;
                */fish) RC="~/.config/fish/config.fish" ;;
                *)      RC="~/.bashrc" ;;
            esac
            printf '\n%s%s ainda não está no seu PATH.%s Adicione esta linha ao %s:\n\n' "$SAND" "$BIN_DIR" "$RESET" "$RC"
            if [ "$RC" = "~/.config/fish/config.fish" ]; then
                printf '    fish_add_path %s\n\n' "$BIN_DIR"
            else
                printf '    export PATH="%s:$PATH"\n\n' "$BIN_DIR"
            fi
            printf 'Depois abra um terminal novo e rode:  %statu%s\n' "$SAND" "$RESET"
            ;;
    esac
}

MODE="auto"
case "${1:-}" in
    --uninstall|-u) uninstall ;;
    --help|-h)      usage; exit 0 ;;
    --binario|-b)   MODE="binario" ;;
    --python|-p)    MODE="python" ;;
    "")             ;;
    *)              die "Opção desconhecida: $1 (use --help)" ;;
esac
install
