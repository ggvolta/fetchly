Fetchly now runs on Linux as well as Windows.

### Which file do I need?

| Your computer | Download this |
|---|---|
| **Windows 10 or 11** | **Fetchly-Windows-Setup.exe** (recommended). Installs Fetchly with Start menu and desktop shortcuts. |
| Windows, without installing | **Fetchly-Windows-Portable.zip**. Unzip it anywhere and open `Fetchly.exe`. |
| **Linux** (64-bit) | **Fetchly-Linux-x86_64.AppImage**. One file, runs on Ubuntu 22.04 and newer, Fedora, Debian, Mint, Arch and most other distributions. |

You only need one file. The browser extension is already included in all three, so **Fetchly-Browser-Extension.zip** is only for people who want to inspect it or load it on its own.

**Windows:** the installer isn't code-signed yet, so SmartScreen may warn you the first time. Choose **More info**, then **Run anyway**. See the [code signing policy](https://github.com/ggvolta/fetchly/blob/main/CODE_SIGNING_POLICY.md).

**Linux:** right-click the AppImage, open **Properties** and turn on **Allow executing file as program** (or run `chmod +x Fetchly-Linux-x86_64.AppImage`), then double-click it. Fetchly offers to add itself to your applications menu. More help is in the [install guide](https://github.com/ggvolta/fetchly#linux).

### In this version

- **Linux support.** Everything works the same as on Windows: multi-connection downloads, browser integration, video downloads, the tray icon, the scheduler and the queue. Fetchly can add itself to your applications menu and start when you sign in, opens downloaded files with your usual apps, and shows file icons from your desktop theme. On GNOME without a tray, closing the window keeps Fetchly running in the dock.
- On Linux, Fetchly downloads ffmpeg for streaming videos automatically when it's needed, the same as on Windows.
- Settings and message windows no longer block the download windows. You can keep watching and controlling downloads while **Options** or another window is open.
- Release files now have the same name in every version, so links to the latest download always work.
