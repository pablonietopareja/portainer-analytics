# Security policy and deployment guidance

Portainer Analytics is an alpha-stage, read-only console intended for controlled networks. I maintain the project on a best-effort basis and do not offer a contractual response time, security SLA or certification.

## Report a vulnerability

Use **Security → Report a vulnerability** in this GitHub repository if private vulnerability reporting is enabled. If that option is unavailable, open a minimal public issue requesting a private contact channel. Do not publish exploit instructions, credentials, internal hostnames, access URLs or customer data in an issue.

A useful report includes the affected commit or version, impact, a synthetic reproduction and the expected versus observed behavior. Do not use a production Docker environment to prove an exploit.

## Security model

- **Read-only monitoring:** the Portainer API client is designed to query environment data, not to create or modify Docker resources. The service does not require a Docker socket, privileged container, host mount or Portainer write endpoint.
- **First-use setup:** an empty workspace must be claimed by its first administrator. Complete this step on a controlled network before allowing broader access.
- **Credentials:** use a dedicated Portainer API token with the least read permissions your environment supports. Restrict network egress where possible.
- **Local persistence:** SQLite stores Portainer tokens, password hashes, dashboards and sharing capabilities. Passwords use salted scrypt; **API tokens do not have application-level encryption**. Protect `/data` and backups.
- **Sessions:** management routes require authenticated sessions and CSRF validation. Public dashboard links are separate bearer credentials that can be revoked.
- **Transport:** TLS certificate verification for Portainer is enabled by default. For external access, terminate HTTPS at a reverse proxy, preserve the external Host header and configure `CONSOLE_PUBLIC_URL` so cookies use `Secure`.
- **Operational content:** upstream labels, logs and errors may contain sensitive values. Pattern-based redaction is a safeguard, not comprehensive data-loss prevention.
- **Exposure:** HTTP concurrency, session limits and socket timeouts reduce accidental overload; the built-in HTTP listener should not be exposed directly as an Internet-facing gateway.

Public interface screenshots in the README are illustrative. Before replacing them with screenshots from a different installation, check browser address bars, endpoint names, container names and metric labels for information that should not be disclosed.

## Dependencies and release validation

Install Python packages from the locked, hash-verified manifests. CI checks source behavior, dependencies and static Python security, and builds/test-runs containers on native AMD64 and ARM64 Linux runners. These results do not constitute a comprehensive penetration test or OS-level vulnerability scan of a distributable image.

Keep the pinned base image updated deliberately, review OS package advisories before distributing built images, and retain the installed dependency license files. Refer to [RELEASE_AUDIT.md](RELEASE_AUDIT.md), [DEPLOYMENT.md](docs/DEPLOYMENT.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the current boundaries and procedures.
