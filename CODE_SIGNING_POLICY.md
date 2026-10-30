# Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org).

> Fetchly has applied to the SignPath Foundation open source program. Until the application is approved, releases
> are not signed and Windows SmartScreen may show a warning the first time you run the installer.

## What is signed

Each [release](https://github.com/ggvolta/fetchly/releases) contains Windows files built by
[GitHub Actions](.github/workflows/release.yml) directly from the source code in this repository:

- `Fetchly.exe`, the application, inside the installer and the portable zip
- `Fetchly-Setup-<version>.exe`, the installer

Only files produced by that automated build are submitted for signing. Nothing built on a personal computer is
signed. The file's product name is always *Fetchly* and its version matches the release.

## Team roles

Fetchly is maintained by one person.

| Role | Members |
|---|---|
| Committers and reviewers | [ggvolta](https://github.com/ggvolta) |
| Approvers | [ggvolta](https://github.com/ggvolta) |

- **Committers** can change the source code in this repository.
- **Reviewers** review every change from people who aren't committers (pull requests) before it is merged.
- **Approvers** approve each signing request by hand in SignPath before a release is signed.

All team members use multi-factor authentication for GitHub and SignPath.

## Privacy policy

This program will not transfer any information to other networked systems unless specifically requested by the
user or the person installing or operating it. Fetchly connects only to the websites the user downloads from and,
when the user downloads a streaming video and ffmpeg isn't installed, to GitHub to download ffmpeg once (this can
be turned off in Options › Videos). See the full [privacy policy](PRIVACY.md).

## Installing and uninstalling

The installer asks before creating a desktop shortcut or starting Fetchly with Windows. To uninstall, use
**Settings › Apps › Installed apps › Fetchly › Uninstall** in Windows, or run `Uninstall.exe` in the Fetchly folder.
The uninstaller removes the program, its shortcuts and the start-with-Windows entry, and asks whether to also remove
your settings and download list. Downloaded files are never touched.

## Reporting a problem

If you believe a signed Fetchly file is malicious or was not built from this repository, report it privately as
described in [SECURITY.md](SECURITY.md).
