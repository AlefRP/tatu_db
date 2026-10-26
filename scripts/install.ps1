<#
.SYNOPSIS
    🐾 Instalador do Tatu DB para Windows.

.DESCRIPTION
    Cria os comandos `tatu` e `toca` sem precisar de administrador. Dois modos:
      - Python:  se houver Python 3.10+, instala num ambiente virtual só do Tatu;
      - Binario: sem Python, baixa o executável pronto do último Release.
    Por padrão o modo é escolhido sozinho.

.EXAMPLE
    irm https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.ps1 | iex

.EXAMPLE
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.ps1))) -Binario

.EXAMPLE
    .\scripts\install.ps1              # de dentro do repositório: instala a cópia local

.EXAMPLE
    .\scripts\install.ps1 -Uninstall   # remove tudo

.NOTES
    Variáveis opcionais: TATU_REF (versão, ex. v0.1.0, ou branch; padrão: main / último
    Release), TATU_HOME (pasta, padrão %LOCALAPPDATA%\tatu-db) e TATU_PYTHON (qual Python usar).
#>
param(
    [switch]$Uninstall,
    [switch]$NoPath,
    [switch]$Binario,
    [switch]$Python,
    [string]$Ref = $(if ($env:TATU_REF) { $env:TATU_REF } else { "main" })
)

$ErrorActionPreference = "Stop"

# O Windows PowerShell 5.1 lê arquivos .ps1 sem BOM como ANSI e estraga os acentos.
# (Com BOM, quem quebra é o `irm | iex`.) Então, rodando de um arquivo no 5.1,
# relemos o próprio script como UTF-8 e o executamos de novo.
$runningFromThisFile = $PSCommandPath -and
    (Select-String -Path $PSCommandPath -Pattern "TATU_RELIDO" -SimpleMatch -Quiet)  # e não de um `irm | iex`
if ($PSVersionTable.PSVersion.Major -lt 6 -and $runningFromThisFile -and -not $env:TATU_RELIDO) {
    $env:TATU_RELIDO = "1"
    $env:TATU_SCRIPT_DIR = $PSScriptRoot
    try {
        $code = [IO.File]::ReadAllText($PSCommandPath, [Text.Encoding]::UTF8)
        & ([scriptblock]::Create($code)) @PSBoundParameters
    } finally {
        Remove-Item Env:TATU_RELIDO, Env:TATU_SCRIPT_DIR -ErrorAction SilentlyContinue
    }
    return
}

$ScriptDir = if ($env:TATU_SCRIPT_DIR) { $env:TATU_SCRIPT_DIR } else { $PSScriptRoot }
$RepoUrl = "https://github.com/AlefRP/tatu_db"
$TatuHome = if ($env:TATU_HOME) { $env:TATU_HOME } else { Join-Path $env:LOCALAPPDATA "tatu-db" }
$TatuHome = [IO.Path]::GetFullPath($TatuHome)
$Venv = Join-Path $TatuHome "venv"
$BinDir = Join-Path $TatuHome "bin"
$Shim = Join-Path $BinDir "tatu.cmd"     # modo Python: "atalho" para o tatu.exe do ambiente virtual
$Exe = Join-Path $BinDir "tatu.exe"      # modo Binario: o executável pronto
$GuiShim = Join-Path $BinDir "toca.cmd"
$GuiExe = Join-Path $BinDir "toca.exe"

function Write-Step($Text) { Write-Host "==> " -ForegroundColor DarkYellow -NoNewline; Write-Host $Text }
function Write-Ok($Text) { Write-Host "OK  " -ForegroundColor Green -NoNewline; Write-Host $Text }
function Stop-WithError($Text) { Write-Host "ERRO: $Text" -ForegroundColor Red; throw $Text }

function Show-Armadillo {
    $art = @'
                 _.-''''''''-._
            _.-''  |  |  |  |  ''-._      __
         .-'   |   |  |  |  |   |   '-.  / /
       .'   |  |   |  |  |  |   |  |   './ /____
      (_____|__|___|__|__|__|___|__|_____)  o   ''-._
  ~~~~~   \__\  \__\          /__/  /__/ '-._______.-'
'@
    Write-Host $art -ForegroundColor DarkYellow
}

