# 📦 Instalação

> [← índice](README.md) · [README](../README.md)

O Tatu DB não tem nenhuma dependência além do Python — e até o Python é opcional: há instaladores e
executáveis prontos para Windows, macOS e Linux. Escolha o caminho que combina com você:

| Jeito | Precisa de Python? | Ideal para |
|---|:-:|---|
| 📥 [Instaladores](#-instaladores) `.exe` `.pkg` `.deb` `.rpm` | ❌ | instalar com dois cliques |
| ⚡ [Script de uma linha](#-script-de-uma-linha) | opcional | ter o comando `tatu` em um minuto, pelo terminal |
| 🎒 [Executável portátil](#-executável-portátil) `.zip` `.tar.gz` | ❌ | usar sem instalar nada (até de um pendrive) |
| 🧑‍💻 [Código-fonte](#-do-código-fonte-recomendado-para-estudar) | ✅ 3.10+ | **estudar o código** (o melhor para a trilha de aprendizado) |
| 🐍 [pip / pipx](#-pip-e-pipx) | ✅ 3.10+ | quem já vive no ecossistema Python |

Todas as versões, com notas e arquivos, ficam na página de **[Releases](https://github.com/AlefRP/tatu_db/releases)**.

---

## 📥 Instaladores

Os links abaixo sempre baixam a **versão mais recente**. O instalador já traz o Python dentro — não
precisa ter nada instalado.

| Sistema | Instalador | Portátil |
|---|---|---|
| 🪟 **Windows 10/11** (x64 — também roda no Windows ARM) | [tatu-windows-x86_64-setup.exe](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-windows-x86_64-setup.exe) | [.zip](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-windows-x86_64.zip) |
| 🍎 **macOS** com Apple Silicon (M1, M2…) | [tatu-macos-arm64.pkg](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-macos-arm64.pkg) | [.tar.gz](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-macos-arm64.tar.gz) |
| 🍎 **macOS** com Intel | [tatu-macos-x86_64.pkg](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-macos-x86_64.pkg) | [.tar.gz](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-macos-x86_64.tar.gz) |
| 🐧 **Debian, Ubuntu, Mint…** (x64) | [tatu-linux-x86_64.deb](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-linux-x86_64.deb) | [.tar.gz](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-linux-x86_64.tar.gz) |
| 🐧 **Fedora, RHEL, Rocky, openSUSE…** (x64) | [tatu-linux-x86_64.rpm](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-linux-x86_64.rpm) | (o mesmo `.tar.gz`) |
| 🐧 **Linux ARM64** (Raspberry Pi 4/5 com sistema 64 bits, servidores ARM) | [.deb](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-linux-arm64.deb) · [.rpm](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-linux-arm64.rpm) | [.tar.gz](https://github.com/AlefRP/tatu_db/releases/latest/download/tatu-linux-arm64.tar.gz) |

**Como instalar cada um:**

- **Windows** — dê dois cliques no `setup.exe`. O assistente instala na sua pasta de usuário (sem pedir
  administrador), cria o atalho **Tatu DB** no menu Iniciar e, se você deixar marcado, põe o `tatu` no PATH.
- **macOS** — dê dois cliques no `.pkg`. O comando fica em `/usr/local/bin/tatu`.
- **Debian/Ubuntu** — `sudo apt install ./tatu-linux-x86_64.deb`
- **Fedora/RHEL** — `sudo dnf install ./tatu-linux-x86_64.rpm`

> [!WARNING]
> Os instaladores **não são assinados digitalmente** (assinatura custa caro para um projeto educacional).
> Por isso o sistema vai desconfiar na primeira vez:
>
> - **Windows** — "O Windows protegeu o computador": clique em **Mais informações → Executar assim mesmo**.
> - **macOS** — "não pode ser aberto porque é de um desenvolvedor não identificado": clique com o **botão
>   direito** no `.pkg` → **Abrir**, ou vá em **Ajustes do Sistema → Privacidade e Segurança → Abrir Mesmo Assim**.
>
> Desconfiar é saudável! Confira o [SHA256](#-conferindo-o-download) do arquivo, ou use o script ou o
> código-fonte — dá para ler cada linha antes.

## ⚡ Script de uma linha

O script escolhe sozinho o melhor jeito de instalar:

- **tem Python 3.10+?** Cria um ambiente virtual só para o Tatu (não mexe no Python do sistema) e instala o pacote;
- **não tem?** Baixa o **executável pronto** do último Release.

Nos dois casos, cria o comando `tatu` sem pedir administrador.

### 🪟 Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.ps1 | iex
```

- Instala em `%LOCALAPPDATA%\tatu-db` e coloca `%LOCALAPPDATA%\tatu-db\bin` no PATH do seu usuário.
- Funciona no Windows PowerShell 5.1 (o que vem com o Windows) e no PowerShell 7.

### 🍎 macOS e 🐧 Linux

```bash
curl -fsSL https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.sh | sh
```

- Instala em `~/.local/share/tatu-db` e cria `~/.local/bin/tatu`.
- Se `~/.local/bin` não estiver no seu PATH, o script mostra a linha exata para colar no `~/.zshrc` ou `~/.bashrc`.

### Opções dos scripts

| | Windows | macOS / Linux |
|---|---|---|
| forçar o executável pronto | `& ([scriptblock]::Create((irm …/install.ps1))) -Binario` | `curl … \| sh -s -- --binario` |
| forçar o modo Python | `… -Python` | `curl … \| sh -s -- --python` |
| uma versão específica | `$env:TATU_REF = "v0.1.0"` antes de rodar | `curl … \| TATU_REF=v0.1.0 sh` |
| escolher a pasta | `$env:TATU_HOME = "D:\ferramentas\tatu"` | `TATU_HOME=… TATU_BIN_DIR=…` |
| escolher o Python | `$env:TATU_PYTHON = "C:\Python313\python.exe"` | `TATU_PYTHON=python3.12` |
| não mexer no PATH | parâmetro `-NoPath` | (o script nunca mexe nos seus arquivos de shell) |

Dentro de um clone do repositório, os scripts instalam a **cópia local**: `sh scripts/install.sh`
ou `.\scripts\install.ps1`.

## 🎒 Executável portátil

Um único arquivo `tatu` (ou `tatu.exe`), sem instalação — veja os links `.zip`/`.tar.gz` na
[tabela acima](#-instaladores).

```bash
# Linux
tar xzf tatu-linux-x86_64.tar.gz
./tatu-linux-x86_64/tatu

# macOS (tire a "quarentena" que o navegador coloca em downloads)
tar xzf tatu-macos-arm64.tar.gz
xattr -d com.apple.quarantine tatu-macos-arm64/tatu
./tatu-macos-arm64/tatu
```

No Windows, descompacte o `.zip` e dê dois cliques em `tatu.exe` (ou rode-o no terminal).

> [!NOTE]
> O executável é um "pacote" com o Python dentro: na primeira execução ele leva um segundinho a mais
> para se desempacotar numa pasta temporária.

## 🧑‍💻 Do código-fonte (recomendado para estudar)

```bash
git clone https://github.com/AlefRP/tatu_db.git
cd tatu_db
python -m tatu          # pronto! (no macOS/Linux talvez seja python3)
```

Nada para instalar: o código que roda é o mesmo que você está lendo. Quer o comando `tatu` apontando
para a sua cópia (e refletindo suas mudanças na hora)? Rode `pip install -e .` dentro da pasta.

## 🐍 pip e pipx

```bash
pipx install git+https://github.com/AlefRP/tatu_db.git     # recomendado: isolado e com o comando tatu
pip install git+https://github.com/AlefRP/tatu_db.git      # dentro de um ambiente virtual seu
```

Cada Release também traz a *wheel* (`tatu_db-<versão>-py3-none-any.whl`), que instala com `pip install`.
Para usar como biblioteca no seu código, o pacote se chama `tatu`: `import tatu`.

---

## ✅ Conferindo

```bash
tatu --version
tatu -c "SELECT 'funcionou!' AS status"
tatu                     # abre o shell; digite .demo
```

## 🔐 Conferindo o download

Cada Release traz um `SHA256SUMS.txt` com a "impressão digital" de cada arquivo. Compare com a do seu download:

```bash
sha256sum tatu-linux-x86_64.deb                   # Linux
shasum -a 256 tatu-macos-arm64.pkg                # macOS
```

```powershell
Get-FileHash .\tatu-windows-x86_64-setup.exe      # Windows
```

## 🗑️ Desinstalando

| Instalou com… | Para remover |
|---|---|
| setup.exe | **Configurações → Aplicativos → Tatu DB → Desinstalar** |
| .pkg | `sudo rm /usr/local/bin/tatu && sudo pkgutil --forget io.github.alefrp.tatu-db` |
| .deb | `sudo apt remove tatu-db` |
| .rpm | `sudo dnf remove tatu-db` |
| script (Windows) | `& ([scriptblock]::Create((irm https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.ps1))) -Uninstall` |
| script (macOS/Linux) | `curl -fsSL https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.sh \| sh -s -- --uninstall` |
| portátil | apague a pasta |
| pipx / pip | `pipx uninstall tatu-db` / `pip uninstall tatu-db` |

Nenhum desinstalador apaga seus arquivos `.tatu`.

## 🩺 Problemas comuns

| Sintoma | O que fazer |
|---|---|
| `Não encontrei Python 3.10+` (usando `--python`) | instale pelo [python.org](https://www.python.org/downloads/), `winget install Python.Python.3.13` (Windows), `brew install python` (macOS) ou o gerenciador da sua distribuição — ou use `--binario` |
| `No module named ensurepip` / "não tem o módulo venv" | Ubuntu/Debian: `sudo apt install python3-venv` (ou deixe o script usar o executável pronto) |
| `tatu: command not found` / `'tatu' não é reconhecido` | abra um **terminal novo** (o PATH só vale para terminais abertos depois da instalação); no macOS/Linux, confira se `~/.local/bin` está no PATH |
| `Não há executável pronto para …` | sua combinação de sistema e processador ainda não tem executável: instale o Python 3.10+ e rode o script de novo |
| bordas da tabela viram `?` ou letras esquisitas no Windows | use o **Windows Terminal** (vem no Windows 11) ou rode `chcp 65001` antes |
| o antivírus reclamou do `tatu.exe` | falso positivo comum em executáveis feitos com PyInstaller; confira o SHA256 ou use o script/código-fonte |
| `irm : ... não pôde ser carregado` (política de execução) | rode `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e tente de novo |

Não resolveu? Abra uma [issue](https://github.com/AlefRP/tatu_db/issues/new/choose) contando o sistema, a versão do Python e a mensagem completa.
