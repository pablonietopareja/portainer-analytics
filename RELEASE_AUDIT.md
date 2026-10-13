# Release audit — alpha.3

**Release:** `alpha.3`  
**Documentation reviewed:** 2026-10-13  
**Repository:** [pablonietopareja/portainer-analytics](https://github.com/pablonietopareja/portainer-analytics)  
**Disposition:** Public alpha source release; automated checks passing, with deployment-specific limits stated below.

## Summary

I reviewed the `alpha.3` source tree, release packaging, documented security boundaries and test configuration. The repository's GitHub Actions workflow completed successfully on 2026-10-13 for all four matrix jobs: Ubuntu source checks, Windows source checks, native Linux AMD64 Docker acceptance and native Linux ARM64 Docker acceptance.

This is a source-level and CI-backed release record, not a claim that every real Portainer installation or every container package has been separately audited. The distinction matters: the CI jobs start isolated application instances and synthetic Portainer services. Live screenshots demonstrate an operating installation, but do not by themselves establish which exact release commit was deployed.

**CI evidence:** [successful workflow run #3](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38356061403) on `main` (`f50c0d931a8811c8a26f18c46717aad6a5d59232`).

## Scope and changes

`alpha.3` establishes a standalone source distribution of the console. The project includes five Python runtime modules, locally hosted HTML/CSS/JavaScript, synthetic Python and browser tests, pinned Python and Node development dependencies, Docker/Compose manifests, security checks, an MIT license, third-party notices and release scripts.

The implementation also introduces first-use administrator setup, hardened session handling, bounded HTTP concurrency and request bodies, fixed SQL query paths, dashboard persistence, read-only sharing and a multi-stage non-root Docker image. The container requires neither privileged mode nor a Docker socket mount.

I excluded credentials, deployment databases, private connection settings, raw telemetry exports, virtual environments, installed development tools and generated caches from the distributable source. Documentation screenshots are interface illustrations rather than exported operational fixtures.

## Verification matrix

The statuses below distinguish **results visible in GitHub Actions** from **checks recorded in the earlier local release review** and **work still requiring separate evidence**. A successful Docker build is not equivalent to a full vulnerability assessment or a production Portainer integration test.

| Check | Evidence / command | Status | Scope |
| --- | --- | --- | --- |
| Linux Python and frontend checks | GitHub Actions `checks (ubuntu-24.04)` | **PASS — CI** | Locked install, Ruff, Python tests, JS/DOM/browser tests, release verification, Bandit, pip-audit and npm audit |
| Windows Python and frontend checks | GitHub Actions `checks (windows-2025)` | **PASS — CI** | Same source-check pipeline on Windows |
| Docker AMD64 build and health | GitHub Actions `docker (ubuntu-24.04)` | **PASS — CI** | Native build, Compose startup and healthcheck |
| Docker ARM64 build and health | GitHub Actions `docker (ubuntu-24.04-arm)` | **PASS — CI** | Native ARM64 build, Compose startup and healthcheck |
| Container security policy | `scripts/check_container.py`, run by both Docker jobs | **PASS — CI** | UID/GID 10001, read-only root filesystem, denied anonymous management and volume persistence after restart |
| Release packaging | `scripts/verify_release.py` and `scripts/build_release.py`, run by source-check jobs | **PASS — CI** | Required source files, relative Markdown links, build context, archive contents and pinned CI actions |
| Python functional regression | `python -m unittest discover -s tests -v`, run by source-check jobs | **PASS — CI** | Metrics, persistence, first-use, session security and API behavior with synthetic fixtures |
| Browser interaction regression | `npm test` and `npm run test:browser`, run by source-check jobs | **PASS — CI** | Canvas charts, dashboard interactions, login, sharing and UI workflows with synthetic services |
| Python and Node dependency advisories | `pip-audit` / `npm audit`, run by source-check jobs | **PASS — CI** | Advisory checks against locked package manifests at run time; not a permanent guarantee |
| Static Python security review | Bandit, run by source-check jobs | **PASS — CI** | Configured runtime static-analysis check, not penetration testing |
| Source secret scan | Gitleaks directory scan documented in the local 2026-10-12 review | **PASS — recorded local review** | Not part of the current GitHub Actions workflow; no new scan is implied |
| Source isolation | Comparison of 132 original files documented in the local 2026-10-12 review | **PASS — recorded local review** | Historical preparation check; not rerun by this audit |
| Real Portainer API integration of the exact `alpha.3` image | Dedicated deployment acceptance required | **NOT INDEPENDENTLY VERIFIED** | Screenshots and an earlier `alpha.2` health check are not exact-version integration evidence |
| Built-image OS vulnerability and license scan | Container image inventory and advisory scanner | **NOT INDEPENDENTLY VERIFIED** | CI dependency scans do not inspect all operating-system image packages |
| Live behavior across specific Portainer/Agent versions | Record exact server, Agent and Docker versions per environment | **NOT FULLY QUALIFIED** | Optional APIs, network topology and platform versions vary |

The Python test suite included 97 tests in the earlier local acceptance record. The current CI workflow supplies stronger independent execution evidence for its source and native-container jobs; individual pass counts should be taken from the associated logs rather than assumed for future revisions.

## Architecture and deployment evidence

The Docker configuration builds a Python 3.14.6-based image on both native architectures in the CI matrix, runs it under UID/GID `10001:10001`, mounts a dedicated SQLite data volume and applies a read-only root filesystem, capability drop, `no-new-privileges` and a healthcheck. The automated container acceptance script also verifies startup state, session restrictions and restart persistence in a disposable test workspace.

A separate running edgeNode installation has been observed through the console's Overview, Containers, Dashboards and administrator access screens. That observation establishes the UI's operational presentation, not a controlled comparison between `alpha.2` and `alpha.3`. The original `alpha.2` field review also recorded HTTP 200 from `/api/health` and Docker 28.3.0 on an aarch64 host.

For a particular target deployment, follow [DEPLOYMENT.md](docs/DEPLOYMENT.md), confirm the running application version, verify live Portainer queries, and record the host's Docker, Portainer and Agent versions.

## Security and licensing

The runtime Python dependencies are pinned as follows:

| Package | Version |
| --- | --- |
| requests | `2.34.2` |
| urllib3 | `2.8.0` |
| certifi | `2026.7.22` |
| charset-normalizer | `3.5.2` |
| idna | `3.20` |

The [runtime CycloneDX SBOM](docs/sbom-runtime.cdx.json) identifies these Python libraries. It does not list all operating-system packages or browser-test tools. License and notice information is maintained in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [docs/LICENSING.md](docs/LICENSING.md).

The application uses salted scrypt password hashes, cookie-based sessions and CSRF protection for authenticated management. Portainer tokens are stored in SQLite **without application-level encryption**. Public share URLs grant limited read access to explicitly shared dashboards and must be treated as bearer credentials. Secure cookies depend on an appropriately configured HTTPS public origin and reverse proxy. The default HTTP server is intended for controlled networks.

A clear dependency or static scan is not a guarantee against undiscovered vulnerabilities; it does not replace threat modeling, penetration testing or ongoing patch management. Before distributing an image to others, inspect the actual built image for OS advisories and redistribution obligations.

## Packaging and publication

`scripts/build_release.py` creates a source ZIP and a Docker build-context tar. The source archive includes repository documentation and interface screenshots; the Docker build context includes only runtime sources and web assets. No credentials or operational telemetry belong in either artifact.

The CI workflow checks and builds but does not publish a registry image or a GitHub release. Release/tag creation and deployment are deliberate maintainer actions. The repository is available under the [MIT License](LICENSE), with dependencies retaining their own terms.

**Release decision:** Suitable for an openly documented `alpha.3` source release, with the verified CI acceptance and the separate integration/security qualification boundaries recorded above.
