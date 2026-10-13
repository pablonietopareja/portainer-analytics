# Changelog

## alpha.3 — 2026-10-12

This is the first standalone public alpha source release of Portainer Analytics. I consolidated the existing `alpha.2` console into a distributable project and aligned local development, automated tests and container deployment around the same application.

### Application

- Kept the environment overview, container and stack inventory, charts, metric selection, dashboard editor, saved layouts and read-only dashboard sharing.
- Standardized the initial administrator setup and sign-in workflow for Python and Docker installations.
- Added light, dark and system themes, along with responsive dashboard and navigation behavior.
- Standardized the application listening port to `8082`.

### Reliability and security

- Removed inherited parent-directory credential loading and the duplicate unauthenticated entry point.
- Bounded HTTP handlers, session count, request sizes and socket idle time; hardened session and CSRF handling.
- Replaced dynamic SQL identifier interpolation with explicit query paths.
- Added hash-locked Python requirements, pinned development dependencies and maintained third-party license notices.

### Packaging and validation

- Added a multi-stage, non-root Dockerfile, persistent-volume Compose definitions, a healthcheck and isolated container acceptance tests.
- Added automated Python, JavaScript, DOM and Chromium tests with synthetic Portainer fixtures.
- Added GitHub Actions checks on Windows and Linux plus native Docker acceptance on AMD64 and ARM64.
- Added deterministic source and Docker-context packaging scripts, documentation and the MIT License.

**Verification update — 2026-10-13:** All four GitHub Actions matrix jobs completed successfully, including both native container acceptance jobs. See [RELEASE_AUDIT.md](RELEASE_AUDIT.md) for exactly what they cover and what still requires live-deployment qualification.

The repository's interface screenshots illustrate a running installation. Earlier development iterations are not represented as separately published releases.
