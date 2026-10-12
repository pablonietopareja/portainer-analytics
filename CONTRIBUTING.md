# Contributing

Use Python 3.14 and Node 24 for development. Follow the virtual-environment setup
in [README.md](README.md), then install `requirements-dev.txt` with `--require-hashes`
and run `npm ci --ignore-scripts`. Install the test browser with
`npm run browser:install`.

Keep changes focused, explain the operational problem, and include a regression
test for correctness or security fixes. Synthetic fixtures belong in `tests/`;
do not record a real Portainer response, database, token, IP inventory or log as
a fixture. Contributions must be compatible with [the MIT license](LICENSE).

## Checks before a change

```sh
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -v
npm run check
npm test
npm run test:browser
python scripts/verify_release.py
python scripts/build_release.py
```

Python checks cover parsing, lint and formatting; JavaScript checks cover syntax,
chart behavior, DOM interactions and actual Chromium rendering. There is no
separate static type-checker configuration. Do not describe syntax checks as type
checking. Browser tests use synthetic HTTP fixtures and temporary data directories.

## Dependency updates

Runtime dependencies are declared in `requirements.in`. Development requirements
extend them in `requirements-dev.in`. Use uv 0.11.21 (the recorded lock generator)
or review changes produced by a newer version:

```sh
uv pip compile requirements.in --universal --python-version 3.14 --generate-hashes --no-emit-index-url --no-header --output-file requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.14 --generate-hashes --no-emit-index-url --no-header --output-file requirements-dev.txt
python -m pip install --require-hashes -r requirements-dev.txt
```

Change the direct pin before updating it; use `--upgrade` deliberately for
transitive upgrades. Review licenses and vulnerabilities, then rerun checks.
For Node, use `npm install --save-dev --save-exact PACKAGE@VERSION --ignore-scripts`
and commit both package manifests. Node dependencies are development-only.

The Dockerfile pins the base manifest digest as well as the Python version.
Update both `FROM` lines together, verify AMD64/ARM64 manifests, and rerun native
container acceptance tests. A digest provides reproducibility, not automatic
security updates.

## Security scans

```sh
python -m pip_audit -r requirements-dev.txt --no-deps --disable-pip
npm audit --audit-level=moderate
python -m bandit -r portainer_console.py engine.py persistence.py dashboard_metrics.py telemetry.py -ll
gitleaks dir . --config .gitleaks.toml --redact --max-archive-depth 3
```

The preparation scan used Gitleaks 8.30.1. Install it from its official distribution
and verify its checksum. Advisory tools send public package names and versions to
their services; source code and application settings are not scan inputs to those
services. A clean scan is not a proof that all vulnerabilities are absent.

Regenerate the runtime-only SBOM with:

```sh
python -m pip_audit -r requirements.txt --no-deps --disable-pip --format cyclonedx-json --output docs/sbom-runtime.cdx.json
```

The SBOM lists Python runtime libraries, not OS packages or browser tooling. Keep
[third-party notices](THIRD_PARTY_NOTICES.md) current.

## CI and release review

The [CI workflow](.github/workflows/ci.yml) runs Windows/Linux source checks and
native AMD64/ARM64 container jobs. It uses pinned actions and read-only repository
permissions; it does not publish packages, images or releases. Actual CI execution
is separate from local workflow validation.

Before a release, follow the [container acceptance steps](docs/DEPLOYMENT.md),
review licenses and secrets, and update [RELEASE_AUDIT.md](RELEASE_AUDIT.md) with
executed results. Build artifacts are generated under ignored `dist/`; source
archives and build contexts have different purposes.
