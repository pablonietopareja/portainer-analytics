# Changelog

## 1.0.0 - 2026-10-13

The Portainer Analytics 1.0.0 source candidate at `3671d45a3d9ca2f83cccc218c36843ff1e886b13` passed Ubuntu and Windows source checks and native Linux AMD64/ARM64 container acceptance in both recorded CI executions. See [RELEASE_AUDIT.md](RELEASE_AUDIT.md) for revision-specific evidence and remaining limitations. Git tag creation and formal GitHub Release publication are separate steps; this entry does not claim either has occurred. Subsequent commits require their own CI runs.

### Release consistency

- Align runtime responses, package metadata, Docker labels and deployment image tags with `1.0.0`.
- Produce deterministic `portainer-analytics-1.0.0-source.zip` and `portainer-analytics-1.0.0-build-context.tar` artifacts.
- Use descriptive UI assets and integration-test names, with regression coverage for version agreement and packaging.
- Show the actual browser port in the interface, including customized published ports.
- Refresh public documentation and screenshots with synthetic test data.
- Fix Windows packaging validation by comparing canonical child paths with a canonical root, preserving traversal, link-escape and credential rejection. Retain existing assertions and add regression coverage for noncanonical and linked roots.

### Deployment and security

- Publish the supplied Compose and Docker Standalone stack services on host loopback by default.
- Document deliberate LAN exposure, secure first-use access, reverse-proxy configuration and preservation of the existing data volume.
- Browser-local theme preferences may return to the system default; reselect the preferred theme after upgrading. Saved dashboard data remains in the existing volume.
- Preserve non-root execution, read-only container filesystems, capability restrictions, healthchecks, authenticated management and read-only Portainer access.

### Existing capabilities retained

Environment discovery, container/resource inventory, telemetry, dashboard editing and sharing, selected-metric history, three display themes and first-use administrator setup remain available. Earlier development changes remain in Git history rather than being presented as separately published releases.
