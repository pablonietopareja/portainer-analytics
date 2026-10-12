# Release audit: alpha.3

Preparation date: **2026-10-12**.

## Acceptance status

**READY TO PUBLISH as an alpha source release, with maintainer acceptance.**

The source candidate has passed local Python, JavaScript, browser and dependency
checks. The application author confirmed authorship, and the application is now
licensed under MIT. On 2026-10-12, the author accepted completion and authorized
manual GitHub publication with the outstanding deployment checks disclosed. This
changes the publication scope to an alpha source release; it does not establish
full container acceptance.

Execution of the final Docker image, acceptance checks on the target architectures
and live Portainer integration remain **NOT RUN**. Docker is not available in the
preparation environment. These results have not been changed to PASS. No remote
repository, image or release was published during preparation, and no existing
deployment was changed.

## Selected source and scope

The latest complete application was the existing `alpha.2` implementation, including
its locally saved changes. There was no Git repository or commit/tag history to use
as an authoritative version. All 17 runtime/frontend files matched its existing
build-context archive before preparation. The older console was missing the saved
dashboard, theme and first-use capabilities and was not selected.

The public copy advances that development label to `alpha.3`; no earlier public
release history is asserted. It consists of five Python runtime modules, local web
assets, synthetic tests, dependency manifests, deployment files, packaging and
verification scripts, documentation and CI. It has no runtime JavaScript dependency.

| Inventory class | Treatment |
| --- | --- |
| Runtime modules, web assets, metric definitions | Copied from the selected application, then independently hardened and checked |
| Automated tests | Included after removing personal paths, sibling-project dependencies and live-instance requirements |
| Deployment/build files | Rebuilt for the independent source tree, fixed image tag, port 8082, persistent volume and hash-locked dependencies |
| Documentation, CI, notices | Written for external users with no private endpoints or unsupported compatibility claims |
| Databases, telemetry exports, local connection files, legacy audit scripts | Excluded; no real fixtures or credentials included |
| Caches, virtual environments, installed Node packages and archives | Rebuildable; excluded from source distribution and Docker contexts |
| Licensing | First-party authorship confirmed; MIT added; dependency terms retained |

## Changes made only in the public copy

- Removed parent-directory credential loading and the duplicate unauthenticated
  engine entry point. First-use setup and login are the defaults for local and
  Docker execution; environment credentials cannot silently bootstrap a workspace.
- Limited active HTTP handlers to 32, sessions to 256 and socket inactivity to 15s.
  HTTPS public origins enable Secure cookies without trusting forwarded headers.
- Read bounded mutation bodies before early authentication/CSRF rejection so a
  response is not lost to a TCP reset on Windows. Added regression coverage.
- Replaced dynamic SQL column interpolation with fixed parameterized queries.
- Kept dashboard, chart, metric and sharing behavior, with synthetic browser
  coverage of the complete interaction flow. The original installation was not
  upgraded or restarted.
- Locked Python runtime/development packages with hashes and Node development
  packages with an npm lockfile. Docker uses Python 3.14.6-slim-bookworm pinned to
  a manifest digest; both AMD64 and ARM64 entries were present in registry metadata.
- Added a multi-stage non-root image, read-only Compose filesystem, no added
  capabilities, healthcheck, private volume and clean Portainer upload context.
- Pinned CI actions to commit SHAs and restricted repository permissions to read.
  CI performs checks/builds and contains no publication job.

## Security and license evidence

Runtime pins: Requests 2.34.2, urllib3 2.8.0, certifi 2026.7.22,
charset-normalizer 3.5.2 and idna3.20. Installed distribution metadata and license
files were inspected; [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) records the
identified licenses and required notice handling. No third-party fonts, stock
images, external UI scripts or Portainer application source are bundled.

pip-audit 2.10.1 reported no known vulnerabilities in the runtime and development
requirements at scan time. npm auditing reported no vulnerabilities in the locked
development tree. Advisory results are time-specific, not a security guarantee.

Gitleaks 8.30.1 was obtained from its official release and checked against the
published SHA256 checksum. Redacted directory scanning found no leaks in the
reviewed source. Its config extends the default rules and excludes only installed
development dependencies and generated caches. There is no Git history in this
delivery to scan. Manual checks also covered private references, examples and the
archive allowlists.

Bandit 1.9.4 initially flagged the deliberately empty setup token and a column name
selected from two fixed strings. The empty token has a narrow, explained B105
annotation; the SQL query now uses fixed strings. Runtime scanning then reported
no unsuppressed findings. This is static review, not penetration testing.

[The CycloneDX SBOM](docs/sbom-runtime.cdx.json) records the five Python runtime
libraries. It does not cover operating-system layers, development browsers or
every dependency in the Node test toolchain. A built-container vulnerability and
license scan remains outstanding.

## Verification matrix

The matrix below covers the `alpha.3` public candidate. Acceptance of the deployed
`alpha.2` baseline is recorded separately below.

