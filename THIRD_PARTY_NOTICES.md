# Third-party notices

Portainer Analytics application code and documentation are licensed under [MIT](LICENSE). The dependencies listed here retain their own licenses and are **not** relicensed by this project. This document records the reviewed direct dependencies, development tooling and interface assets; installed distribution notices and applicable upstream license texts remain authoritative.

## Python runtime packages

| Package | Pinned version | License | Upstream reference |
| --- | --- | --- | --- |
| requests | `2.34.2` | Apache-2.0 | [LICENSE](https://github.com/psf/requests/blob/main/LICENSE) / [NOTICE](https://github.com/psf/requests/blob/main/NOTICE) |
| urllib3 | `2.8.0` | MIT | [LICENSE](https://github.com/urllib3/urllib3/blob/main/LICENSE.txt) |
| certifi | `2026.7.22` | MPL-2.0 | [License and CA provenance](https://github.com/certifi/python-certifi/blob/master/LICENSE) |
| charset-normalizer | `3.5.2` | MIT | [LICENSE](https://github.com/jawah/charset_normalizer/blob/master/LICENSE) |
| idna | `3.20` | BSD-3-Clause | [LICENSE](https://github.com/kjd/idna/blob/master/LICENSE.md) |

Requests' distribution NOTICE identifies copyright 2019 Kenneth Reitz. Runtime Python dependencies are installed from hash-locked requirements instead of being vendored into the source. Preserve their `*.dist-info` metadata and license files when distributing an installed runtime environment.

certifi includes Mozilla-derived certificate data; its MPL-covered material retains its own terms. Refer to the [Mozilla Public License 2.0 FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/) for applicable distribution obligations.

## Development-only packages

Browser tests use [Playwright](https://github.com/microsoft/playwright/blob/main/LICENSE) `1.64.0` (Apache-2.0) and [jsdom](https://github.com/jsdom/jsdom/blob/main/LICENSE.txt) `30.1.2` (MIT). Their transitive dependency versions are recorded in `package-lock.json`. The earlier reviewed Node development tree contained 38 packages with metadata identifying MIT, MIT-0, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, CC0-1.0 and BlueOak-1.0.0 license identifiers. Complete package texts take precedence over this summary.

Node packages and Playwright browser executables are used for development tests; they are **not** included in the application runtime Docker image. Python development tools are similarly excluded from the runtime dependency set. Retain their notices if you redistribute a development environment.

## Python and the base container

The Dockerfile uses the official `python:3.14.6-slim-bookworm` image pinned to a manifest digest. Python has [PSF and incorporated-software license terms](https://docs.python.org/3.14/license.html); the Debian-based image includes operating-system packages with additional licenses.

A source dependency audit does not establish that every container OS package is vulnerability-free or that every image redistribution obligation has been discharged. Inspect the actual built image and preserve applicable notices before publishing an image to a registry. The [runtime SBOM](docs/sbom-runtime.cdx.json) is limited to Python runtime libraries.

## Interface and documentation

The runtime frontend uses local HTML, CSS and JavaScript with system-font fallbacks. It does not bundle third-party font binaries, icon packages, stock photos, externally hosted UI scripts or Portainer application source. The screenshots in `imgs/` are documentation of the project's own interface, not an external runtime asset.

Portainer Analytics is independently developed against the Portainer API. Portainer and third-party marks remain the property of their respective owners. This repository does not claim their endorsement.

See [Licensing](docs/LICENSING.md) and [Release audit](RELEASE_AUDIT.md) for distribution requirements and verification boundaries.
