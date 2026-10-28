# Store listing kit (Chrome Web Store and Microsoft Edge Add-ons)

Everything below is ready to copy into the store forms. Upload `Fetchly-Extension-<version>.zip`
from the GitHub release (or zip the contents of the `extension` folder).

---

## Store listing tab

**Name** (comes from the extension): `Fetchly Download Manager`

**Summary** (132 characters max):
> Send downloads, links and videos to the Fetchly app for faster, resumable downloads with up to 32 connections.

**Category:** Tools (Chrome: *Productivity → Tools*; Edge: *Productivity*)

**Language:** English

**Description:**

> Fetchly connects your browser to the free, open-source Fetchly download manager for Windows.
>
> When you download a file, Fetchly takes over and downloads it using up to 32 connections at once, so it finishes faster on servers that limit each connection. Paused, interrupted or failed downloads resume where they stopped — even after restarting your computer.
>
> WHAT THE EXTENSION DOES
> • Hands downloads of the file types you choose (zip, exe, iso, mp4, pdf and more) to Fetchly automatically
> • Keeps sign-in-protected downloads working by passing the page's cookies to the Fetchly app on your computer
> • Shows a "Download this video" button over videos on web pages (direct video files and HLS streams)
> • Adds right-click options: Download with Fetchly, Download all links, Download selected links
> • Hold Alt while clicking a link to let the browser download it instead
>
> REQUIREMENTS
> This extension needs the Fetchly desktop app (free, Windows 10/11): https://github.com/ggvolta/fetchly/releases/latest
>
> PRIVACY
> The extension only talks to the Fetchly app on your own computer (127.0.0.1). No accounts, no analytics, no data sent to any server. Full policy: https://github.com/ggvolta/fetchly/blob/main/PRIVACY.md
>
> OPEN SOURCE
> Source code (MIT license): https://github.com/ggvolta/fetchly
>
> Fetchly does not download from YouTube or DRM-protected streaming services.

**Images** (in `store/images`):
- Store icon: `icon-128.png`
- Screenshots (1280×800): `1-main.png`, `2-catch.png`, `3-progress.png`, `4-dark.png`
- Small promo tile (440×280): `promo-small-440x280.png`
- Marquee (1400×560, optional): `promo-marquee-1400x560.png`

**Homepage URL:** `https://github.com/ggvolta/fetchly`
**Support URL:** `https://github.com/ggvolta/fetchly/issues`

---

## Privacy practices tab

**Single purpose:**
> Send the user's browser downloads, links and detected media files to the Fetchly download manager app installed on the same computer, so they download faster and can be resumed.

**Permission justifications:**

| Permission | Justification |
|---|---|
| `downloads` | Detects when the user starts a download of a file type they selected, cancels it in the browser and hands it to the Fetchly app instead. If the app isn't running the browser download continues normally. |
| `contextMenus` | Adds "Download with Fetchly", "Download all links with Fetchly" and "Download selected links with Fetchly" to the right-click menu. |
| `cookies` | Reads the cookies for the exact address being downloaded and passes them to the Fetchly app on the same computer, so downloads from sites the user is signed in to still work. Cookies are never sent anywhere else. |
| `storage` | Saves the user's settings (on/off switch and port number) and the list of videos detected in the current tab. |
| `webRequest` | Reads response headers (content type and size) of media requests to detect video and audio files on the page and offer a "Download this video" button. Requests are not blocked or modified. |
| `tabs` | Clears the detected-media list when a tab navigates or closes, and gives the popup the current tab's title and address to name downloaded videos. |
| `scripting` | When the user picks "Download all links" or "Download selected links", collects the links on that page so the user can choose which to download. |
| `alarms` | Checks every 30 seconds whether the Fetchly app is running, to show the connection status. |
| Host permission `<all_urls>` | Downloads and videos can come from any website, and the extension must reach the Fetchly app at http://127.0.0.1. |

**Are you using remote code?** No, I am not using remote code.

**Data usage:** Fetchly does not collect or transmit user data off the user's device; download details and cookies are passed only to the Fetchly app on the same computer (127.0.0.1). Leave the data-type boxes unticked and tick all three certifications:
- I do not sell or transfer user data to third parties, outside of the approved use cases
- I do not use or transfer user data for purposes that are unrelated to my item's single purpose
- I do not use or transfer user data to determine creditworthiness or for lending purposes

If a reviewer asks you to declare cookies, tick **Authentication information** and keep the certifications.

**Privacy policy URL:** `https://github.com/ggvolta/fetchly/blob/main/PRIVACY.md`

---

## Test instructions (for reviewers)

> The extension works together with the free Fetchly desktop app for Windows.
> 1. Install Fetchly from https://github.com/ggvolta/fetchly/releases/latest and start it.
> 2. Click the extension icon: it shows "Fetchly is running".
> 3. Download any .zip, .exe or .pdf file in the browser: the Fetchly "Download File Info" window opens.
> 4. Right-click any link and choose "Download with Fetchly".
> Without the app running, the extension leaves all downloads to the browser.

---

## Distribution tab

- Visibility: **Public**
- Regions: **All regions**
- Pricing: **Free**
