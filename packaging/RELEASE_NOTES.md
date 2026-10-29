Streaming videos now save as MKV.

**Download**
- **Fetchly-Setup-1.1.0.exe** installs Fetchly with Start menu and desktop shortcuts (64-bit Windows 10 or 11).
- **Fetchly-1.1.0-portable.zip** runs without installing: unzip it and open `Fetchly.exe`.
- **Fetchly-Extension-1.1.0.zip** is the browser extension, also included in the installer at `C:\Program Files\Fetchly\extension`.

The installer isn't code-signed yet, so Windows SmartScreen may warn you the first time. Choose **More info**, then **Run anyway**.

**In this version**
- Streaming (HLS) videos are saved as **MKV** instead of a raw `.ts` file. The pieces are joined and converted
  without re-encoding, so quality is unchanged and the video plays and seeks smoothly in VLC and other players.
  Pick MKV, MP4 or TS in **Options → Videos**.
- Fetchly now finds ffmpeg wherever it's installed (PATH, winget, Scoop, Chocolatey, `C:\ffmpeg`, VidSnag), and
  if there's none, downloads it once (about 200 MB) the first time a video needs converting. This can be turned
  off in **Options → Videos**.
- If a video can't be converted, the Download complete window says why.
