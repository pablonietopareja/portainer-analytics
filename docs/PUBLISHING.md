# Repository maintenance and publication

This guide describes how I keep the public `portainer-analytics` repository consistent when updating documentation, example screenshots or a release. The repository already exists; these instructions do **not** create a second repository or overwrite history.

## Updating documentation and interface screenshots

Documentation images live in the root `imgs/` folder and are referenced by relative links from `README.md`. The expected public images are:

| File | View |
| --- | --- |
| `imgs/portainer-analytics_UI_access.png` | Administrator sign-in |
| `imgs/portainer-analytics_UI_dashboard.png` | Dashboard editor and live charts |
| `imgs/portainer-analytics_UI_containers.png` | Container inventory |
| `imgs/portainer-analytics_UI_overview.png` | Environment overview |

The old repository entry named `imgs` was a regular file, not a directory. It must be removed before adding `imgs/` and these screenshots. Keep the provided filenames exactly; relative Markdown paths are case-sensitive on Linux and GitHub.

When preparing public screenshots, inspect addresses, environment labels, container names and all visible operational details. Private RFC1918 addresses are not routable Internet endpoints, but screenshots can still disclose internal infrastructure naming and topology. Only publish views you have reviewed.

The source packaging script includes the `imgs/` screenshots in the source ZIP, so the README renders correctly in source distributions. Screenshots are intentionally **excluded** from the Docker runtime build context; the application does not load them.

## Local review before pushing

From an up-to-date local clone of the public repository:

```sh
python scripts/verify_release.py
python scripts/build_release.py
git status --short
git diff --check
```

For a documentation-only update, also inspect Markdown links and the exact staged file list. For application changes, run the complete checks in [CONTRIBUTING.md](../CONTRIBUTING.md).

An optional PowerShell script distributed alongside this documentation update clones or updates `main`, copies the approved files, replaces the erroneous `imgs` file with a folder, prints the staged diff and asks for an explicit `PUSH` confirmation before publishing. It does not rebuild or redeploy a running container.

## GitHub Actions and release evidence

On 2026-10-13, the repository's [CI run #3](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38356061403) passed all four jobs: Ubuntu checks, Windows checks, AMD64 Docker acceptance and ARM64 Docker acceptance. GitHub Actions runs the same checks on subsequent pushes. Inspect the new run before referring to a later commit as validated.

CI does not publish a Docker registry image or create GitHub releases. It uses isolated synthetic Portainer fixtures for automated testing, so live compatibility and image OS scans remain distinct release considerations. Keep [RELEASE_AUDIT.md](../RELEASE_AUDIT.md) factual and commit-specific.

## Optional GitHub prerelease

When you deliberately decide to publish a release, open **Releases → Draft a new release** and create a version tag from the intended tested commit, for example `v0.1.0-alpha.3`. Mark it as a prerelease, summarize meaningful changes and attach any artifacts you have separately built and verified. Do not relabel an older container image as a new release.

GitHub automatically offers source archives for a tag. The project's own `scripts/build_release.py` also generates a deterministic source ZIP and a Docker build-context tar; these artifacts serve different purposes.

Keep [LICENSE](../LICENSE), [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) and [SECURITY.md](../SECURITY.md) available in the repository. I maintain this as an independent project, not as an official Portainer distribution.
