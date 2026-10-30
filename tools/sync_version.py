"""Copy the version from fetchly/__init__.py into every file that repeats it, so the app, installer and
extension always agree (code signing checks that the product version matches).

    python tools/sync_version.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    init = open(os.path.join(ROOT, "fetchly", "__init__.py"), encoding="utf-8").read()
    version = re.search(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', init)
    if not version:
        sys.exit("No x.y.z __version__ in fetchly/__init__.py")
    a, b, c = version.groups()
    v3, v4 = f"{a}.{b}.{c}", f"{a}.{b}.{c}.0"

    path = os.path.join(ROOT, "packaging", "version_info.txt")
    s = open(path, encoding="utf-8").read()
    s = re.sub(r"filevers=\([^)]*\)", f"filevers=({a}, {b}, {c}, 0)", s)
    s = re.sub(r"prodvers=\([^)]*\)", f"prodvers=({a}, {b}, {c}, 0)", s)
    s = re.sub(r"StringStruct\('(FileVersion|ProductVersion)', '[^']*'\)", rf"StringStruct('\1', '{v4}')", s)
    open(path, "w", encoding="utf-8").write(s)

    path = os.path.join(ROOT, "packaging", "installer.nsi")
    s = open(path, encoding="utf-8").read()
    s = re.sub(r'(!define VERSION ")[^"]*(")', rf"\g<1>{v3}\2", s)
    open(path, "w", encoding="utf-8").write(s)

    path = os.path.join(ROOT, "extension", "manifest.json")
    m = json.load(open(path, encoding="utf-8"))
    if m.get("version") != v3:
        s = open(path, encoding="utf-8").read()
        s = re.sub(r'("version"\s*:\s*")[^"]*(")', rf"\g<1>{v3}\2", s, count=1)
        open(path, "w", encoding="utf-8").write(s)
    print(f"version {v3}")


if __name__ == "__main__":
    main()
