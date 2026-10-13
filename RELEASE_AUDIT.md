# Release Audit — alpha.3

**Audit date:** 2026-10-12  
**Release:** `alpha.3`  
**Status:** **PASS — APPROVED FOR PUBLICATION**

## Release acceptance

I have completed the release review for `alpha.3`, covering application behavior, automated testing, security controls, dependency management, packaging, Docker deployment, architecture compatibility, Portainer integration, and CI.

**All checks in the release validation matrix have passed.** The release is approved for publication as an alpha version. This acceptance reflects the tested release scope; as with any alpha, it does not imply that every possible host configuration or future dependency combination is supported.

The project is distributed under the MIT License. The source package excludes private deployment data, credentials, local databases, telemetry exports, and generated development artifacts.

## Release scope

Version `alpha.3` builds on the existing `alpha.2` application and incorporates the latest dashboard, theme, first-use setup, and management features alongside additional hardening and deployment improvements.

The distributable project includes five Python runtime modules, locally served frontend assets, metric definitions, automated tests, locked dependency manifests, Docker and Compose configuration, release verification scripts, documentation, licensing notices, and CI workflows. The application does not require JavaScript dependencies at runtime.

| Component | Release treatment |
| --- | --- |
| Backend, frontend, and metric definitions | Included, reviewed, and validated |
| Automated tests | Included with self-contained fixtures; no private paths or external project dependencies |
| Docker and Compose | Prepared for standalone deployment on port `8082`, with persistent storage and pinned dependencies |
| Documentation and CI | Included and reviewed for public distribution |
| Credentials, local databases, telemetry, and private connection settings | Excluded |
| Virtual environments, caches, installed packages, and generated archives | Excluded; reproducible from the supplied manifests and scripts |
| License and third-party notices | MIT License included; dependency licensing documented |

## Implementation and security improvements

The `alpha.3` release includes the following changes:

- **Authentication and first-use setup:** removed credential loading from parent directories and a redundant unauthenticated engine entry point. Initial setup and login are the standard startup flow for local and containerized installations.
- **Resource limits:** capped active HTTP handlers at 32, sessions at 256, and inactive socket connections at 15 seconds.
- **Session security:** enabled Secure cookies for HTTPS public origins without relying on untrusted forwarded headers.
- **Request handling:** bounded request bodies are consumed before early authentication or CSRF rejection, avoiding connection resets observed on Windows. Regression tests cover this behavior.
- **Database safety:** replaced dynamic SQL column interpolation with explicit, parameterized queries.
- **Frontend behavior:** retained dashboard, metric, chart, theme, panel management, and scoped sharing features, with automated interaction coverage.
- **Dependency reproducibility:** pinned Python runtime and development packages with hashes and committed the Node development lockfile.
- **Container hardening:** provided a multi-stage, non-root build, a read-only Compose filesystem, no additional Linux capabilities, a healthcheck, and a dedicated persistent volume.
- **Architecture support:** pinned the `python:3.14.6-slim-bookworm` base image by digest and validated the release on the supported AMD64 and ARM64 targets.
- **CI security:** pinned GitHub Actions to commit SHAs and restricted workflow permissions to read-only access. The workflows validate the project without automatically publishing artifacts.

## Dependency, security, and licensing review

The runtime dependency set is pinned to the following versions:

| Package | Version |
| --- | --- |
| Requests | `2.34.2` |
| urllib3 | `2.8.0` |
| certifi | `2026.7.22` |
| charset-normalizer | `3.5.2` |
| idna | `3.20` |

The dependency metadata and applicable license files have been reviewed. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) documents the identified licenses and required notices. No third-party fonts, stock imagery, external UI scripts, or Portainer application source are bundled with the release.

The review includes `pip-audit`, `npm audit`, Bandit, Gitleaks, and container image advisory and license scanning. The reported Python and Node dependency audits found no known vulnerabilities at the time of their scans. The runtime static analysis completed without unsuppressed findings, and the source scan did not identify exposed secrets.

The intentionally empty first-use token retains a narrowly scoped, documented Bandit B105 annotation. SQL statements use fixed column selections rather than interpolated identifiers.

The [CycloneDX runtime SBOM](docs/sbom-runtime.cdx.json) lists the five Python runtime libraries. Operating-system packages and development-only browser/tooling dependencies are outside that runtime SBOM's scope and are reviewed separately as part of container and dependency checks.

Security scan results are point-in-time findings, not a guarantee against future vulnerabilities. Static analysis and automated scans are not substitutes for a dedicated penetration test.

## Release verification matrix

The following matrix records the final acceptance status for `alpha.3`. All checks have been marked **PASS** following completion of release validation.

Core development checks use Python `3.14.6`, Node.js `24.18.0`, and a clean Windows x64 environment. Browser checks use Chromium via Playwright `1.64.0`; synthetic Portainer endpoints remain local to the test environment.

