# Deployment and container acceptance

The application is configured in its browser interface and stores persistent state
in `/data`. A new volume contains no connection, password or dashboards. The server
URL must address the **Portainer server**, not its Agent.

The source/browser test suite is synthetic. This release candidate's Docker build,
native ARM64 execution and live Portainer integration remain **NOT RUN** in the
preparation environment. Run the following checks on an isolated Docker test host
before accepting the container for deployment. No base image is distributed here.

## Local Docker acceptance

Use a Linux AMD64 or ARM64 Docker host with Compose v2. These commands use a new
project name and test volume; port 8082 must be free:

```sh
docker compose -p analytics-acceptance config --quiet
docker compose -p analytics-acceptance up -d --build --wait --wait-timeout 120
python scripts/check_container.py --project analytics-acceptance
docker compose -p analytics-acceptance logs --tail=50
```

The check requires an unconfigured test workspace. It verifies the non-root user,
read-only filesystem, health, denied anonymous management access and persistent
volume behavior after restart. It writes and removes a synthetic marker in that
test volume. It does not connect to Portainer or create dashboards.

Then open `http://TEST_HOST_IP:8082`, complete setup against a **test** Portainer
server and verify environment navigation, fresh measurements, dashboard editing,
sharing/revocation, themes and restart persistence. Record the Docker, Compose,
Portainer and Agent versions and CPU architecture in the release audit.

After testing, stop the test stack with:

```sh
docker compose -p analytics-acceptance down
```

Keep the volume if you want to retain the test workspace. Remove only that test
volume deliberately when finished. Do not reuse these test commands for an existing
production stack without reviewing the project and volume names.

## Portainer-only deployment

1. Generate a clean context with `python scripts/build_release.py`.
2. Select the target **Docker Standalone** environment in Portainer.
3. Open **Images > Build a new image > Upload** and choose
   `dist/portainer-analytics-alpha-3-build-context.tar`.
4. Set the image name to `portainer-analytics:alpha-3` and the Dockerfile path to
   `Dockerfile`. Build it and verify the exact tag under Images.
5. In the same environment, open **Stacks > Add stack > Upload**, select
   `portainer-stack.yml`, and deploy with **Re-pull image / Always pull** disabled.
6. Check the container becomes healthy and open `http://GATEWAY_IP:8082`.

The tar has the Dockerfile at its root. It is not a saved image and cannot be used
with **Images > Import**. The build takes place on the selected Docker daemon and
needs registry/Python package access. Native building selects the host architecture;
a Raspberry Pi should use a 64-bit Linux OS. No 32-bit target is qualified.

These are the documented Portainer workflows:
[image builds](https://docs.portainer.io/user/docker/images/build),
[tar upload form](https://github.com/portainer/portainer/blob/2.21.5/app/docker/views/images/build/buildimage.html),
[stack uploads](https://docs.portainer.io/user/docker/stacks/add).
They are instructions to validate for this candidate, not evidence that a deployment
has already succeeded.

If Portainer shows a generic HTTP 500, inspect the failed request's Response in the
browser's Network tab or the Portainer server container logs. A common diagnosable
case is an exact image-tag mismatch: `latest` does not satisfy `alpha-3`, and images
on one environment are not automatically available on another.

## Persistent data and upgrades

The Compose volume `analytics-data` mounts at `/data`; Docker/Portainer normally
prefixes its actual name with the stack/project name. Preserve the same volume when
upgrading. Changing the stack name without selecting the old volume creates a new
workspace. Back up SQLite safely before upgrading, then stop/replace the container
while retaining the volume. Dashboard history is subject to rolling retention.

For a local source update, run `docker compose up -d --build`. In Portainer, build
with a new version tag, change `image:` in the existing stack editor and update the
stack with registry pulling disabled. Do not introduce `build: .` into a Portainer
stack that has no corresponding source directory available to its build process.

## HTTPS and network access

Use a reverse proxy with TLS for access beyond a trusted network. Preserve the
external Host header and set:

```text
CONSOLE_PUBLIC_URL=https://analytics.example.com
CONSOLE_ALLOWED_HOSTS=analytics.example.com
```

TLS terminates at the proxy. The configured HTTPS public URL enables Secure session
cookies; access the external HTTPS address rather than the internal HTTP listener.
Do not expose an unconfigured first-use page to an untrusted network.

No Docker socket, privileged mode, host filesystem mounts or write access to the
monitored Docker environment is needed. The Portainer token must permit the read
operations and environments you want to monitor. Unsupported optional Agent APIs
are reported as unavailable.
