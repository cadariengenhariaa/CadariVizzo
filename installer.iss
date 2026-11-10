; Script do Inno Setup para gerar o instalador do Cadari Vizzo.
; Compilar com: ISCC.exe installer.iss
; (gera dist_installer\CadariVizzo_Setup.exe a partir de dist\CadariVizzo\,
; que precisa já estar construído via PyInstaller + VisualizadorCadari.spec)

#define MyAppName "Cadari Vizzo"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Cadari Engenharia"
#define MyAppExeName "CadariVizzo.exe"

[Setup]
AppId={{B3F2C9A1-6D4E-4B8A-9C2F-1A7E5D3B8F6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Instala só para o usuário atual, sem precisar de permissão de administrador
; — importante num ambiente corporativo onde nem todo mundo tem acesso admin.
DefaultDirName={localappdata}\Programs\{#MyAppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=CadariVizzo_Setup
SetupIconFile=assets\icone_cadari_vizzo.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
Source: "dist\CadariVizzo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o {#MyAppName} agora"; Flags: nowait postinstall skipifsilent