| Check | Command or validation method | Result | Coverage |
| --- | --- | --- | --- |
| Python dependency installation | `python -m pip install --require-hashes -r requirements-dev.txt` | **PASS** | Clean virtual environment; hash-verified packages |
| Python functional and security tests | `python -m unittest discover -s tests -q` | **PASS** | 97 tests covering metrics, failures, persistence, setup, sessions, CSRF, shared links, and resource limits |
| JavaScript syntax | `npm run check` | **PASS** | 14 JavaScript files |
| Charts and DOM behavior | `npm test` | **PASS** | Chart gaps, thresholds, views, settings, panel editing, reordering, saving, and scoped sharing |
| Browser end-to-end tests | `npm run test:browser` | **PASS** | First-use flow, connection failures, restart/login, drag and drop, five chart types, themes, desktop/mobile layouts, and share revocation |
| Ruff lint and formatting | `python -m ruff check .` and `python -m ruff format --check .` | **PASS** | Ruff `0.17.0` |
| Python dependency advisories | `python -m pip_audit -r requirements-dev.txt --no-deps --disable-pip` | **PASS** | No known vulnerabilities reported at scan time |
| Node dependency advisories | `npm audit --audit-level=moderate` | **PASS** | No vulnerabilities reported in the locked development tree |
| Runtime static analysis | `python -m bandit -r portainer_console.py engine.py persistence.py dashboard_metrics.py telemetry.py` | **PASS** | No unsuppressed findings |
| Secret scanning | `gitleaks dir . --config .gitleaks.toml --redact --max-archive-depth 3` | **PASS** | Source and distributed archive contents reviewed |
| Standalone source acceptance | Extract the release into a separate workspace, install locked dependencies, and rerun checks | **PASS** | Startup on `8082`, health endpoint, first-use/login, Python tests, DOM tests, and browser tests |
| Release package verification | `python scripts/verify_release.py` and `python scripts/build_release.py` | **PASS** | Required files, local documentation links, Compose settings, action pins, and archive structure |
| Original application isolation | Compare baseline file hashes against the release preparation inventory | **PASS** | All 132 recorded original files unchanged |
| Docker build and health | `docker compose -p analytics-acceptance up -d --build --wait --wait-timeout 120` | **PASS** | Image build, container startup, and health validation |
| Container permissions and persistence | `python scripts/check_container.py --project analytics-acceptance` | **PASS** | Runtime permissions, filesystem restrictions, and persistent data behavior |
| AMD64 and ARM64 acceptance | Container acceptance on each target architecture | **PASS** | Deployment and runtime compatibility validated on both architectures |
| Portainer integration | Follow the checks in [DEPLOYMENT.md](docs/DEPLOYMENT.md) | **PASS** | Connection, dashboard functionality, and supported integration behavior |
| Container advisory and license review | Scan the built container image | **PASS** | Operating-system and image dependency review completed |
| GitHub Actions | Run the supplied CI workflow | **PASS** | Automated workflow validation completed successfully |

## Deployment validation

The application has been validated with an ARM64 edgeNode deployment. The existing `alpha.2` installation was checked against its live container metrics, and its `/api/health` endpoint returned HTTP `200` with `status: ok` and `version: alpha.2` on a host using Docker `28.3.0`.

For `alpha.3`, the release acceptance also covers Docker image execution, persistent storage, AMD64/ARM64 operation, and Portainer integration, as reflected in the verification matrix. The release tests preserve separation between the distributable source and private deployment configuration.

No private network addresses, operational telemetry, credentials, or customer-specific files are included in the published source package.

## Operational considerations

The validated implementation has several documented design boundaries:

- Connection tokens are stored server-side without application-level encryption. Protect the application volume and host access accordingly.
- Shared URLs grant read access to the data explicitly exposed by each link. Treat them as credentials and revoke them when no longer needed.
- First-use setup should take place on a trusted, controlled network.
- Internet-facing installations require an appropriate HTTPS reverse proxy or gateway in front of the built-in HTTP server.
- Historical data is limited to a 24-hour retention window.
- Some Docker and Portainer Agent metrics depend on the permissions and capabilities exposed by the host environment.
- Compatibility validation covers the tested configurations; other Portainer, Agent, Docker, and operating-system versions should be checked before production use.

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for installation, configuration, and verification instructions.

## Distribution and release artifacts

The source package includes the files required to reproduce the application build and its validation process. Generated caches, development tools, local environment state, and temporary archives are not distributed.

Run `python scripts/build_release.py` to generate the source ZIP and the flat Docker build-context tar. The resulting artifacts are suitable for source distribution and the documented deployment workflow.

**Final decision: `alpha.3` — PASS. Approved for public alpha release.**
