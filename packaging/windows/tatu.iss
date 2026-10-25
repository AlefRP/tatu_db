; 🪟 Instalador do Tatu DB para Windows (Inno Setup 6.3+)
;
; Primeiro gere o executável, depois compile este script:
;   python packaging\build_binary.py
;   iscc /DAppVersion=0.1.0 packaging\windows\tatu.iss
;
; Resultado: dist\release\tatu-<versão>-windows-x86_64-setup.exe
; Instala sem pedir administrador (na pasta do usuário), cria atalho no menu
; Iniciar e, se você quiser, coloca o comando `tatu` no PATH.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8F1C5E2A-7B3D-4C9E-A1F0-5D2B6E8C4A17}
AppName=Tatu DB
AppVersion={#AppVersion}
AppVerName=Tatu DB {#AppVersion}
AppPublisher=AlefRP
AppPublisherURL=https://github.com/AlefRP/tatu_db
AppSupportURL=https://github.com/AlefRP/tatu_db/issues
AppUpdatesURL=https://github.com/AlefRP/tatu_db/releases
DefaultDirName={autopf}\Tatu DB
DefaultGroupName=Tatu DB
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesEnvironment=yes
LicenseFile=..\..\LICENSE
SetupIconFile=..\icons\tatu.ico
UninstallDisplayIcon={app}\tatu.ico
UninstallDisplayName=Tatu DB {#AppVersion}
OutputDir=..\..\dist\release
OutputBaseFilename=tatu-{#AppVersion}-windows-x86_64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "addtopath"; Description: "Adicionar o comando tatu ao PATH (recomendado)"; GroupDescription: "Opções:"
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Opções:"; Flags: unchecked

[Files]
Source: "..\..\build\pyinstaller\dist\tatu.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\icons\tatu.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Tatu DB"; Filename: "{app}\tatu.exe"; IconFilename: "{app}\tatu.ico"; WorkingDir: "{userdocs}"; Comment: "Shell interativo do Tatu DB"
Name: "{group}\Desinstalar o Tatu DB"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Tatu DB"; Filename: "{app}\tatu.exe"; IconFilename: "{app}\tatu.ico"; WorkingDir: "{userdocs}"; Tasks: desktopicon

[Run]
Filename: "{app}\tatu.exe"; Description: "Abrir o Tatu DB agora"; Flags: nowait postinstall skipifsilent

[Code]
{ O PATH fica em HKCU (instalação só para você) ou em HKLM (para todos). }
function PathRootKey: Integer;
begin
  if IsAdminInstallMode then
    Result := HKEY_LOCAL_MACHINE
  else
    Result := HKEY_CURRENT_USER;
end;

function PathSubKey: string;
begin
  if IsAdminInstallMode then
    Result := 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
  else
    Result := 'Environment';
end;

function PathContains(Paths, Dir: string): Boolean;
begin
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') > 0;
end;

procedure AddToPath(Dir: string);
var
  Paths: string;
begin
  if not RegQueryStringValue(PathRootKey, PathSubKey, 'Path', Paths) then
    Paths := '';
  if PathContains(Paths, Dir) then
    exit;
  if (Paths <> '') and (Copy(Paths, Length(Paths), 1) <> ';') then
    Paths := Paths + ';';
  RegWriteExpandStringValue(PathRootKey, PathSubKey, 'Path', Paths + Dir);
end;

procedure RemoveFromPath(Dir: string);
var
  Paths: string;
begin
  if not RegQueryStringValue(PathRootKey, PathSubKey, 'Path', Paths) then
    exit;
  if not PathContains(Paths, Dir) then
    exit;
  Paths := ';' + Paths + ';';
  StringChangeEx(Paths, ';' + Dir + ';', ';', True);
  while Pos(';;', Paths) > 0 do
    StringChangeEx(Paths, ';;', ';', True);
  if Copy(Paths, 1, 1) = ';' then
    Delete(Paths, 1, 1);
  if Copy(Paths, Length(Paths), 1) = ';' then
    Delete(Paths, Length(Paths), 1);
  RegWriteExpandStringValue(PathRootKey, PathSubKey, 'Path', Paths);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then
    AddToPath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromPath(ExpandConstant('{app}'));
end;
