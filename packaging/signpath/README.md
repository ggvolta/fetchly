# SignPath setup

Used once the SignPath Foundation approves Fetchly. In SignPath:

1. Create the project with the slug `fetchly` and link it to the predefined **GitHub.com** trusted build system.
2. Add two artifact configurations, `app` and `installer`, from the XML files in this folder.
3. Create the signing policy `release-signing` with the Foundation's certificate, restrict it to the `main` branch,
   and require manual approval by the approver.
4. Install the SignPath GitHub App on this repository.

In GitHub (**Settings › Secrets and variables › Actions**):

- Secret `SIGNPATH_API_TOKEN`: an API token for a SignPath user who can submit signing requests.
- Variable `SIGNPATH_ORGANIZATION_ID`: the organization ID shown in SignPath.

The release workflow signs `Fetchly.exe` before building the installer, then signs the installer. Both files must
have the product name *Fetchly* and the release version, which `packaging/version_info.txt` and
`packaging/installer.nsi` already set. Raise those versions together with `fetchly/__init__.py`.
