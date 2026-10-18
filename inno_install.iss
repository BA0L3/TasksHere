#define AppName "TasksHere"
#define AppVersion "1.1.0"
#define AppPublisher "BA0L3"
#define DistDir "build\main_gui.dist"

[Setup]
AppId={{1EDA2C1E-4BC5-4721-BC17-479A8F8C5C14}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=build\installer
OutputBaseFilename=TasksHere-Setup-{#AppVersion}
SetupIconFile=Datas\assets\TaskHere.ico
UninstallDisplayIcon={app}\Datas\assets\TaskHere.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; \
    GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; \
    Excludes: "Datas\Tasks.json,Datas\settings.json,Datas\logs\*"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\TasksHere"; Filename: "{app}\main_gui.exe"; \
    WorkingDir: "{app}"; IconFilename: "{app}\Datas\assets\TaskHere.ico"
Name: "{autodesktop}\TasksHere"; Filename: "{app}\main_gui.exe"; \
    WorkingDir: "{app}"; IconFilename: "{app}\Datas\assets\TaskHere.ico"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\main_gui.exe"; WorkingDir: "{app}"; \
    Description: "Launch TasksHere"; \
    Flags: nowait postinstall skipifsilent