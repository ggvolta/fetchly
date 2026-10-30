"""Slim down the PyInstaller output for the Linux AppImage.

1. Remove Qt plugins Fetchly never uses (they drag in QML/Quick, PDF, GTK and more).
2. Remove libraries every Linux desktop already provides. Bundled copies of these break on newer systems,
   for example graphics drivers loaded from the host that need a newer C++ runtime than the bundled one.
   Follows the spirit of the AppImage project's exclude list.
3. Remove libraries nothing left in the bundle needs.

    python tools/prune_linux_bundle.py dist/AppDir/usr/lib/fetchly
"""
import fnmatch
import os
import re
import subprocess
import sys

UNUSED_PLUGINS = [
    "platforminputcontexts/libqtvirtualkeyboardplugin.so",
    "imageformats/libqpdf.so",
    "generic/*",
    "platforms/libqvnc.so", "platforms/libqlinuxfb.so", "platforms/libqeglfs.so", "platforms/libqminimalegl.so",
    "platforms/libqvkkhrdisplay.so",
    "platformthemes/libqgtk3.so",
    "egldeviceintegrations/*",
]

HOST_LIBS = [  # provided by every desktop Linux system
    "libstdc++.so*", "libgcc_s.so*", "libc.so*", "libm.so*", "libdl.so*", "libpthread.so*", "librt.so*",
    "libGL.so*", "libGLX.so*", "libGLdispatch.so*", "libEGL.so*", "libOpenGL.so*", "libgbm.so*", "libdrm.so*",
    "libvulkan.so*", "libX11.so*", "libX11-xcb.so*", "libxcb.so*", "libXau.so*", "libXdmcp.so*",
    "libfontconfig.so*", "libfreetype.so*", "libexpat.so*", "libz.so*", "libdbus-1.so*", "libuuid.so*",
    "libglib-2.0.so*", "libgobject-2.0.so*", "libgio-2.0.so*", "libgmodule-2.0.so*", "libgthread-2.0.so*",
    "libasound.so*", "libpulse*.so*", "libwayland-client.so*", "libwayland-cursor.so*", "libwayland-egl.so*",
    "libsystemd.so*", "libudev.so*", "libselinux.so*", "libmount.so*", "libblkid.so*", "libgcrypt.so*",
    "libgpg-error.so*", "libcap.so*", "liblzma.so*", "liblz4.so*", "libzstd.so*", "libbz2.so*", "libpcre*.so*",
    "libffi.so*",
]


def is_elf(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


def needed(path):
    try:
        out = subprocess.run(["readelf", "-d", path], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return set(re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", out))


def main(root):
    removed = 0
    plugins = os.path.join(root, "_internal", "PySide6", "Qt", "plugins")
    for pattern in UNUSED_PLUGINS:
        d, name = os.path.split(pattern)
        folder = os.path.join(plugins, d)
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            if fnmatch.fnmatch(f, name):
                os.remove(os.path.join(folder, f))
                removed += 1

    libdirs = [os.path.join(root, "_internal"), os.path.join(root, "_internal", "PySide6", "Qt", "lib")]
    for d in libdirs:
        for f in os.listdir(d):
            if any(fnmatch.fnmatch(f, p) for p in HOST_LIBS) and os.path.isfile(os.path.join(d, f)):
                os.remove(os.path.join(d, f))
                removed += 1

    # Orphan sweep: keep only libraries reachable from the program, Python extensions and remaining plugins.
    libs = {}
    for d in libdirs:
        for f in os.listdir(d):
            p = os.path.join(d, f)
            if ".so" in f and os.path.isfile(p) and is_elf(p) and not f.endswith((".abi3.so",)) \
                    and ".cpython-" not in f:
                libs.setdefault(f, []).append(p)
    roots = [os.path.join(root, "Fetchly")]
    for dirpath, _, files in os.walk(os.path.join(root, "_internal")):
        for f in files:
            p = os.path.join(dirpath, f)
            if (f.endswith(".abi3.so") or ".cpython-" in f or f.startswith("libpython")
                    or dirpath.startswith(plugins)) and is_elf(p):
                roots.append(p)
    keep, todo = set(), list(roots)
    while todo:
        for dep in needed(todo.pop()):
            if dep in libs and dep not in keep:
                keep.add(dep)
                todo.extend(libs[dep])
    for name, paths in libs.items():
        if name not in keep and not name.startswith("libpython"):
            for p in paths:
                os.remove(p)
                removed += 1
    print(f"pruned {removed} files")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dist/AppDir/usr/lib/fetchly")
