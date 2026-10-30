; Fetchly installer (NSIS 3, Modern UI 2)
Unicode true
ManifestDPIAware true
SetCompressor /SOLID lzma

!define APPNAME   "Fetchly"
!define SHORTNAME "Fetchly"
!ifndef VERSION
  !define VERSION "1.1.2"
!endif
!define PUBLISHER "ggvolta"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Fetchly"
!ifndef SRCDIR
  !define SRCDIR "..\dist\Fetchly"
!endif
!ifndef OUTFILE
  !define OUTFILE "..\dist\Fetchly-Setup-${VERSION}.exe"
!endif

Name "${APPNAME}"
OutFile "${OUTFILE}"
InstallDir "$PROGRAMFILES64\Fetchly"
InstallDirRegKey HKLM "Software\Fetchly" "InstallDir"
RequestExecutionLevel admin
BrandingText "${APPNAME} ${VERSION}"
VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "${APPNAME}"
VIAddVersionKey "FileDescription" "${APPNAME} Setup"
VIAddVersionKey "CompanyName" "${PUBLISHER}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "Copyright (C) 2026 ggvolta"

!include "MUI2.nsh"
!include "x64.nsh"
!include "LogicLib.nsh"

!define MUI_ICON "..\assets\fetchly.ico"
!define MUI_UNICON "..\assets\fetchly.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "wizard.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "wizard.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP "header.bmp"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Welcome to ${APPNAME} ${VERSION} Setup"
!define MUI_WELCOMEPAGE_TEXT "This will install ${APPNAME} on your computer.$\r$\n$\r$\nFetchly speeds up downloads using up to 32 connections, resumes broken downloads, and catches downloads and videos from your browser.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN "$INSTDIR\Fetchly.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${APPNAME}"
!define MUI_COMPONENTSPAGE_NODESC

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "${APPNAME} requires 64-bit Windows 10 or later."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

Function un.onInit
  SetRegView 64
FunctionEnd

Section "${APPNAME}" SecMain
  SectionIn RO
  ; close a running copy so files can be replaced
  nsExec::Exec 'taskkill /F /IM Fetchly.exe'
  Sleep 500
  SetOutPath "$INSTDIR"
  RMDir /r "$INSTDIR\_internal"
  File /r "${SRCDIR}\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Fetchly" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "${UNINSTKEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKLM "${UNINSTKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINSTKEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKLM "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\Fetchly.exe"
  WriteRegStr HKLM "${UNINSTKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "${UNINSTKEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKLM "${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTKEY}" "NoRepair" 1
  SectionGetSize ${SecMain} $0
  WriteRegDWORD HKLM "${UNINSTKEY}" "EstimatedSize" $0
  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\Fetchly.exe" "" "$INSTDIR\Fetchly.exe" 0
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Browser Extension Folder.lnk" "$INSTDIR\extension"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Desktop shortcut" SecDesktop
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\Fetchly.exe" "" "$INSTDIR\Fetchly.exe" 0
SectionEnd

Section "Start Fetchly when Windows starts" SecStartup
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Fetchly" '"$INSTDIR\Fetchly.exe" --tray'
SectionEnd

Section "Uninstall"
  nsExec::Exec 'taskkill /F /IM Fetchly.exe'
  Sleep 500
  Delete "$DESKTOP\${APPNAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APPNAME}"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Fetchly"
  DeleteRegKey HKLM "${UNINSTKEY}"
  DeleteRegKey HKLM "Software\Fetchly"
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\extension"
  Delete "$INSTDIR\Fetchly.exe"
  Delete "$INSTDIR\*.txt"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  MessageBox MB_YESNO|MB_ICONQUESTION "Also remove your Fetchly settings and download list?$\r$\n(Your downloaded files are not touched.)" /SD IDNO IDNO keep
    RMDir /r "$APPDATA\Fetchly"
  keep:
SectionEnd
