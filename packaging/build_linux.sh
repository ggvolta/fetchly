#!/usr/bin/env bash
# Builds dist/Fetchly-Linux-x86_64.AppImage.
#   packaging/build_linux.sh              (needs Python 3.10+, the packages in requirements.txt and pyinstaller)
#   APPIMAGETOOL=/path/to/appimagetool packaging/build_linux.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
ID=io.github.ggvolta.Fetchly
ARCH="${ARCH:-x86_64}"

"$PY" tools/sync_version.py
"$PY" tools/make_assets.py
rm -rf build dist
"$PY" -m PyInstaller --noconfirm --clean --windowed --name Fetchly \
  --add-data "fetchly/ui/assets:fetchly/ui/assets" \
  --exclude-module tkinter --exclude-module unittest --exclude-module pydoc \
  --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick \
  --exclude-module brotli --exclude-module _brotli --exclude-module chardet \
  main.py

APPDIR=dist/AppDir
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/metainfo" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$APPDIR/usr/share/icons/hicolor/128x128/apps"
mv dist/Fetchly "$APPDIR/usr/lib/fetchly"
"$PY" tools/prune_linux_bundle.py "$APPDIR/usr/lib/fetchly"
cp -r extension "$APPDIR/usr/lib/fetchly/extension"
cp LICENSE packaging/THIRD-PARTY-NOTICES.txt "$APPDIR/usr/lib/fetchly/"
cp packaging/linux/AppRun "$APPDIR/AppRun"
cp packaging/linux/$ID.desktop "$APPDIR/$ID.desktop"
cp packaging/linux/$ID.desktop "$APPDIR/usr/share/applications/"
cp packaging/linux/$ID.metainfo.xml "$APPDIR/usr/share/metainfo/"
cp assets/fetchly.png "$APPDIR/$ID.png"
cp assets/fetchly.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/$ID.png"
cp extension/icons/icon128.png "$APPDIR/usr/share/icons/hicolor/128x128/apps/$ID.png"
ln -sf "$ID.png" "$APPDIR/.DirIcon"

TOOL="${APPIMAGETOOL:-appimagetool}"
ARCH=$ARCH APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "dist/Fetchly-Linux-$ARCH.AppImage"
ls -la dist/*.AppImage
