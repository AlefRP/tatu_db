# 📦 Instalação

> [← índice](README.md) · [README](../README.md)

O Tatu DB não tem nenhuma dependência além do Python, e mesmo o Python é opcional: há instaladores
e executáveis prontos para Windows, macOS e Linux. Escolha o caminho que combina com você:

| Jeito | Precisa de Python? | Ideal para |
|---|:-:|---|
| 🧑‍💻 [Código-fonte](#-do-código-fonte-recomendado-para-estudar) | ✅ 3.10+ | **estudar o código** (o melhor para a trilha de aprendizado) |
| ⚡ [Script de instalação](#-script-de-instalação) | ✅ 3.10+ (o script avisa se faltar) | ter o comando `tatu` em um minuto |
| 📀 [Instaladores](#-instaladores-exe-pkg-deb) `.exe` `.pkg` `.deb` | ❌ | quem não quer instalar Python |
| 🎒 [Executável portátil](#-executável-portátil) `.zip` `.tar.gz` | ❌ | usar sem instalar nada (até de um pendrive) |
| 🐍 [pip / pipx](#-pip-e-pipx) | ✅ 3.10+ | quem já vive no ecossistema Python |

Os instaladores e executáveis ficam na página de **[Releases](https://github.com/AlefRP/tatu_db/releases/latest)**.

---

## 🧑‍💻 Do código-fonte (recomendado para estudar)

```bash
git clone https://github.com/AlefRP/tatu_db.git
cd tatu_db
python -m tatu          # pronto! (no macOS/Linux talvez seja python3)
```

Nada para instalar: o código que roda é o mesmo que você está lendo. Quer o comando `tatu` apontando
para a sua cópia (e refletindo suas mudanças na hora)? Rode `pip install -e .` dentro da pasta.

## ⚡ Script de instalação

O script procura um Python 3.10+, cria um ambiente virtual **só para o Tatu** (não mexe no Python do
sistema), instala o pacote e cria o comando `tatu`. Não pede administrador.

### 🪟 Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.ps1 | iex
```

- Instala em `%LOCALAPPDATA%\tatu-db` e coloca `%LOCALAPPDATA%\tatu-db\bin` no PATH do seu usuário.
- Funciona no Windows PowerShell 5.1 (o que vem com o Windows) e no PowerShell 7.
- Não tem Python? `winget install Python.Python.3.13` e rode o script de novo.

### 🍎 macOS e 🐧 Linux

```bash
curl -fsSL https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.sh | sh
```

- Instala em `~/.local/share/tatu-db` e cria `~/.local/bin/tatu`.
- Se `~/.local/bin` não estiver no seu PATH, o script mostra a linha exata para colar no `~/.zshrc` ou `~/.bashrc`.
- **Ubuntu/Debian:** o script avisa se faltar o pacote do venv — `sudo apt install python3-venv`.

### Opções dos scripts

| | Windows | macOS / Linux |
|---|---|---|
| instalar uma versão específica | `$env:TATU_REF = "v0.1.0"` antes de rodar | `curl ... \| TATU_REF=v0.1.0 sh` |
| escolher a pasta | `$env:TATU_HOME = "D:\ferramentas\tatu"` | `TATU_HOME=... TATU_BIN_DIR=...` |
| escolher o Python | `$env:TATU_PYTHON = "C:\Python313\python.exe"` | `TATU_PYTHON=python3.12` |
| não mexer no PATH | parâmetro `-NoPath` | (o script nunca mexe nos seus arquivos de shell) |

Dentro de um clone do repositório, os scripts instalam a **cópia local**: `sh scripts/install.sh`
ou `.\scripts\install.ps1`.

## 📀 Instaladores (.exe, .pkg, .deb)

Baixe na página de [Releases](https://github.com/AlefRP/tatu_db/releases/latest). Eles trazem um
executável que já inclui o Python — não precisa ter nada instalado.

| Sistema | Arquivo | Como instalar |
|---|---|---|
| 🪟 Windows 10/11 (x64) | `tatu-<versão>-windows-x86_64-setup.exe` | dê dois cliques; o assistente cria o atalho no menu Iniciar e (se você deixar marcado) põe o `tatu` no PATH |
| 🍎 macOS (Apple Silicon) | `tatu-<versão>-macos-arm64.pkg` | dê dois cliques; instala em `/usr/local/bin/tatu` |
| 🐧 Debian, Ubuntu, Mint… (x64) | `tatu-db_<versão>_amd64.deb` | `sudo apt install ./tatu-db_<versão>_amd64.deb` |

> [!WARNING]
> Os instaladores **não são assinados digitalmente** (assinatura custa caro para um projeto educacional).
> Por isso o sistema vai desconfiar na primeira vez:
>
> - **Windows** — "O Windows protegeu o computador": clique em **Mais informações → Executar assim mesmo**.
> - **macOS** — "não pode ser aberto porque é de um desenvolvedor não identificado": clique com o **botão
>   direito** no `.pkg` → **Abrir**, ou vá em **Ajustes do Sistema → Privacidade e Segurança → Abrir Mesmo Assim**.
>
> Desconfiar é saudável! Se preferir, use o script ou o código-fonte — dá para ler cada linha antes.

Mac com processador Intel? Ainda não há instalador para ele: use o [script](#-macos-e--linux) ou o [pipx](#-pip-e-pipx).

## 🎒 Executável portátil

Também nos [Releases](https://github.com/AlefRP/tatu_db/releases/latest): um único arquivo `tatu`
(ou `tatu.exe`), sem instalação.

```bash
# Linux
tar xzf tatu-<versão>-linux-x86_64.tar.gz
./tatu-<versão>-linux-x86_64/tatu

# macOS (tire a "quarentena" que o navegador coloca em downloads)
tar xzf tatu-<versão>-macos-arm64.tar.gz
xattr -d com.apple.quarantine tatu-<versão>-macos-arm64/tatu
./tatu-<versão>-macos-arm64/tatu
```

No Windows, descompacte o `.zip` e dê dois cliques em `tatu.exe` (ou rode-o no terminal).

> [!NOTE]
> O executável é um "pacote" com o Python dentro: na primeira execução ele leva um segundinho a mais
> para se desempacotar numa pasta temporária.

## 🐍 pip e pipx

```bash
pipx install git+https://github.com/AlefRP/tatu_db.git     # recomendado: isolado e com o comando tatu
pip install git+https://github.com/AlefRP/tatu_db.git      # dentro de um ambiente virtual seu
```

Para usar como biblioteca no seu código, o pacote se chama `tatu`: `import tatu`.

---

## ✅ Conferindo

```bash
tatu --version
tatu -c "SELECT 'funcionou!' AS status"
tatu                     # abre o shell; digite .demo
```

## 🗑️ Desinstalando

| Instalou com… | Para remover |
|---|---|
| script (Windows) | `& ([scriptblock]::Create((irm https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.ps1))) -Uninstall` |
| script (macOS/Linux) | `curl -fsSL https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.sh \| sh -s -- --uninstall` |
| setup.exe | **Configurações → Aplicativos → Tatu DB → Desinstalar** |
| .pkg | `sudo rm /usr/local/bin/tatu && sudo pkgutil --forget io.github.alefrp.tatu-db` |
| .deb | `sudo apt remove tatu-db` |
| portátil | apague a pasta |
| pipx / pip | `pipx uninstall tatu-db` / `pip uninstall tatu-db` |

Nenhum desinstalador apaga seus arquivos `.tatu`.

## 🩺 Problemas comuns

| Sintoma | O que fazer |
|---|---|
| `Não encontrei Python 3.10+` | instale pelo [python.org](https://www.python.org/downloads/), `winget install Python.Python.3.13` (Windows), `brew install python` (macOS) ou o gerenciador da sua distribuição |
| `No module named ensurepip` / "não tem o módulo venv" | Ubuntu/Debian: `sudo apt install python3-venv` |
| `tatu: command not found` / `'tatu' não é reconhecido` | abra um **terminal novo** (o PATH só vale para terminais abertos depois da instalação); no macOS/Linux, confira se `~/.local/bin` está no PATH |
| bordas da tabela viram `?` ou letras esquisitas no Windows | use o **Windows Terminal** (vem no Windows 11) ou rode `chcp 65001` antes |
| o antivírus reclamou do `tatu.exe` | falso positivo comum em executáveis feitos com PyInstaller; use o script ou o código-fonte, se preferir |
| `irm : ... não pôde ser carregado` (política de execução) | rode `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e tente de novo |

Não resolveu? Abra uma [issue](https://github.com/AlefRP/tatu_db/issues/new/choose) contando o sistema, a versão do Python e a mensagem completa.