Local environment: Python 3.14.6, Node 24.18.0, Windows x64; dependency installation
uses a new virtual environment. Synthetic Portainer services bind only loopback.

| Check | Command or strategy | Result | Evidence / limitation |
| --- | --- | --- | --- |
| Python installation | `python -m pip install --require-hashes -r requirements-dev.txt` | PASS | Fresh environment, hash-verified runtime and development packages |
| Python behavior/security | `python -m unittest discover -s tests -q` | PASS | 97 tests, including metrics, failures, persistence, setup, sessions, CSRF, links and resource bounds |
| JS syntax | `npm run check` | PASS | 14 JavaScript files checked |
| Charts and DOM interactions | `npm test` | PASS | Chart gaps/thresholds, views, settings, panel editing, reorder, save and scoped sharing |
| Real browser | `npm run test:browser` | PASS | Chromium through Playwright 1.64.0; first-use, failed connection, restart/login, drag/drop, five chart types, themes, desktop/mobile and revocation; synthetic API only |
| Ruff lint/format | `python -m ruff check .` and `python -m ruff format --check .` | PASS | Ruff 0.17.0; no separate type checker configured |
| Python advisories | `python -m pip_audit -r requirements-dev.txt --no-deps --disable-pip` | PASS | No known vulnerabilities at scan time |
| Node advisories | `npm audit --audit-level=moderate` | PASS | No vulnerabilities reported in the locked development tree |
| Runtime static security | `python -m bandit -r portainer_console.py engine.py persistence.py dashboard_metrics.py telemetry.py` | PASS | No unsuppressed runtime findings after review |
| Secrets | `gitleaks dir . --config .gitleaks.toml --redact --max-archive-depth 3` | PASS | Redacted directory scan; no known secret values or real-data fixtures copied |
| Independent-copy acceptance | Extract source outside the original project, create a fresh venv, install Python/Node locks, and rerun checks | PASS | Default startup on 8082, health/first-use/authentication; 97 Python tests; charts/DOM and complete Chromium suite passed from that copy |
| Package and documentation | `python scripts/verify_release.py` and `python scripts/build_release.py` | PASS | Source/asset completeness, local Markdown links, Compose policy, pinned actions, archive bytes and root Dockerfile checked |
| Original isolation | Compare original-file hashes with the pre-work inventory | PASS | All 132 recorded original files unchanged, including private state; no production API writes or service changes |
| Docker build and health | `docker compose -p analytics-acceptance up -d --build --wait --wait-timeout 120` | NOT RUN | No Docker CLI/daemon available here |
| Container permissions/persistence | `python scripts/check_container.py --project analytics-acceptance` | NOT RUN | Requires a fresh Docker test workspace |
| Native ARM64 / AMD64 | Run container acceptance on each architecture | NOT RUN | Base manifest availability is not runtime verification |
| Live Portainer integration | Follow browser checks in deployment guide | NOT RUN | No production API or private deployment used for release tests |
| Container OS advisory/license scan | Scan the actual built image | NOT RUN | No built image available |
| GitHub Actions | Execute the supplied workflow in a repository | NOT RUN | Workflow prepared locally; no repository upload or CI run performed |

## Field acceptance of the alpha.2 baseline

On 2026-10-12, the application author reported that the container deployed on an
ARM64 edgeNode works as expected and accepted its operation. The supplied screenshot
shows a populated overview with live container metrics on an aarch64 host running
Docker 28.3.0. A read-only request to that deployment's `/api/health` returned
HTTP 200, `status: ok` and `version: alpha.2`.

This records successful user acceptance of the deployed `alpha.2` baseline. It does
not qualify the `alpha.3` image: the public candidate changes runtime hardening,
dependencies and the Docker build. Its container execution, persistence and live
integration checks remain NOT RUN until that version is tested. The deployment
was not modified. The screenshot, private address and operational data are not
included in this public source tree.

## Remaining actions and boundaries

Run the [container acceptance procedure](docs/DEPLOYMENT.md), inspect the built
image's packages/licenses/advisories, and qualify the real Portainer/Agent versions
you plan to use. Update this matrix with real results before declaring full
container acceptance. These checks remain outstanding for deployment qualification;
the author has accepted source publication with those limitations disclosed.

The token is stored server-side without application encryption. Shared URLs grant
read access to their selected data. First-use setup needs a controlled network.
The built-in HTTP server requires a gateway/proxy for Internet-facing deployment.
History is limited to 24 hours, and several Docker/Agent metrics depend on runtime
capabilities. These are documented boundaries, not hidden guarantees.

No push, remote repository creation, public release, registry upload, production
credential rotation or existing-container change was performed.

Generated caches, installed tools and archives are omitted from the final source
folder. `scripts/build_release.py` reconstructs the source ZIP and flat Docker
context tar; private test logs and environment fingerprints are not distributed.
