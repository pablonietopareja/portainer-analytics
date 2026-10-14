# Release verification record - 1.0.0

- **Release:** [Portainer Analytics 1.0.0](https://github.com/pablonietopareja/portainer-analytics/releases/tag/v1.0.0)
- **Published:** 2026-10-14
- **Tag:** `v1.0.0`
- **Review date:** 2026-10-14
- **Repository:** [pablonietopareja/portainer-analytics](https://github.com/pablonietopareja/portainer-analytics)
- **Tagged source revision:** `724531289db31d5e37bc3aa4baaf1114bd074c93`
- **Remote verification of the tagged revision:** **PASS**, 4/4 jobs in each execution below

This is a maintainer verification record, not independent third-party certification. The current release evidence applies specifically to tagged revision `724531289db31d5e37bc3aa4baaf1114bd074c93`. CI results are revision-specific: subsequent commits require their own workflow runs. Documentation updates on `main` do not change the files or source archives published under `v1.0.0`.

## Validated CI evidence

[GitHub Actions run 38521810456](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38521810456) and [GitHub Actions run 38525747883](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38525747883) both completed successfully for tagged revision `724531289db31d5e37bc3aa4baaf1114bd074c93`. The tag target, run revisions, conclusions and all four job outcomes in each execution were verified through the GitHub API.

| Job | Run 38521810456 | Run 38525747883 | Scope |
| --- | --- | --- | --- |
| `checks (ubuntu-24.04)` | **PASS** | **PASS** | Ubuntu source, frontend, packaging and configured security checks |
| `checks (windows-2025)` | **PASS** | **PASS** | Windows source checks, including the corrected release-path regressions and subsequent frontend, packaging and security steps |
| `docker (ubuntu-24.04)` | **PASS** | **PASS** | Native Linux AMD64 build and isolated container acceptance |
| `docker (ubuntu-24.04-arm)` | **PASS** | **PASS** | Native Linux ARM64 build and isolated container acceptance |

The tagged revision includes the completed Windows packaging correction. Synthetic acceptance and application dependency checks do not establish live Portainer compatibility or replace a full built-image operating-system vulnerability scan.

## Historical CI evidence

[GitHub Actions run 38438590497](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38438590497) failed Windows release-path regression tests for older revision `4890c05cee15a3d24e34d4c8dd5da24bd39c3612`; Ubuntu source checks and both native container jobs passed. Later Windows frontend, packaging and security steps were skipped. This resolved historical incident does not describe the published release.

The canonical-path correction was included in `3671d45a3d9ca2f83cccc218c36843ff1e886b13`, which passed all four jobs in [run 38459321879](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38459321879) and [run 38459321693](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38459321693). The tagged revision includes that fix and has its own successful CI evidence above.

[GitHub Actions run 38371715631](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38371715631) completed successfully for earlier source revision `dcff77cacec7b88481fd7754d8f4a76d28ba223c`. Its four jobs covered Ubuntu and Windows source checks, plus native Linux AMD64 and ARM64 container acceptance. Historical runs apply only to their listed revisions.

The source-check pipeline includes locked dependency installs, Python lint/format/tests, JavaScript and browser tests, source/release verification, deterministic packaging, Bandit, pip-audit and npm audit. Container jobs build and start isolated, unconfigured application instances and check non-root operation, the read-only root filesystem, anonymous management denial and restart persistence.

## Resolved Windows release-path incident

The archive reader compared a resolved child path against an unresolved root. A local Windows NTFS junction reproduced both reported errors: an existing `.dockerignore` was rejected, and a synthetic credential fixture was rejected as a missing file before content validation. The resolved files were contained by the canonical root but not by the lexical alias. The exact temporary-directory alias on the hosted Windows runner was not diagnosed directly and remains unverified.

The reader canonicalizes the root once and compares canonical child paths against that root. Strict archive-name validation remains in place and explicitly rejects POSIX absolute names, Windows drive-qualified names, backslashes, empty path components and traversal. It still rejects missing files, leaf symlinks, resolved parent-link escapes and credential-like content. Existing archive-content, metadata, checksum and reproducibility assertions are preserved. Two regressions cover noncanonical roots and linked roots with an escaping child; Windows runs real NTFS junction fixtures, while the Linux branch uses directory and file symlinks. Both platform source jobs passed for the tagged revision.

## Local verification

The following table preserves Windows checks recorded on 2026-10-13 during remediation, before commit `3671d45a3d9ca2f83cccc218c36843ff1e886b13`, using Python 3.14.6. Local results apply to the files examined at that time. Unperformed local checks remain distinct from the successful remote CI for the tagged revision.

| Check | Status | Evidence and scope |
| --- | --- | --- |
| Python syntax | **PASS** | `python -m compileall -q`, covering runtime, scripts and tests |
| Ruff lint and formatting | **PASS** | Ruff 0.17.0: `python -m ruff check .` and `python -m ruff format --check .`; 24 files reported as correctly formatted |
| Focused release regression suite | **PASS** | `python -m unittest discover -s tests -p test_release.py -v`; all 6 tests passed in 0.982 seconds, no skips; includes real Windows NTFS junction acceptance and escape rejection |
| Full Python regression suite | **PASS** | `python -m unittest discover -s tests -v`; all 104 tests passed in 25.289 seconds, no skips; covers synthetic telemetry, setup, authentication, CSRF, sessions, persistence, API behavior and release regressions |
| Independent Windows path diagnostic | **PASS** | 4 valid file reads, 2 synthetic credential detections and 22 unsafe-path rejections; no fixture values printed |
| Locked Node install and JavaScript checks | **PASS** | `npm ci --ignore-scripts` and `npm run check`; development dependencies and frontend syntax |
| Frontend unit/DOM tests | **PASS** | `npm test`; synthetic interface behavior and charts |
| Chromium acceptance | **PASS** | `npm run test:browser`; isolated test services, not live Portainer |
| Both Compose manifests | **PASS** | Compose CLI 5.6.0: `config --quiet` for both manifests; no daemon required |
| Source verifier and documentation links | **PASS** | `python scripts/verify_release.py`; 65 intended source files, assets and release policies; all 47 local links/anchors resolve; all 22 unique external Markdown targets returned HTTP 200 |
| Deterministic archives and regressions | **PASS** | Focused fixtures and two builds from an isolated 65-file source snapshot passed; ZIP/TAR payloads, timestamps, modes, exclusions and SHA-256 checksums verified; repeated archives and checksum files were byte-identical, with 23 Docker-context files |
| Version agreement and runtime health/version | **PASS** | Release regression tests and `scripts/verify_release.py` check `1.0.0` metadata, image tags and names; native Python CLI startup and `/api/health`/`/api/session` report `1.0.0` |
| Native Python restart and persistence | **PASS** | Two disposable local starts, no configured Portainer connection; health succeeds, anonymous snapshot access returns 401 and a SQLite marker survives restart |
| Python dependency advisory checks | **PASS** | pip-audit 2.10.1: `python -m pip_audit -r requirements-dev.txt --no-deps --disable-pip`; no known vulnerabilities in the combined locked dependency set; `python -m pip check` passed |
| npm dependency advisory check | **PASS** | `npm audit --audit-level=moderate`; zero reported vulnerabilities in locked development packages |
| Bandit runtime static analysis | **PASS** | Bandit 1.9.4: configured runtime `-ll` scan; zero findings at the selected severity/confidence threshold |
| Current-source secret scan | **PASS** | Gitleaks 8.30.1 scanned the 65-file source snapshot; zero leaks detected; not a guarantee of complete detection |
| Git history secret review | **PASS** | Gitleaks 8.30.1 scanned all five local commits with `git --all`; no leaks detected; history retained |
| Screenshot privacy review | **PASS** | All four tracked 2020 x 1110 screenshots visually rechecked: synthetic interface data, no credentials or private infrastructure identifiers, no embedded text or EXIF metadata |
| Final whitespace and current release-reference sweep | **PASS** | `git diff --check`; exhaustive case-insensitive checks found zero old release-label matches in current source text and filenames; separate visual screenshot review passed |
| Local disposable Docker acceptance | **NOT RUN** | No Docker Engine/daemon is available locally; standalone Compose validation cannot verify container behavior |
| Local native ARM64 acceptance | **NOT RUN** | No native ARM64 runner is available locally; cross-building is not native acceptance |
| Local Linux source suite | **NOT RUN** | No installed WSL Linux distribution was available locally; Ubuntu source CI passed for the tagged revision |
| Local Windows file/parent symlink fixtures | **NOT RUN** | Creating symlinks required unavailable privileges; real NTFS junction cases ran locally, and the POSIX symlink cases ran in the tagged revision's Linux source CI |
| Exact-version live Portainer integration | **NOT RUN** | Must use a separately authorized test environment |
| Built-image OS advisory and complete license scan | **NOT RUN** | No local built image/daemon is available; Python/npm audits and source notices do not cover the full image |

## Public tracked-file review

All 65 tracked files were reviewed: 61 UTF-8 text files and the four screenshots. No additional public files need deletion. Tests, archive builders, CI, contributor and security guides, licensing notices, the runtime SBOM and deployment instructions are intentional public project content. The source tree has no tracked operational database, private key, backup or real credential file; documentation contains no personal workstation paths, internal publication instructions or conversational residues. Current source text and filenames contain no obsolete release label.

Local virtual environments, dependencies, caches, `build/`, `dist/`, `.env`, databases and backups are excluded by `.gitignore`; the Docker context uses an explicit allowlist. The public tree retains its 65-file structure.

## Release content and operational boundaries

The release contains five Python runtime modules, a locally hosted frontend, synthetic test services, locked dependencies, hardened Docker/Compose definitions and deterministic archive builders. Source packaging includes public documentation and screenshots. The Docker build context contains runtime sources, frontend assets and project license/notices; it excludes screenshots, development tools and local operational state.

Portainer Analytics reads inventory and telemetry through the Portainer Server API. It does not modify managed Docker resources. It persists its own configuration, administrator password hashes, dashboards, sharing capabilities and selected-metric history. Existing SQLite data volumes must be retained across upgrades.

The supplied Docker Compose and Docker Standalone stack manifests publish to host loopback by default. LAN publication is an explicit configuration choice. Containers on a shared Docker network can still reach the internal listener. Docker Swarm publication has different semantics and is not supported by these stack instructions.

The runtime uses salted scrypt password hashes, cookie sessions and CSRF checks for management. Portainer API tokens are stored **without application-level encryption**. Dashboard share URLs are bearer credentials. Secure cookies require the actual HTTPS origin in `CONSOLE_PUBLIC_URL`; the built-in server does not terminate TLS.

The recorded local validation used Python 3.14.6, Node.js 24.18.0, npm 11.16.0 and Chromium 156.0.8078.4 through Playwright 1.64.0. Container security settings were exercised by the tagged revision's native AMD64 and ARM64 CI jobs in both successful executions. Local Docker acceptance remains unperformed because no Docker daemon was available.

Archive reproducibility was checked for identical source bytes with the same Python/compression toolchain. Fixed ZIP Unix metadata, timestamps, file modes and LF checksum output remove those platform differences; byte identity across different compression-library versions has not been established.

## Evidence limits

Synthetic Portainer fixtures test supported response shapes and failure modes; they do not prove exact compatibility with a live Portainer Server, Agent, Edge deployment or Docker version. Public synthetic screenshots are interface illustrations, not benchmarks or production acceptance evidence. No live infrastructure, real tokens or production data are needed for these checks.

Application dependency scans do not inspect every container operating-system package. A complete built-image advisory and redistribution assessment needs separate image inventory, scanner output and upstream notices. Clear scans are time-specific and do not guarantee the absence of vulnerabilities or replace ongoing patch management.

The [runtime CycloneDX SBOM](docs/sbom-runtime.cdx.json) lists only the five locked Python runtime libraries. It is not a full image SBOM and does not include browser-test binaries. License terms and notices are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [Licensing](docs/LICENSING.md). The existing [MIT License](LICENSE) and copyright statement are retained; this review does not independently establish authorship or employment-related ownership.

See [Deployment](docs/DEPLOYMENT.md), [Security](SECURITY.md) and [Contributing](CONTRIBUTING.md) for installation, safeguards and reproducible verification commands.

**Release disposition:** Portainer Analytics 1.0.0 was published on 2026-10-14 under `v1.0.0`, targeting `724531289db31d5e37bc3aa4baaf1114bd074c93`. The tagged revision passed all four jobs in both recorded release CI executions and includes the resolved Windows packaging issue. Live Portainer integration and a full built-image OS vulnerability and license assessment remain unperformed.
