# Changelog

## 1.0.0 - 2026-10-14

Published as [Portainer Analytics 1.0.0](https://github.com/pablonietopareja/portainer-analytics/releases/tag/v1.0.0), with tag `v1.0.0` at `724531289db31d5e37bc3aa4baaf1114bd074c93`. The tagged revision passed Ubuntu and Windows source checks and native Linux AMD64/ARM64 container acceptance in [CI run 38521810456](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38521810456) and [CI run 38525747883](https://github.com/pablonietopareja/portainer-analytics/actions/runs/38525747883). See [RELEASE_AUDIT.md](RELEASE_AUDIT.md) for evidence and remaining limitations.

### Release consistency

- Aligned runtime responses, package metadata, Docker labels and deployment image tags with `1.0.0`.
- Added deterministic `portainer-analytics-1.0.0-source.zip` and `portainer-analytics-1.0.0-build-context.tar` packaging.
- Used descriptive UI assets and integration-test names, with regression coverage for version agreement and packaging.
- Updated the interface to show the actual browser port, including customized published ports.
- Refreshed public documentation and screenshots with synthetic test data.
- Fixed Windows packaging validation by comparing canonical child paths with a canonical root, preserving traversal, link-escape and credential rejection. Retained existing assertions and added regression coverage for noncanonical and linked roots.

### Deployment and security

- Bound the supplied Compose and Docker Standalone stack services to host loopback by default.
- Documented deliberate LAN exposure, secure first-use access, reverse-proxy configuration and preservation of the existing data volume.
- Browser-local theme preferences may return to the system default; reselect the preferred theme after upgrading. Saved dashboard data remains in the existing volume.
- Preserved non-root execution, read-only container filesystems, capability restrictions, healthchecks, authenticated management and read-only Portainer access.

### Existing capabilities retained

Environment discovery, container/resource inventory, telemetry, dashboard editing and sharing, selected-metric history, three display themes and first-use administrator setup remain available. Earlier development changes remain in Git history rather than being presented as separately published releases.
