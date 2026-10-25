<#
.SYNOPSIS
    🐾 Instalador do Tatu DB para Windows.

.DESCRIPTION
    Instala o Tatu DB num ambiente virtual só dele e cria o comando `tatu`.
    Não precisa de administrador e não mexe no Python do sistema.

.EXAMPLE
    irm https://raw.githubusercontent.com/AlefRP/tatu_db/main/scripts/install.ps1 | iex

.EXAMPLE
    .\scripts\install.ps1              # de dentro do repositório: instala a cópia local

.EXAMPLE
    .\scripts\install.ps1 -Uninstall   # remove tudo

.NOTES
    Variáveis opcionais: TATU_REF (branch ou tag, padrão main), TATU_HOME (pasta de
    instalação, padrão %LOCALAPPDATA%\tatu-db) e TATU_PYTHON (qual Python usar).
#>
param(
    [switch]$Uninstall,
    [switch]$NoPath,
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
$Venv = Join-Path $TatuHome "venv"
$BinDir = Join-Path $TatuHome "bin"

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

# ─────────────────────────── desinstalar ───────────────────────────

if ($Uninstall) {
    Write-Step "Removendo o Tatu DB de $TatuHome"
    if (Test-Path $TatuHome) { Remove-Item -Recurse -Force $TatuHome }
    $entries = Get-UserPathEntries
    $remaining = @($entries | Where-Object { $_.TrimEnd("\") -ne $BinDir.TrimEnd("\") })
    if ($remaining.Count -ne $entries.Count) {
        Set-UserPathEntries $remaining
        Write-Ok "$BinDir removido do PATH"
    }
    Write-Ok "Tatu DB removido. Seus arquivos .tatu continuam onde estavam."
    return
}

# ─────────────────────────── instalar ───────────────────────────

function Find-Python {
    # Cada candidato é um comando + argumentos ("py -3" usa o lançador oficial do Windows)
    $candidates = @()
    if ($env:TATU_PYTHON) { $candidates += , @($env:TATU_PYTHON) }
    $candidates += , @("py", "-3")
    $candidates += , @("python")
    $candidates += , @("python3")
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $prefix = @($candidate | Select-Object -Skip 1)
        $check = "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
        try {
            & $exe @prefix -c $check 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                # Pergunta ao próprio Python onde ele mora: evita o atalho falso da Microsoft Store
                $path = & $exe @prefix -c "import sys; print(sys.executable)"
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

Show-Armadillo
Write-Step "Procurando Python 3.10 ou mais novo"
$python = Find-Python
if (-not $python) {
    Stop-WithError ("Não encontrei Python 3.10+. Instale em https://www.python.org/downloads/ " +
        "(ou: winget install Python.Python.3.13) e rode este instalador de novo.")
}
$pythonVersion = & $python -c "import platform; print(platform.python_version())"
Write-Ok "Usando $python ($pythonVersion)"

$source = Find-Source
Write-Step "Criando o ambiente virtual em $Venv"
if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
New-Item -ItemType Directory -Force -Path $TatuHome | Out-Null
& $python -m venv $Venv
if ($LASTEXITCODE -ne 0) { Stop-WithError "Não consegui criar o ambiente virtual." }

Write-Step "Instalando o Tatu DB ($source)"
$venvPython = Join-Path $Venv "Scripts\python.exe"
& $venvPython -m pip install --quiet --disable-pip-version-check --upgrade $source
if ($LASTEXITCODE -ne 0) { Stop-WithError "A instalação falhou. Verifique sua conexão com a internet e tente de novo." }

# Um "atalho" tatu.cmd numa pasta só dele: assim o PATH não ganha o python.exe do ambiente virtual
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$shim = Join-Path $BinDir "tatu.cmd"
Set-Content -Path $shim -Encoding ascii -Value "@echo off`r`n`"%~dp0..\venv\Scripts\tatu.exe`" %*"
$version = & $shim --version
Write-Ok "$version instalado em $shim"

if ($NoPath) {
    Write-Host "`nPATH não alterado (-NoPath). Rode com:  $shim"
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
