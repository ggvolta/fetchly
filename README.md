<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/art/banner-dark.png">
    <img src="docs/art/banner-light.png" width="100%" alt="Fetchly: faster downloads, up to 32 connections per file">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/ggvolta/fetchly/releases/latest"><img src="https://img.shields.io/github/v/release/ggvolta/fetchly?style=flat-square&label=release&color=FFB33A&labelColor=161845" alt="Latest release"></a>
  <a href="https://github.com/ggvolta/fetchly/releases"><img src="https://img.shields.io/github/downloads/ggvolta/fetchly/total?style=flat-square&color=3D42C9&labelColor=161845" alt="Downloads"></a>
  <img src="https://img.shields.io/badge/Windows-10%20and%2011-3D42C9?style=flat-square&labelColor=161845" alt="Windows 10 and 11">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-3D42C9?style=flat-square&labelColor=161845" alt="MIT license"></a>
  <a href="https://github.com/ggvolta/fetchly/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/ggvolta/fetchly/ci.yml?branch=main&style=flat-square&label=tests&labelColor=161845" alt="Tests"></a>
</p>

<p align="center">
  <a href="https://github.com/ggvolta/fetchly/releases/latest">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/art/download-dark.png">
      <img src="docs/art/download-light.png" width="300" alt="Download for Windows">
    </picture>
  </a>
</p>

Fetchly is a download manager for Windows. It splits each file into pieces and downloads them over many
connections at once, picks up where it left off when a download breaks, and takes over downloads from your
browser so you don't have to copy links by hand.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/art/framed-main-dark.png">
    <img src="docs/art/framed-main-light.png" width="100%" alt="The Fetchly main window with a list of downloads">
  </picture>
</p>

## Why it's faster

Many servers cap the speed of each connection. A browser opens one; Fetchly opens up to 32 and gives each a
piece of the file. When a connection finishes its piece, it takes over half of whatever is left of the
slowest one, so every connection stays busy until the last byte.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/art/speed-dark.png">
    <img src="docs/art/speed-light.png" width="100%" alt="A 64 MB file takes 33.7 seconds over one connection and 4.2 seconds with Fetchly's eight">
  </picture>
</p>

If one browser download already fills your internet connection, Fetchly can't go beyond it. It helps with
servers that limit each connection, with file hosts and mirrors, and on unstable connections where resuming
saves you from starting over.

## What it does

- Downloads with up to 32 connections per file, and keeps them all busy with dynamic splitting.
- Resumes after a pause, a lost connection, a crash or a restart. If a link expires, paste a fresh one in
  **Properties** and carry on.
- Takes over browser downloads of the file types you choose, with the page's cookies so downloads that need
  you to be signed in still work. Hold **Alt** while clicking a link to let the browser handle that one.
- Shows a **Download this video** button over videos on web pages (direct video files and HLS streams).
  Streaming videos are saved as **MKV** (or MP4, in **Options → Videos**), converted without re-encoding so
  they keep full quality and play and seek smoothly. Fetchly uses ffmpeg for this: it finds an existing copy
  or downloads one the first time it's needed.
- Adds **Download with Fetchly**, **Download all links** and **Download selected links** to the right-click
  menu in your browser.
- Sorts files into Compressed, Documents, Music, Programs and Video, each with its own folder.
- Runs a download queue on a schedule, then exits or shuts the computer down when it's done.
- Also: a speed limiter, batch downloads (`photo*.jpg` from 001 to 100), link import and export, clipboard
  monitoring, drag and drop, proxy support, and light and dark themes that follow Windows.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/art/framed-progress-dark.png">
    <img src="docs/art/framed-progress-light.png" width="49%" alt="Progress window showing eight connections">
  </picture>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/art/framed-download-info-dark.png">
    <img src="docs/art/framed-download-info-light.png" width="49%" alt="Download File Info window">
  </picture>
</p>

## Install

1. Download **Fetchly-Setup-1.0.0.exe** from the [latest release](https://github.com/ggvolta/fetchly/releases/latest).
   It needs 64-bit Windows 10 or 11.
2. Run it. The installer isn't code-signed yet, so Windows SmartScreen may warn you: choose
   **More info**, then **Run anyway**.

To skip the installer, download **Fetchly-1.0.0-portable.zip**, unzip it anywhere and run `Fetchly.exe`.

## Browser extension

The extension works in Chrome, Edge, Brave, Opera and Vivaldi. Until it's listed in the browser stores, add it
once by hand. Fetchly walks you through this the first time it starts (also under **Help > Browser
integration**):

1. Open `chrome://extensions` (in Edge, `edge://extensions`) and turn on **Developer mode**.
2. Click **Load unpacked** and select `C:\Program Files\Fetchly\extension`.

The status bar in Fetchly shows **Browser connected** once it works. The extension only talks to the Fetchly
app on your own computer; see the [privacy policy](PRIVACY.md).

## Benchmarks

Measured with [`tools/benchmark.py`](tools/benchmark.py), comparing Fetchly with
[aria2](https://aria2.github.io/), a well-known multi-connection downloader written in C++.

| Connections | 1 | 4 | 8 | 16 | 32 |
|---|---|---|---|---|---|
| Fetchly | 2.0 MB/s | 8.0 MB/s | 15.9 MB/s | 31.3 MB/s | 59.9 MB/s |
| aria2 | 2.0 MB/s | 7.9 MB/s | 15.7 MB/s | 30.7 MB/s | 30.6 MB/s* |

Server limited to 2 MB/s per connection, 64 MB file. \*aria2 opens at most 16 connections per server.
With no limit on a local server, Fetchly reaches 520 to 780 MB/s, well beyond any home connection.

## Build from source

```bash
pip install -r requirements.txt
python main.py                  # run Fetchly
python -m tests.test_engine     # run the engine tests
```

Each version tag is built into the installer, portable zip and extension zip by
[GitHub Actions](.github/workflows/release.yml). To build on your own Windows machine, run
`packaging\build.bat` (the setup file also needs [NSIS](https://nsis.sourceforge.io/)).

<details>
<summary>Project layout</summary>

```
main.py               entry point: one running copy, --tray starts minimized
fetchly/engine.py     segmented HTTP engine, HLS streams, speed limiter
fetchly/manager.py    download list, queue, scheduler, saved state in %APPDATA%\Fetchly
fetchly/server.py     local API on 127.0.0.1:7614 that the extension talks to
fetchly/ui/           the Qt interface
extension/            Chromium extension (Manifest V3)
packaging/            installer script and build files
tools/                benchmark, icon and artwork generators
```
</details>

## Limitations

- YouTube, which serves audio and video as separate streams, and DRM-protected services aren't supported.
- Firefox support is planned.
- No FTP, BitTorrent or website grabber.

## Contributing

Bug reports and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Fetchly is released under the [MIT License](LICENSE). It uses Qt for Python, Fluent UI System Icons and the
Bricolage Grotesque typeface; see [third-party notices](packaging/THIRD-PARTY-NOTICES.txt).
