# Manual publication

The maintainer has accepted the application and authorized publication of the
**alpha.3 source**. Docker execution, native AMD64/ARM64 acceptance, live Portainer
integration and the built image's OS advisory/license checks remain **NOT RUN** in
[RELEASE_AUDIT.md](../RELEASE_AUDIT.md). Source publication does not change those
results or establish full deployment acceptance. Record actual results before
marking any of those checks PASS.

The commands below are manual instructions. The preparation scripts do not create
a Git repository, publish a release or upload an image.

## 1. Create an empty GitHub repository

Sign in to GitHub, select **New repository**, name it `portainer-analytics` and
choose **Public**. Leave the README, `.gitignore` and license initialization options
disabled: this source tree already contains them. Create the repository and copy
its HTTPS URL.

## 2. Prepare and inspect the local commit

Open PowerShell and replace the example path with your local `Github-Release`
folder. Upload **its contents as the repository root**, including `.github` and
other source dotfiles. Do not select the parent project or add databases, `.env`,
virtual environments, `node_modules` or generated `dist` archives.

```powershell
Set-Location -LiteralPath 'C:\path\to\Github-Release'
git init -b main
git add .
git diff --cached --stat
git diff --cached --check
```

Inspect the staged inventory and resolve any reported errors before committing.
Review [LICENSE](../LICENSE), [third-party notices](../THIRD_PARTY_NOTICES.md) and
the audit. To inspect the staged content, run `git diff --cached`.

```powershell
git commit -m "Prepare Portainer Analytics alpha.3"
```

If Git reports that your identity is missing, set it for this repository and retry
the commit. Use your GitHub-provided `noreply` address from **Settings > Emails**
if you want to keep your personal email out of public commits:

```powershell
git config user.name "YOUR_NAME"
git config user.email "YOUR_GITHUB_NOREPLY_ADDRESS"
git commit -m "Prepare Portainer Analytics alpha.3"
```

## 3. Push the source

Replace `YOUR_ACCOUNT` with your GitHub account, or use the exact HTTPS URL copied
from your empty repository. Complete GitHub authentication if Git prompts for it.

```powershell
git remote add origin https://github.com/YOUR_ACCOUNT/portainer-analytics.git
git push -u origin main
```

Refresh the repository page to confirm that README.md and Dockerfile appear at the
root. Open **Actions** and inspect the supplied CI workflow's actual results.
Record them in the audit when available; do not assume that uploading passed CI.
Enable GitHub private vulnerability reporting in the repository security settings.

## 4. Optionally create the alpha.3 prerelease

After reviewing CI, open **Releases > Draft a new release**. Create the tag
`v0.1.0-alpha.3` targeting `main`, use the title `Portainer Analytics alpha.3`, and
mark **Set as a pre-release** before publishing. Describe the changes and retain
the outstanding Docker, architecture, live integration and image-scan limitations
from the audit. GitHub supplies source ZIP and tarball downloads for the tag.

Do not attach or relabel an existing alpha.2 image as alpha.3. Container-image
publication is a separate step requiring a build from this source, deployment
checks and review of the built image's packages, notices and advisories.

References: [GitHub's local-source upload guide](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
and [release management guide](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).
