# Security policy

## Supported versions

Security fixes are made in the latest release only. Please update to the
[latest version](https://github.com/ggvolta/fetchly/releases/latest) before reporting.

## Reporting a vulnerability

Please don't open a public issue for security problems. Instead, use
[**Report a vulnerability**](https://github.com/ggvolta/fetchly/security/advisories/new) on GitHub, which reaches the
maintainer privately.

Include what you found, the steps to reproduce it, and the Fetchly version. You can expect a first reply within
7 days. Once a fix is released, you'll be credited in the release notes unless you'd rather not be.

Things that are in scope include the local API the browser extension uses (`127.0.0.1:7614`), the extension itself,
the installer, and the way Fetchly handles downloaded files and cookies.

## Signed releases

Official releases are built by GitHub Actions from this repository; see the [code signing policy](CODE_SIGNING_POLICY.md).
If you find a Fetchly file signed with Fetchly's certificate that you believe is malicious, report it as above.
