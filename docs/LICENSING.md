# Licensing

Portainer Analytics application code and documentation are provided under the existing [MIT License](../LICENSE). Contributions must be original work or redistributable under compatible terms. The repository's copyright statement is retained; source review alone does not independently establish ownership or resolve employment-related intellectual-property obligations.

Third-party packages retain their own terms. Recorded versions and upstream references are listed in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Preserve installed Python distribution metadata, notices and applicable license files when redistributing a complete runtime environment or container.

The source repository does not bundle Python/Debian base layers, test-browser executables, third-party font files or Portainer application code. Container builds download their declared dependencies and base image. The included [Python runtime SBOM](sbom-runtime.cdx.json) identifies runtime libraries; it is not a full built-image operating-system or license inventory.

Screenshots in `imgs/` document the application's interface using synthetic test data. They do not imply ownership of Docker, Portainer or third-party names.

Portainer Analytics is independent and uses the Portainer Server API. Product names and trademarks belong to their owners; no sponsorship, certification or endorsement is claimed.

See [Release verification](../RELEASE_AUDIT.md) for the evidence and limitations of completed checks.
