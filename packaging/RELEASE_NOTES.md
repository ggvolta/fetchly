Fetchly now stays out of your way in the system tray, and download windows work on their own.

**Download**
- **Fetchly-Setup-1.1.2.exe** installs Fetchly with Start menu and desktop shortcuts (64-bit Windows 10 or 11).
- **Fetchly-1.1.2-portable.zip** runs without installing: unzip it and open `Fetchly.exe`.
- **Fetchly-Extension-1.1.2.zip** is the browser extension, also included in the installer at `C:\Program Files\Fetchly\extension`.

The installer isn't code-signed yet, so Windows SmartScreen may warn you the first time. Choose **More info**, then **Run anyway**. See the [code signing policy](https://github.com/ggvolta/fetchly/blob/main/CODE_SIGNING_POLICY.md).

**In this version**
- Download windows are now independent windows with their own taskbar button, which shows the progress
  (for example *29% Episode 21.mp4*). You no longer need the main Fetchly window open to see or reach them.
- Minimizing or closing the main window sends Fetchly to the system tray. Downloads keep running, and new
  downloads from your browser open only their own window. Click the tray icon to open Fetchly again.
- The tray icon shows a green dot while something is downloading.
- Windows opened from the tray menu, such as **Add URL**, also get their own taskbar button.
- To have minimize and close work the old way, turn off **Options › General › Keep Fetchly in the system tray**.

Also includes 1.1.1 (the video list in the browser no longer opens off-screen) and 1.1.0 (streaming videos save
as MKV).
