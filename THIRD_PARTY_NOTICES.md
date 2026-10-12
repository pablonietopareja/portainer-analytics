# Third-party notices

This inventory describes dependencies and resources used by Portainer Analytics.
Dependencies retain their own licenses. Application code is distributed under
the [MIT license](LICENSE); see [Licensing](docs/LICENSING.md).

## Python runtime dependencies

The following versions and license identifiers were checked against installed
Python distribution metadata and their included license files during preparation.
The release dependency files define the versions to install. Upstream links are
provided for reference; installed distribution notices remain authoritative for
the exact package version.

| Package | Reviewed version | License | Upstream notices |
| --- | --- | --- | --- |
| Requests | 2.34.2 | Apache-2.0 | [License](https://github.com/psf/requests/blob/main/LICENSE), [NOTICE](https://github.com/psf/requests/blob/main/NOTICE) |
| urllib3 | 2.8.0 | MIT | [License](https://github.com/urllib3/urllib3/blob/main/LICENSE.txt) |
| certifi | 2026.7.22 | MPL-2.0 | [License and certificate-bundle provenance](https://github.com/certifi/python-certifi/blob/master/LICENSE) |
| charset-normalizer | 3.5.2 | MIT | [License](https://github.com/jawah/charset_normalizer/blob/master/LICENSE) |
| idna | 3.20 | BSD-3-Clause | [License](https://github.com/kjd/idna/blob/master/LICENSE.md) |

Requests' distributed NOTICE identifies: Copyright 2019 Kenneth Reitz.

The repository declares these dependencies instead of vendoring their source.
Installing them with pip retains the distribution metadata and license files in
`site-packages/*.dist-info/`. Keep those files when packaging or redistributing an
environment or container; do not strip license directories to reduce image size.
This summary is not a substitute for the complete licenses and required notices.

certifi includes Mozilla-derived certificate data. It is installed without local
modifications. Its MPL-covered files retain their own terms; see the upstream
[MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/) for distribution of larger
works and source-availability requirements.

## Development tools

JavaScript browser tests use [Playwright](https://github.com/microsoft/playwright/blob/main/LICENSE)
(Apache-2.0) and [jsdom](https://github.com/jsdom/jsdom/blob/main/LICENSE.txt) (MIT).
Their versions and transitive dependencies are managed by the development package
lockfile. They are not included in the application runtime image. Browser binaries
installed for testing have their own notices and are not included in this source
repository. Preserve dependency notices when distributing development environments.

The reviewed direct versions are Playwright 1.64.0 and jsdom 30.1.2. License metadata
for all 38 locked Node packages was present: MIT, MIT-0, BSD-2-Clause, BSD-3-Clause,
Apache-2.0, ISC, CC0-1.0 and BlueOak-1.0.0. The lockfile records the package-level
identifiers; the installed packages retain their complete license texts.

Python development tools are installation dependencies, not application source.
Their package metadata and installed licenses must be retained when redistributing
the tools. A runtime dependency inventory is not a complete inventory of a separate
development environment.

## Python and the container base

Python includes the PSF license and additional incorporated-software notices;
see [Python's license documentation](https://docs.python.org/3.14/license.html).
The Docker build uses an [official Python image](https://hub.docker.com/_/python),
which also contains operating-system packages with separate licenses.

Building a container does not relicense its base or installed dependencies.
Preserve their notices and review the actual built image, package inventory and
applicable source-distribution obligations before publishing an image. The source
repository contains no redistributed base image or browser binary. Container
license verification is separate from this source inventory; its execution status
is recorded in [the release audit](RELEASE_AUDIT.md).

## Interface resources and names

The inspected interface consists of local HTML, CSS and JavaScript. No third-party
font files, stock images or icon-package assets are bundled. Typography uses local
system-font fallbacks; naming a font family in CSS does not bundle that font.
Navigation symbols are text characters, the brand mark uses CSS, and charts are
drawn by the application's code. No CDN is required for interface resources.

Portainer Analytics is an independent application that connects to the Portainer
API. It is not presented as an official, endorsed or certified Portainer product.
Portainer and other third-party product names belong to their respective owners.
No Portainer logo or Portainer application source is included in this repository.