# O PATH do usuário é lido e gravado direto no registro, sem expandir variáveis
# como %USERPROFILE% (o que [Environment]::SetEnvironmentVariable faria).
function Get-UserPathEntries {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment")
    $value = $key.GetValue("Path", "", [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    return @($value -split ";" | Where-Object { $_ })
}

function Set-UserPathEntries($Entries) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment", $true)
    $key.SetValue("Path", ($Entries -join ";"), [Microsoft.Win32.RegistryValueKind]::ExpandString)
    # Avisa o Windows que o ambiente mudou: terminais novos já enxergam o PATH novo
    [Environment]::SetEnvironmentVariable("TATU_DB_AVISO", "1", "User")
    [Environment]::SetEnvironmentVariable("TATU_DB_AVISO", $null, "User")
}

# Apaga só o que é do Tatu (nunca a pasta inteira: TATU_HOME pode ter outras coisas).
function Remove-Installation {
    $prefix = $TatuHome.TrimEnd("\") + "\"
    foreach ($path in @($Venv, $Shim, $Exe, $GuiShim, $GuiExe)) {
        $resolved = [IO.Path]::GetFullPath($path)
        if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            Stop-WithError "O caminho $resolved fica fora da pasta do Tatu. Confira TATU_HOME."
        }
        if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
    }
    foreach ($dir in @($BinDir, $TatuHome)) {
        if ((Test-Path -LiteralPath $dir) -and -not (Get-ChildItem -LiteralPath $dir -Force)) {
            Remove-Item -LiteralPath $dir -Force
        }
    }
}

# --------------------------- desinstalar ---------------------------

if ($Uninstall) {
    Write-Step "Removendo o Tatu DB de $TatuHome"
    Remove-Installation
    $entries = Get-UserPathEntries
    $remaining = @($entries | Where-Object { $_.TrimEnd("\") -ne $BinDir.TrimEnd("\") })
    if ($remaining.Count -ne $entries.Count) {
        Set-UserPathEntries $remaining
        Write-Ok "$BinDir removido do PATH"
    }
    Write-Ok "Tatu DB removido. Seus arquivos .tatu continuam onde estavam."
    return
}

# --------------------------- modo Python ---------------------------

function Find-Python {
    # Cada candidato é um comando + argumentos ("py -3" usa o lançador oficial do Windows)
    $candidates = @()
    if ($env:TATU_PYTHON) { $candidates += , @($env:TATU_PYTHON) }
    $candidates += , @("py", "-3")
    $candidates += , @("python")
    $candidates += , @("python3")
    foreach ($candidate in $candidates) {
        $command = $candidate[0]
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { continue }
        $prefix = @($candidate | Select-Object -Skip 1)
        $check = "import sys, venv, ensurepip; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
        try {
            & $command @prefix -c $check 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                # Pergunta ao próprio Python onde ele mora: evita o atalho falso da Microsoft Store
                $path = & $command @prefix -c "import sys; print(sys.executable)"
                if ($LASTEXITCODE -eq 0 -and $path) { return $path.Trim() }
            }
        } catch { }
    }
    return $null
}

function Find-Source {
    # Rodando de dentro de um clone do repositório? Então instala a cópia local.
    if ($ScriptDir) {
        $root = Split-Path -Parent $ScriptDir
        $pyproject = Join-Path $root "pyproject.toml"
        if ((Test-Path $pyproject) -and (Select-String -Path $pyproject -Pattern 'name = "tatu-db"' -Quiet)) {
            return $root
        }
    }
    return "$RepoUrl/archive/$Ref.zip"
}

function Install-WithPython($PythonExe) {
    $pythonVersion = & $PythonExe -c "import platform; print(platform.python_version())"
    Write-Ok "Usando $PythonExe ($pythonVersion)"
    $source = Find-Source
    Write-Step "Criando o ambiente virtual em $Venv"
    Remove-Installation
    New-Item -ItemType Directory -Force -Path $TatuHome | Out-Null
    # "| Out-Host": o que um programa imprime dentro de uma função viraria o valor de retorno dela
    & $PythonExe -m venv $Venv | Out-Host
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Não consegui criar o ambiente virtual." }

    Write-Step "Instalando o Tatu DB ($source)"
    & (Join-Path $Venv "Scripts\python.exe") -m pip install --quiet --disable-pip-version-check --upgrade $source |
        Out-Host
    if ($LASTEXITCODE -ne 0) { Stop-WithError "A instalação falhou. Verifique sua conexão com a internet e tente de novo." }

    # Um tatu.cmd numa pasta só dele: assim o PATH não ganha o python.exe do ambiente virtual
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    Set-Content -Path $Shim -Encoding ascii -Value "@echo off`r`n`"%~dp0..\venv\Scripts\tatu.exe`" %*"
    if (Test-Path -LiteralPath (Join-Path $Venv "Scripts\toca.exe")) {
        Set-Content -Path $GuiShim -Encoding ascii -Value "@echo off`r`n`"%~dp0..\venv\Scripts\toca.exe`" %*"
    }
    return $Shim
}

# --------------------------- modo Binario ---------------------------

function Install-Binary {
    # Executável x64: também roda no Windows ARM, pela emulação do próprio Windows
    $name = "tatu-windows-x86_64"
    $url = if ($Ref -match '^v\d') { "$RepoUrl/releases/download/$Ref/$name.zip" }
           else { "$RepoUrl/releases/latest/download/$name.zip" }
    Write-Step "Baixando o executável ($url)"
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("tatu-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor
            [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = "SilentlyContinue"  # a barra de progresso deixa o download do 5.1 lentíssimo
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile (Join-Path $tmp "tatu.zip")
        } catch {
            Stop-WithError "Não consegui baixar $url ($($_.Exception.Message))"
        }
        Expand-Archive -Path (Join-Path $tmp "tatu.zip") -DestinationPath $tmp -Force
        Remove-Installation
        New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
        Copy-Item (Join-Path $tmp "$name\tatu.exe") $Exe -Force
        # Releases antigos trazem só o shell. O mesmo script continua instalando essas versões.
        $guiSource = Join-Path $tmp "$name\toca.exe"
        if (Test-Path -LiteralPath $guiSource) { Copy-Item -LiteralPath $guiSource $GuiExe -Force }
    } finally {
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd("\") + "\"
        $resolvedTemp = [IO.Path]::GetFullPath($tmp)
        if ($resolvedTemp.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedTemp -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    return $Exe
}

# --------------------------- instalar ---------------------------

Show-Armadillo
$mode = if ($Binario) { "binario" } elseif ($Python) { "python" } else { "auto" }
$pythonExe = $null
if ($mode -ne "binario") {
    Write-Step "Procurando Python 3.10 ou mais novo"
    $pythonExe = Find-Python
}
if ($mode -eq "python" -and -not $pythonExe) {
    Stop-WithError ("Não encontrei Python 3.10+. Instale em https://www.python.org/downloads/ " +
        "(ou: winget install Python.Python.3.13), ou rode com -Binario para usar o executável pronto.")
}
if ($mode -eq "auto" -and -not $pythonExe) {
    Write-Step "Python 3.10+ não encontrado: vou instalar o executável pronto (não precisa de Python)"
    $mode = "binario"
}
$command = if ($mode -eq "binario") { Install-Binary } else { Install-WithPython $pythonExe }

$version = & $command --version
if ($LASTEXITCODE -ne 0) { Stop-WithError "O comando tatu não funcionou depois de instalado." }
Write-Ok "$version instalado em $command"
if ((Test-Path -LiteralPath $GuiShim) -or (Test-Path -LiteralPath $GuiExe)) {
    Write-Ok "Cliente gráfico Toca instalado. Abra com: toca"
}

if ($NoPath) {
    Write-Host "`nPATH não alterado (-NoPath). Rode com:  $command"
    return
}
$entries = Get-UserPathEntries
if ($entries -notcontains $BinDir) {
    Set-UserPathEntries (@($entries) + $BinDir)
    Write-Ok "$BinDir adicionado ao PATH do seu usuário"
}
if (($env:Path -split ";") -notcontains $BinDir) { $env:Path = "$env:Path;$BinDir" }
Write-Host "`nPronto! Abra um terminal novo e rode:  " -NoNewline
Write-Host "tatu" -ForegroundColor DarkYellow -NoNewline
Write-Host "   (e digite .demo)"
