[Setup]
AppId={{B31ABF4F-C8FF-417E-87DB-265888D72165}
AppName={APP_DISP_NAME}
AppVersion={APP_VERSION}
AppVerName={APP_NAME}
AppPublisher={APP_AUTHOR}
AppPublisherURL={APP_URL}
WizardStyle=classic

; Per-user by default, and out of the way of Program Files. {autopf} would
; ask for elevation, and an elevation prompt that gets dismissed leaves the
; user with nothing at all -- no wizard, no window, no error. Here there is
; nothing to elevate, so the wizard always comes up, and the folder page is
; there for anyone who wants it somewhere else.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{APP_NAME}
DefaultGroupName={APP_DISP_NAME}
UninstallDisplayIcon={app}\{APP_NAME}.exe
Compression=lzma2
LZMAUseSeparateProcess=yes
SolidCompression=yes
ShowLanguageDialog=no
VersionInfoVersion={APP_VERSION_NUMERIC}
VersionInfoCompany={APP_AUTHOR}
VersionInfoCopyright=(c) 2021 {APP_AUTHOR}
VersionInfoProductName={APP_DISP_NAME}
VersionInfoProductVersion={APP_VERSION_NUMERIC}
VersionInfoProductTextVersion={APP_VERSION}
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
SourceDir={APP_SRC}
ChangesAssociations=yes

; Ask where to install, always. Left to itself Inno remembers the folder of a
; previous install and skips the page, which is how an old build that used a
; different Python got a whole second runtime dropped on top of the new one --
; two python DLLs in one folder, and the bootloader picks the wrong one.
DisableDirPage=no
UsePreviousAppDir=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion;

; A folder that already held GridPlayer can still hold the runtime of the
; build that was there before -- files this one does not ship, so nothing
; overwrites them. PyInstaller's bootloader takes the first python3xx.dll it
; finds and does not check it against the extensions beside it, so a leftover
; one is not harmless: it is the thing that stops the program from starting.
; Both runtimes are wholly inside these two folders and nowhere else.
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\libVLC"

[Icons]
Name: "{group}\{APP_DISP_NAME}"; Filename: "{app}\{APP_NAME}.exe"; AppUserModelID: "{APP_ID}"
Name: "{group}\{cm:UninstallProgram,{APP_NAME}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{APP_DISP_NAME}"; Filename: "{app}\{APP_NAME}.exe"; AppUserModelID: "{APP_ID}"; Tasks: desktopicon

[Run]
Filename: "{app}\{APP_NAME}.exe"; Flags: nowait postinstall skipifsilent 64bit; Description: "{cm:LaunchProgram,{APP_NAME}}"

[Registry]
{APP_FILE_ASSOCIATIONS}
; HKA, not HKCR -- see generate_file_associations.py. Explorer reads the
; friendly name from whichever classes root the install could write to.
Root: HKA; SubKey: "Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"; ValueType: string; ValueName: "{app}\{APP_NAME}.exe.FriendlyAppName"; ValueData: "{APP_DISP_NAME}"; Flags: uninsdeletevalue
Root: HKA; SubKey: "Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"; ValueType: string; ValueName: "{app}\{APP_NAME}.exe.ApplicationCompany"; ValueData: "{APP_AUTHOR}"; Flags: uninsdeletevalue
