[Setup]
AppId={{F3E0A8D7-6C86-4C91-96A0-965D104DF3B1}
AppName=Arena Duel
AppVersion=1.0.0
AppVerName=Arena Duel 1.0.0
AppPublisher=BunaTech-G
AppPublisherURL=https://github.com/BunaTech-G/Arena_duel
AppSupportURL=https://github.com/BunaTech-G/Arena_duel/issues
AppUpdatesURL=https://github.com/BunaTech-G/Arena_duel/releases
DefaultDirName={autopf}\Arena Duel
DefaultGroupName=Arena Duel
OutputDir=.
OutputBaseFilename=Setup_ArenaDuel
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\images\arena_duel.ico
UninstallDisplayIcon={app}\ArenaDuel.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
VersionInfoVersion=1.0.0.0
VersionInfoCompany=BunaTech-G
VersionInfoDescription=Arena Duel Windows Setup
VersionInfoProductName=Arena Duel
VersionInfoProductVersion=1.0.0

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "..\dist_release\ArenaDuel\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Arena Duel"; Filename: "{app}\ArenaDuel.exe"; IconFilename: "{app}\ArenaDuel.exe"
Name: "{autodesktop}\Arena Duel"; Filename: "{app}\ArenaDuel.exe"; Tasks: desktopicon; IconFilename: "{app}\ArenaDuel.exe"

[Run]
Filename: "{app}\ArenaDuel.exe"; Description: "Lancer Arena Duel"; Flags: nowait postinstall skipifsilent