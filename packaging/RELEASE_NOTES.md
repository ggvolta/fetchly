Fixes the video list in the browser opening off-screen.

**Download**
- **Fetchly-Setup-1.1.1.exe** installs Fetchly with Start menu and desktop shortcuts (64-bit Windows 10 or 11).
- **Fetchly-1.1.1-portable.zip** runs without installing: unzip it and open `Fetchly.exe`.
- **Fetchly-Extension-1.1.1.zip** is the browser extension, also included in the installer at `C:\Program Files\Fetchly\extension`.

The installer isn't code-signed yet, so Windows SmartScreen may warn you the first time. Choose **More info**, then **Run anyway**.

**In this version**
- When a page has several videos, the **Download this video** list now opens on whichever side of the button has
  room. Before, it always opened downwards, so with the button in the bottom corner it disappeared under the
  Windows taskbar.
- The list stays inside the browser window and scrolls when a page has many videos.
- Click anywhere else on the page or press **Esc** to close the list. You can also move through it with **Tab**
  and choose a video with **Enter**.

**Already have the extension?** After installing, open `chrome://extensions` (or `edge://extensions`) and click
the reload button on Fetchly, then refresh the page you're on.

Also includes everything from 1.1.0: streaming videos save as MKV, and Fetchly finds or downloads ffmpeg for you.
