[Setup]
AppName=Arena Duel
AppVersion=1.0
DefaultDirName={pf}\Arena Duel
DefaultGroupName=Arena Duel
OutputDir=.
OutputBaseFilename=Setup_ArenaDuel
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\images\arena_duel.ico

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "..\dist\ArenaDuel\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Arena Duel"; Filename: "{app}\ArenaDuel.exe"; IconFilename: "{app}\ArenaDuel.exe"
Name: "{autodesktop}\Arena Duel"; Filename: "{app}\ArenaDuel.exe"; Tasks: desktopicon; IconFilename: "{app}\ArenaDuel.exe"

[Run]
Filename: "{app}\ArenaDuel.exe"; Description: "Lancer Arena Duel"; Flags: nowait postinstall skipifsilent