# Security

This alpha is designed for a controlled network. No long-term support or security
response SLA is promised. Check [RELEASE_AUDIT.md](RELEASE_AUDIT.md) for the precise
version, checks and outstanding validation before deployment.

## Reporting

Use the repository's **Security > Report a vulnerability** option if private
vulnerability reporting is enabled. If it is unavailable, open a minimal issue
asking the maintainer for a private contact channel; do not include exploit details,
credentials, access URLs, databases or real customer data in a public issue.
Repository maintainers should enable private reporting before public distribution.

Include the affected version, a synthetic reproduction, expected/actual behavior
and impact through the agreed private channel. There is no invented contact email
or guaranteed response deadline.

## Deployment boundaries

- Restrict network access during first setup. The first successful setup claims
  the empty workspace; there is no preconfigured bootstrap secret.
- Use a dedicated Portainer token with the smallest available read permissions.
  The configured server URL causes outbound HTTP from the application by design.
  Limit outbound access at the network boundary where required.
- TLS verification is enabled by default. Prefer a trusted CA chain; disabling
  verification permits interception of the token and upstream responses.
- Use HTTPS at a reverse proxy for remote access, preserve Host, and set
  `CONSOLE_PUBLIC_URL` to the HTTPS origin so session cookies use `Secure`.
- Protect `/data` and backups. Portainer tokens and sharing capabilities are stored
  in SQLite without application-level encryption; passwords use salted scrypt.
- Treat a shared dashboard URL as a read credential. Revoke or rotate it when
  access should end. Shared responses include selected resource names and metrics.
- Logs, labels and upstream errors can carry sensitive operational information.
  Pattern-based redaction cannot recognize every secret format.
- HTTP concurrency, socket inactivity and session counts are bounded. Use a reverse
  proxy for TLS, request-rate limits and exposure control; the built-in server is
  not a replacement for an Internet-facing gateway.

The application needs no privileged container, Docker socket mount, shell on the
monitored node or Portainer write API. Its unauthenticated routes are limited to
static assets, health, setup/login bootstrap and explicitly shared projections.

## Dependency and image hygiene

Install from locked manifests with hash verification. Keep dependency license
metadata in the image. Review base-image and OS advisories after building; a Python
dependency scan does not inspect the operating-system layers. Do not include live
`.env`, data, logs or backup directories in source or Docker build contexts.
