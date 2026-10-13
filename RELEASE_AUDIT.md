# Release verification record - 1.0.0

- **Target version:** `1.0.0`
- **Review date:** 2026-10-13
- **Repository:** [pablonietopareja/portainer-analytics](https://github.com/pablonietopareja/portainer-analytics)
- **Source under review:** local 1.0.0 working-tree changes based on `dcff77cacec7b88481fd7754d8f4a76d28ba223c`
- **Remote verification of these changes:** **PENDING**

This is a maintainer verification record, not independent third-party certification. Local working-tree results apply to the reviewed files, not to an unpublished commit or tag. A final commit must complete its own CI run before historical results can be supplemented with new revision-specific evidence.

## Historical CI evidence

[GitHub Actions run 38371715631](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38371715631) completed successfully for source revision `dcff77cacec7b88481fd7754d8f4a76d28ba223c`. Its four jobs cover Ubuntu and Windows source checks, plus native Linux AMD64 and ARM64 container acceptance. This evidence predates the 1.0.0 working-tree changes and does **not** verify them.

The source-check pipeline includes locked dependency installs, Python lint/format/tests, JavaScript and browser tests, source/release verification, deterministic packaging, Bandit, pip-audit and npm audit. Container jobs build and start isolated, unconfigured application instances and check non-root operation, the read-only root filesystem, anonymous management denial and restart persistence.

## Current verification

The following results record checks of the local 1.0.0 files. `NOT RUN` is not a passing result. Remote jobs remain pending until the final reviewed revision is committed and its workflow completes.

| Check | Status | Evidence and scope |
| --- | --- | --- |
| Python syntax | **PASS** | `python -m compileall -q`, covering runtime, scripts and tests |
| Ruff lint and formatting | **PASS** | Ruff 0.17.0: `python -m ruff check .` and `python -m ruff format --check .`; 24 files reported as correctly formatted |
| Full Python regression suite | **PASS** | `python -m unittest discover -s tests`; 102 tests passed, covering synthetic telemetry, setup, authentication, CSRF, sessions, persistence, API behavior and release regressions |
| Locked Node install and JavaScript checks | **PASS** | `npm ci --ignore-scripts` and `npm run check`; development dependencies and frontend syntax |
| Frontend unit/DOM tests | **PASS** | `npm test`; synthetic interface behavior and charts |
| Chromium acceptance | **PASS** | `npm run test:browser`; isolated test services, not live Portainer |
| Both Compose manifests | **PASS** | Compose CLI 5.6.0: `config --quiet` for both manifests; no daemon required |
| Source verifier and local documentation links | **PASS** | `python scripts/verify_release.py`; 65 intended source files, assets and release policies; all 47 local links/anchors resolve |
| Deterministic source ZIP and build-context tar | **PASS** | `python scripts/build_release.py` run twice; 65 source ZIP files and 23 Docker-context files; exact payloads and SHA-256 checksums verified, byte-identical repeated builds |
| Version agreement and runtime health/version | **PASS** | Release regression tests and `scripts/verify_release.py` check `1.0.0` metadata, image tags and names; native Python CLI startup and `/api/health`/`/api/session` report `1.0.0` |
| Native Python restart and persistence | **PASS** | Two disposable local starts, no configured Portainer connection; health succeeds, anonymous snapshot access returns 401 and a SQLite marker survives restart |
| Python dependency advisory checks | **PASS** | pip-audit 2.10.1: `python -m pip_audit -r requirements-dev.txt --no-deps --disable-pip`; no known vulnerabilities in the combined locked dependency set |
| npm dependency advisory check | **PASS** | `npm audit --audit-level=moderate`; zero reported vulnerabilities in locked development packages |
| Bandit runtime static analysis | **PASS** | Bandit 1.9.4: configured runtime `-ll` scan; zero findings at the selected severity/confidence threshold |
| Current-source secret scan | **PASS** | Gitleaks 8.30.1 scanned the 65-file source snapshot; zero leaks detected; not a guarantee of complete detection |
| Git history secret review | **PASS** | Gitleaks 8.30.1 scanned all four local commits with `git --all`; no leaks detected; history retained |
| Screenshot privacy and rendered UI review | **PASS** | Four updated screenshots captured from the rendered 1.0.0 interface with strictly synthetic data and visually inspected |
| Final whitespace and current release-reference sweep | **PASS** | `git diff --check`; exhaustive case-insensitive checks found zero old release-label matches in current source text and filenames; separate visual screenshot review passed |
| Local disposable Docker acceptance | **NOT RUN** | No Docker Engine/daemon is available locally; standalone Compose validation cannot verify container behavior |
| Local native ARM64 acceptance | **NOT RUN** | No native ARM64 runner is available locally; cross-building is not native acceptance |
| New Ubuntu/Windows source CI | **PENDING REMOTE CI** | Final 1.0.0 revision has not completed a remote run |
| New native AMD64/ARM64 container CI | **PENDING REMOTE CI** | Historical passing jobs cannot qualify new changes |
| Exact-version live Portainer integration | **NOT RUN** | Must use a separately authorized test environment |
| Built-image OS advisory and complete license scan | **NOT RUN** | No local built image/daemon is available; Python/npm audits and source notices do not cover the full image |

## Release content and operational boundaries

The release contains five Python runtime modules, a locally hosted frontend, synthetic test services, locked dependencies, hardened Docker/Compose definitions and deterministic archive builders. Source packaging includes public documentation and screenshots. The Docker build context contains runtime sources, frontend assets and project license/notices; it excludes screenshots, development tools and local operational state.

Portainer Analytics reads inventory and telemetry through the Portainer Server API. It does not modify managed Docker resources. It persists its own configuration, administrator password hashes, dashboards, sharing capabilities and selected-metric history. Existing SQLite data volumes must be retained across upgrades.

The supplied Docker Compose and Docker Standalone stack manifests publish to host loopback by default. LAN publication is an explicit configuration choice. Containers on a shared Docker network can still reach the internal listener. Docker Swarm publication has different semantics and is not supported by these stack instructions.

The runtime uses salted scrypt password hashes, cookie sessions and CSRF checks for management. Portainer API tokens are stored **without application-level encryption**. Dashboard share URLs are bearer credentials. Secure cookies require the actual HTTPS origin in `CONSOLE_PUBLIC_URL`; the built-in server does not terminate TLS.

Local validation uses Python 3.14.6, Node.js 24.18.0, npm 11.16.0 and Chromium through Playwright 1.64.0. Container security settings are inspected in source and were exercised by historical CI; they have not been run locally for the changed release because no Docker daemon is available.

Archive reproducibility was checked for identical source bytes with the same Python/compression toolchain. Fixed ZIP Unix metadata, timestamps, file modes and LF checksum output remove those platform differences; byte identity across different compression-library versions has not been established. Rebuild and verify checksums after any source change, including changes to this record.

## Evidence limits

Synthetic Portainer fixtures test supported response shapes and failure modes; they do not prove exact compatibility with a live Portainer Server, Agent, Edge deployment or Docker version. Public synthetic screenshots are interface illustrations, not benchmarks or production acceptance evidence. No live infrastructure, real tokens or production data are needed for these checks.

Application dependency scans do not inspect every container operating-system package. A complete built-image advisory and redistribution assessment needs separate image inventory, scanner output and upstream notices. Clear scans are time-specific and do not guarantee the absence of vulnerabilities or replace ongoing patch management.

The [runtime CycloneDX SBOM](docs/sbom-runtime.cdx.json) lists only the five locked Python runtime libraries. It is not a full image SBOM and does not include browser-test binaries. License terms and notices are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [Licensing](docs/LICENSING.md). The existing [MIT License](LICENSE) and copyright statement are retained; this review does not independently establish authorship or employment-related ownership.

See [Deployment](docs/DEPLOYMENT.md), [Security](SECURITY.md) and [Contributing](CONTRIBUTING.md) for installation, safeguards and reproducible verification commands.

**Release disposition:** Remote acceptance of the final 1.0.0 revision is pending. This record does not claim that a GitHub release, tag or registry image has been published.
