# Changelog

## alpha.3 - 2026-10-12

First standalone alpha source release, based on the existing alpha.2 console.

- Removed parent-directory configuration and the duplicate unauthenticated server
  entry point. Fresh local and container installations now use the same setup flow.
- Required administrator authentication in normal runtime, bounded sessions and
  concurrent HTTP handlers, added socket read timeouts and HTTPS cookie support.
- Preserved environment views, themes, metric definitions, saved dashboards and
  shared displays. The default local port is now 8082, matching Docker deployment.
- Added hash-locked Python dependencies, locked browser-test tooling, a pinned
  multi-stage Dockerfile, isolated synthetic tests, CI and deployment documentation.
- Added source/build-context packaging, security checks, third-party notices and
  an MIT license following the author's confirmation.

Execution evidence and outstanding container checks are in
[RELEASE_AUDIT.md](RELEASE_AUDIT.md). Earlier development history is not reconstructed
as published releases.
