# Contributing

Portainer Analytics is an independent project focused on readable operational data, bounded resource usage and predictable behavior on small Docker hosts. I welcome focused bug reports and contributions that preserve those goals.

## Development setup

Use Python 3.14 and a supported Node.js version for the development-only browser tests. Create a Python virtual environment, then install the locked dependencies from the repository root:

```sh
python -m pip install --require-hashes -r requirements-dev.txt
npm ci --ignore-scripts
npm run browser:install
```

The production application is Python plus local HTML, CSS and JavaScript. Node.js and Playwright are development tools, not runtime requirements.

## Checks before opening a pull request

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

The browser tests launch isolated local services with synthetic Portainer responses. They must never depend on a real customer workspace, a private Portainer address or a production token. Use `TEST_PYTHON` to choose the Python executable when necessary.

When changing behavior, add regression coverage that reproduces the original issue. Please keep UI interactions keyboard-accessible, keep missing metrics explicitly unavailable, and do not introduce writes to the Portainer/Docker API.

## Dependency and container changes

Direct Python requirements are declared in `requirements.in` and `requirements-dev.in`. Their corresponding `.txt` files contain resolved hashes. The recorded lock generator is uv 0.11.21; if using a newer version, review the lock diff before committing it.

```sh
uv pip compile requirements.in --universal --python-version 3.14 --generate-hashes --no-emit-index-url --no-header --output-file requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.14 --generate-hashes --no-emit-index-url --no-header --output-file requirements-dev.txt
python -m pip install --require-hashes -r requirements-dev.txt
```

Node packages are locked in `package-lock.json`. Update both package manifests together. The Dockerfile pins the Python base image to a digest; changes to the image or runtime requirements need native AMD64 and ARM64 acceptance tests, plus a review of OS packages and third-party licenses.

## Security review

```sh
python -m pip_audit -r requirements-dev.txt --no-deps --disable-pip
npm audit --audit-level=moderate
python -m bandit -r portainer_console.py engine.py persistence.py dashboard_metrics.py telemetry.py -ll
gitleaks dir . --config .gitleaks.toml --redact --max-archive-depth 3
```

CI runs the dependency advisory and Bandit checks. Gitleaks is a separate local check in the documented release workflow. Do not treat these tools as a substitute for a built-image OS scan or a penetration test.

To regenerate the runtime Python SBOM:

```sh
python -m pip_audit -r requirements.txt --no-deps --disable-pip --format cyclonedx-json --output docs/sbom-runtime.cdx.json
```

The SBOM does not include container OS packages or development browser binaries. Keep [third-party notices](THIRD_PARTY_NOTICES.md) current.

## Documentation and packaging

Write documentation for readers deploying the application for the first time. Use concrete paths and commands, name supported configurations precisely, and separate tested behavior from optional capabilities.

The [CI workflow](.github/workflows/ci.yml) covers Linux/Windows source checks and isolated Linux AMD64/ARM64 container acceptance. It does not publish images or releases. The packaging script produces both a source ZIP (including documentation screenshots) and a Docker build-context tar (runtime files only).

Review [DEPLOYMENT.md](docs/DEPLOYMENT.md), [RELEASE_AUDIT.md](RELEASE_AUDIT.md) and [SECURITY.md](SECURITY.md) when changes affect deployment or access control. Contributions must be original or redistributable under compatible terms.
