@echo off
REM Developer build on Windows: produces dist\Fetchly\Fetchly.exe and (if NSIS is installed) dist\Fetchly-Setup.exe
cd /d "%~dp0\.."
python -m pip install -r requirements.txt pyinstaller pillow || exit /b 1
python tools\sync_version.py || exit /b 1
python tools\make_assets.py || exit /b 1
python -m PyInstaller --noconfirm --clean --windowed --name Fetchly --icon assets\fetchly.ico ^
  --version-file packaging\version_info.txt --add-data "fetchly\ui\assets;fetchly\ui\assets" ^
  --exclude-module tkinter --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml main.py || exit /b 1
xcopy /E /I /Y extension dist\Fetchly\extension >nul
copy /Y packaging\THIRD-PARTY-NOTICES.txt dist\Fetchly\ >nul
where makensis >nul 2>nul && (cd packaging && makensis installer.nsi)
echo Done. See the dist folder.
