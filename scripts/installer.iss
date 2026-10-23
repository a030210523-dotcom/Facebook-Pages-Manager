; Inno Setup script — Facebook Pages Manager (Phase 6)
; On Windows, after the PyInstaller build:  iscc scripts\installer.iss
; Produces: installer\FacebookPagesManager-Setup.exe
#define MyAppName "Facebook Pages Manager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Muhammad Aamir"
#define MyAppExeName "FacebookPagesManager.exe"

[Setup]
AppId={{8F3A1C44-FPM1-4A2B-9C77-OWNER-AAMIR}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\installer
OutputBaseFilename=FacebookPagesManager-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\FacebookPagesManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
