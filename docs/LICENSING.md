# Licensing

I publish Portainer Analytics application code and documentation under the [MIT License](../LICENSE). Contributions must be original work or compatible with the licenses of material they include.

Third-party packages retain their own license terms. Their upstream licenses, notices and recorded versions are listed in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). The installed Python distribution metadata and relevant license files should be preserved when redistributing a complete runtime environment or container.

The source repository does not bundle the Python/Debian container base layers, test-browser executables, third-party font files or copied Portainer application code. Container builds download their declared dependencies and base image. A Python runtime SBOM is included, but it does not substitute for a full built-image license and operating-system package inventory.

The interface screenshots in `imgs/` document this project's own UI. They are published as project documentation, not as a claim of ownership over Docker, Portainer or any third-party names that may be visible in an example environment.

Portainer Analytics is an independent project that uses the Portainer API. Portainer's product name and other trademarks belong to their owners; I do not claim sponsorship, certification or endorsement.

Refer to [RELEASE_AUDIT.md](../RELEASE_AUDIT.md) for checks completed in CI and additional release or deployment qualifications.
