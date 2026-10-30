# Privacy Policy

_Last updated: October 30, 2026_

Fetchly (the Windows app and the Fetchly browser extension) does not collect, sell or share your personal data. There are no accounts, no analytics and no telemetry.

## What the browser extension does

- **Downloads you start.** When you download a file of a type you selected, the extension sends that file's address, the page you downloaded it from, the file name and size to the **Fetchly app running on your own computer** (address `127.0.0.1`). It never sends this anywhere else.
- **Cookies.** So that downloads from sites you are signed in to keep working, the extension reads the cookies for the address being downloaded and passes them to the Fetchly app on your computer, which uses them only to request that file from the same website. Cookies are not stored by the extension and are never sent to us or to any third party.
- **Videos on a page.** The extension notices video and audio files the page loads so it can offer a *Download this video* button. This list is kept in your browser's memory for that tab only and is cleared when you leave the page.
- **Settings.** Your on/off switch and port number are saved in your browser's extension storage.

## What the Windows app does

The app connects to the websites you download from, plus one other place described below. Your download list and settings are stored on your computer in `%APPDATA%\Fetchly`. Uninstalling Fetchly offers to delete them.

**ffmpeg download (one time, can be turned off).** To save streaming videos as MKV or MP4, Fetchly uses the free ffmpeg program. If ffmpeg isn't already installed, the first time you download a streaming video Fetchly downloads it once (about 200 MB) from GitHub, at `https://github.com/yt-dlp/FFmpeg-Builds/releases`, and keeps it in `%APPDATA%\Fetchly`. Like any download, this request reveals your IP address to GitHub; Fetchly sends nothing else. GitHub's handling of that request is covered by the [GitHub Privacy Statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement). Turn this off in **Options › Videos** by unticking *Download ffmpeg automatically*; streaming videos are then saved as `.ts` unless you install ffmpeg yourself.

## Data shared with third parties

None. Fetchly has no servers of its own and sends no data about you or your downloads to the Fetchly project or anyone else.

## Contact

Questions or concerns: open an issue at https://github.com/ggvolta/fetchly/issues
