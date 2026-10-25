#!/bin/sh
# 🐾 Instalador do Tatu DB para Linux e macOS
#
# Instala o Tatu DB num ambiente virtual só dele e cria o comando `tatu`.
# Não precisa de sudo e não mexe no Python do sistema.
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.sh | sh
#   sh scripts/install.sh               # de dentro do repositório: instala a cópia local
#   sh scripts/install.sh --uninstall   # remove tudo
#
# Variáveis opcionais:
#   TATU_REF       branch ou tag do GitHub a instalar (padrão: main)
#   TATU_HOME      onde fica o ambiente virtual (padrão: ~/.local/share/tatu-db)
#   TATU_BIN_DIR   onde fica o comando `tatu`    (padrão: ~/.local/bin)
#   TATU_PYTHON    qual Python usar               (padrão: o primeiro >= 3.10 encontrado)

set -eu

REPO_URL="https://github.com/AlefRP/tatu_db"
REF="${TATU_REF:-main}"
TATU_HOME="${TATU_HOME:-$HOME/.local/share/tatu-db}"
BIN_DIR="${TATU_BIN_DIR:-$HOME/.local/bin}"
VENV="$TATU_HOME/venv"

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
    sed -n '2,17p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'
}

# ─────────────────────────── desinstalar ───────────────────────────

uninstall() {
    step "Removendo o Tatu DB de $TATU_HOME"
    rm -rf "$TATU_HOME"
    if [ -L "$BIN_DIR/tatu" ]; then
        rm -f "$BIN_DIR/tatu"
    fi
    ok "Tatu DB removido. Seus arquivos .tatu continuam onde estavam."
    exit 0
}

# ─────────────────────────── instalar ───────────────────────────

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

install() {
    armadillo
    step "Procurando Python 3.10 ou mais novo"
    PYTHON="$(find_python)" || die "Não encontrei Python 3.10+. Instale em https://www.python.org/downloads/ \
(macOS: brew install python · Ubuntu/Debian: sudo apt install python3 python3-venv)"
    ok "Usando $PYTHON ($("$PYTHON" -c 'import platform; print(platform.python_version())'))"

    if ! "$PYTHON" -c 'import venv, ensurepip' >/dev/null 2>&1; then
        die "Esse Python não tem o módulo venv completo. No Ubuntu/Debian: sudo apt install python3-venv"
    fi

    SOURCE="$(find_source)"
    step "Criando o ambiente virtual em $VENV"
    rm -rf "$VENV"
    mkdir -p "$TATU_HOME"
    "$PYTHON" -m venv "$VENV" || die "Não consegui criar o ambiente virtual."

    step "Instalando o Tatu DB ${DIM}($SOURCE)${RESET}"
    "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade "$SOURCE" ||
        die "A instalação falhou. Verifique sua conexão com a internet e tente de novo."

    mkdir -p "$BIN_DIR"
    ln -sf "$VENV/bin/tatu" "$BIN_DIR/tatu"
    VERSION="$("$BIN_DIR/tatu" --version)"
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

case "${1:-}" in
    --uninstall|-u) uninstall ;;
    --help|-h)      usage ;;
    "")             install ;;
    *)              die "Opção desconhecida: $1 (use --help)" ;;
esac
