; Inno Setup script for the Parquet Explorer Windows installer.
;
; Not invoked directly — `packaging/build_installer.py` builds the PyInstaller
; bundle first and then calls ISCC with /DAppVersion, so the installer version
; always matches parquet_explorer.__version__:
;
;     uv run poe installer

; ArchitecturesAllowed=x64compatible was introduced in 6.3; on older compilers it
; fails with an unhelpful "unsupported value" error, so say so plainly instead.
#if VER < EncodeVer(6,3,0)
  #error Inno Setup 6.3 or newer is required to build this installer.
#endif

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Parquet Explorer"
#define AppExeName "parquet-explorer.exe"
#define AppPublisher "Parquet Explorer contributors"
#define AppUrl "https://github.com/angel-milanov/parquet-explorer"
#define ProgId "ParquetExplorer.parquet"

[Setup]
; Never change AppId — it is how Windows recognises an existing install to upgrade.
AppId={{8F3C1A24-5D6B-4E9A-9C21-7B5E0D4A3F18}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
VersionInfoVersion={#AppVersion}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
LicenseFile=..\LICENSE

; Default to a per-user install so no UAC prompt is needed; the wizard still
; offers an all-users install for anyone who wants one.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=..\dist
OutputBaseFilename=parquet-explorer-{#AppVersion}-windows-x86_64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "associate"; Description: "Open .parquet files with {#AppName}"; GroupDescription: "File associations"

[Files]
Source: "..\dist\parquet-explorer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Register as a handler for .parquet rather than seizing the default, so this
; shows up under "Open with" without stomping on whatever is already associated.
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueName: ""; ValueData: "Parquet file"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associate
Root: HKA; Subkey: "Software\Classes\.parquet\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}\SupportedTypes"; ValueType: string; ValueName: ".parquet"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
