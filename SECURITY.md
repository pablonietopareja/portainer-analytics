# Security policy and deployment guidance

Portainer Analytics 1.0.0 is a read-only operations console for controlled deployments. Maintenance is provided on a best-effort basis, without a contractual response time, security SLA or certification.

## Report a vulnerability

Use **Security > Report a vulnerability** in this GitHub repository if private reporting is enabled. If unavailable, open a minimal public issue requesting a private contact channel. Do not publish exploit instructions, credentials, internal hostnames, access URLs or customer data in an issue.

Include the affected commit or version, impact and a synthetic reproduction with expected and observed behavior. Do not use a production Docker environment to demonstrate an exploit.

## Security model

- **Read-only monitoring:** the Portainer Server API client queries data and does not create or modify managed Docker resources. It requires no Docker socket, privileged container or host mount.
- **First-use setup:** an empty workspace can be claimed by its first administrator. Default Docker publication is host loopback. Complete setup locally or through a secure tunnel before enabling LAN or wider access. Other containers sharing the application network can still reach its internal listener.
- **Credentials:** use a dedicated Portainer API token with the least read permissions supported by your environment. Restrict egress and upstream access where possible. The application being read-only does not reduce the permissions of an overprivileged token.
- **Persistence:** SQLite stores Portainer tokens, salted scrypt password hashes, dashboards, history and share capabilities. **API tokens have no application-level encryption.** Restrict access to `/data`, local data directories and backups.
- **Sessions:** authenticated management uses HttpOnly, SameSite=Strict cookies and CSRF validation. Administrator sessions expire after eight hours and are revoked on logout or server restart. Setup sessions expire after 15 minutes. Do not rely on Host-header validation as network access control.
- **Transport:** Portainer TLS verification is enabled by default. Keep it enabled with appropriate certificate trust. For remote browser access, terminate HTTPS at a reverse proxy, preserve Host and configure the actual HTTPS `CONSOLE_PUBLIC_URL` to enable Secure cookies. Forwarded headers alone do not determine cookie security.
- **Sharing:** active dashboard links are bearer credentials granting read access to selected data. Treat links as sensitive and revoke or rotate them when access should end.
- **Operational content:** upstream labels, logs and errors may contain sensitive values. Pattern-based redaction is a safeguard, not comprehensive data-loss prevention.
- **Exposure:** concurrency limits, bounded sessions/request sizes and socket timeouts reduce overload risk. Place access controls and rate limits at ingress; do not expose the built-in HTTP listener directly as an Internet gateway.

The supplied Portainer stack targets Docker Standalone. Docker Swarm published ports have different semantics; do not assume its host-loopback restriction applies in Swarm.

Use Docker Engine 28.0.0 or newer for localhost publication isolation. Earlier versions can expose those ports to hosts on the same layer-2 network, and custom direct routing needs separate access controls. Review [Docker's network guidance](https://docs.docker.com/engine/network/port-publishing/) and the deployment host's actual configuration.

Public screenshots use synthetic fixtures. When documenting another installation, review environment names, container inventories, metric labels, tokens and operational details before publication.

## Dependencies and verification

Install Python packages from locked, hash-verified requirements. CI checks source behavior, application dependencies and static Python security; separate jobs build and test containers on native AMD64 and ARM64 Linux runners. The published 1.0.0 candidate passed Ubuntu source checks and both container jobs, while the Windows source job failed in release-path regression tests. Remote verification of the remediation remains pending until its final source revision completes CI.

Dependency scans do not inspect all container OS packages or guarantee the absence of vulnerabilities. Keep pinned base images updated deliberately, scan the actual built image before redistribution and preserve installed dependency notices. See the revision-specific [verification record](RELEASE_AUDIT.md), [deployment guide](docs/DEPLOYMENT.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
