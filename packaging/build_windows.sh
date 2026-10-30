#!/usr/bin/env bash
# Builds the Windows release (Fetchly.exe + installer) from Linux using Wine and a Windows Python.
#   WINPY=/opt/winpy packaging/build_windows.sh
# On Windows itself use packaging\build.bat instead.
set -euo pipefail
cd "$(dirname "$0")/.."
WINPY="${WINPY:-/opt/winpy}"
export WINEDEBUG=-all WINEPREFIX="${WINEPREFIX:-/opt/wineprefix}"
# conda-style Pythons keep libffi/OpenSSL/etc. in Library\bin; PyInstaller must see them to bundle them
export WINEPATH="Z:${WINPY//\//\\}\\Library\\bin"
VERSION=$(python3 -c "import fetchly;print(fetchly.__version__)")

python3 tools/sync_version.py
python3 tools/make_assets.py
rm -rf build dist
wine "$WINPY/python.exe" -m PyInstaller --noconfirm --clean --windowed --name Fetchly \
  --icon assets\\fetchly.ico --version-file packaging\\version_info.txt \
  --add-data "fetchly\\ui\\assets;fetchly\\ui\\assets" \
  --exclude-module tkinter --exclude-module unittest --exclude-module pydoc \
  --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick \
  main.py </dev/null 2>&1 | cat
cp -r extension dist/Fetchly/extension
cp packaging/THIRD-PARTY-NOTICES.txt LICENSE dist/Fetchly/
(cd packaging && makensis -V2 -DSRCDIR=../dist/Fetchly -DOUTFILE=../dist/Fetchly-Setup-$VERSION.exe -DVERSION=$VERSION installer.nsi)
(cd dist && rm -f Fetchly-$VERSION-portable.zip && zip -qr Fetchly-$VERSION-portable.zip Fetchly)
(cd extension && rm -f ../dist/Fetchly-Extension-$VERSION.zip && zip -qr ../dist/Fetchly-Extension-$VERSION.zip .)
ls -la dist
