# Deployment guide

Portainer Analytics 1.0.0 runs directly with Python or as a non-root Linux container. It is configured through its browser interface and stores state in SQLite. Container deployment examples target **Docker Standalone**, not Docker Swarm stacks.

## Before deploying

Use a Portainer **Server** URL reachable from the application and an API token authorized to read the intended Docker environments. An Agent address is not a Portainer Server API URL. Keep Portainer TLS verification enabled and configure trust for your server's certificate.

Container deployment requires Linux Docker Engine with Compose v2. The published 1.0.0 candidate passed native AMD64 and ARM64 container acceptance; its Windows source job failed in release-path regression tests. Remote verification of the remediation is pending. ARM64 requires a 64-bit host OS. The [verification record](../RELEASE_AUDIT.md) states the available evidence and limitations.

## Docker Compose

From the repository root:

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=50
```

Open `http://localhost:8082` **on the Docker host**. Compose publishes `127.0.0.1:8082:8082` by default while the application listens on `0.0.0.0:8082` inside its container. Host loopback is not reachable from another computer or a separate container.

Use Docker Engine 28.0.0 or newer for the documented localhost publication restriction. Older versions can expose localhost-published ports to other hosts on the same layer-2 network. Custom direct-routing configurations can also broaden container access; review your daemon/network settings and firewall. See [Docker port-publishing guidance](https://docs.docker.com/engine/network/port-publishing/).

For a remote Docker host, use a secure tunnel for first-use setup. With SSH available, run the following in PowerShell and enter your SSH destination, such as a configured alias or an account and hostname:

```powershell
$SshDestination = Read-Host "SSH destination"
ssh -L 8082:127.0.0.1:8082 $SshDestination
```

Then open `http://localhost:8082` on your computer. Keep the tunnel running during setup; select a different local tunnel port if `8082` is already occupied.

First-use setup requests an administrator password of at least 12 characters, the Portainer Server URL and API token. The connection must validate before the workspace is created. An empty workspace can be claimed by its first administrator, so initialize it before allowing broader access.

The service runs under UID/GID `10001:10001`, with a read-only root filesystem, a bounded temporary filesystem, dropped Linux capabilities, `no-new-privileges` and an `analytics-data` volume at `/data`. No Docker socket or privileged mode is required.

### Opt in to LAN access

Set `CONSOLE_BIND_ADDRESS` in an untracked local `.env` file to the Docker host's trusted LAN address. A binding of `0.0.0.0` exposes all host IPv4 interfaces and requires deliberate firewall restrictions. Recreate the service after changing the mapping:

```sh
docker compose config --quiet
docker compose up -d --build
```

Open the host address with port `8082`. For a DNS name, also set `CONSOLE_ALLOWED_HOSTS`; this Host-header check is not a network firewall. Prefer HTTPS and authenticated ingress for remote access. Configure application variables in the service environment when adding them; a local `.env` supplies Compose substitutions and does not automatically pass every variable to the container.

To change the published port, edit the host-side port in `ports:` while retaining container port `8082`. The interface uses the browser's actual port. Changing the application container port additionally requires updating its environment, mapping and Docker healthcheck together.

## Build and deploy through Portainer

Create the source context locally:

```sh
python scripts/build_release.py
```

In the desired **Docker Standalone** environment:

1. Open **Images > Build a new image > Upload**.
2. Select `dist/portainer-analytics-1.0.0-build-context.tar`.
3. Set image tag `portainer-analytics:1.0.0` and Dockerfile path `Dockerfile`.
4. Build and confirm that the image appears in that environment's image list.
5. Open **Stacks > Add stack > Upload** and select `portainer-stack.yml`.
6. Disable image re-pulling and deploy in the same environment where the image was built.
7. Check container health, access host loopback locally or through an SSH tunnel, and complete setup.

The Portainer stack also publishes on host loopback by default. To permit LAN access, deliberately replace `127.0.0.1` in the stack's `ports:` entry with the host's trusted LAN address, and configure any required public origin and allowed hostnames in its `environment:` section. Preserve the container-side port and security settings.

Docker Swarm published ports have different semantics and do not provide this host-loopback binding. Do not deploy this stack unchanged in Swarm or assume the loopback restriction will apply there. Use the documented Standalone deployment or separately design and verify Swarm ingress controls.

The `.tar` is a Docker **build context**, not a saved image archive for **Images > Import**. The build host needs access to the pinned base image and Python package index. An image built on one standalone endpoint is not automatically available on another. If deployment fails, inspect the failing request and Docker/Portainer logs, and verify the exact image tag and endpoint.

## Persistent storage and upgrades

SQLite retains administrator password hashes, the Portainer connection, dashboards, shares and selected-metric history in `/data`. **API tokens are not encrypted by the application.** Restrict volume and backup access.

Compose and Portainer usually prefix `analytics-data` with the project or stack name. Keep that original name or explicitly reattach the original volume when upgrading; a new volume creates an empty workspace. Existing dashboards and history use the same database format during the 1.0.0 transition.

Before upgrading, stop application writes and take a safe SQLite backup, or use SQLite's backup API. Preserve the volume while replacing the image. Locally, run `docker compose up -d --build`. In Portainer, build `portainer-analytics:1.0.0`, update the existing stack's `image:` value, keep image re-pulling disabled for the local image and retain its data-volume mapping.

The 1.0.0 manifests change the default host publication to loopback. Existing LAN deployments must review that mapping before applying the new manifest. A volume migration is not required solely for this network change. Keep a verified pre-upgrade backup for rollback; never use `down --volumes` on a workspace whose data you need.

The browser's theme preference may return to the system default during the 1.0.0 interface transition. Select your preferred theme again if needed; saved SQLite state and dashboard data are unaffected.

Do not add `build: .` to a Portainer stack without a real build context. Never place tokens, databases or backups in the repository or Docker build context.

## HTTPS and reverse proxies

The built-in service uses HTTP. For remote browser access, terminate HTTPS at a reverse proxy, preserve Host, and set the service environment to your actual external origin and hostname:

```text
CONSOLE_PUBLIC_URL=https://analytics.example.com
CONSOLE_ALLOWED_HOSTS=analytics.example.com
```

The configured HTTPS origin enables Secure session cookies; clients must use that HTTPS URL. Forwarded headers alone do not enable Secure cookies. `CONSOLE_ALLOWED_HOSTS` accepts DNS names, not URLs or port numbers.

A proxy running directly on the Docker host can reach the published loopback port. A proxy in another container should share a Docker network and connect to `http://portainer-analytics:8082`; its own `127.0.0.1` refers to itself. Review network membership: host-loopback publication does not isolate the application from containers sharing its network. Restrict ingress, rate-limit requests as appropriate, and keep first-use setup private.

An active dashboard share URL is a bearer credential. Anyone receiving it can see the selected dashboard data; revoke or rotate the link when access should end.

## Isolated container acceptance

On a fresh, disposable Docker workspace:

```sh
docker compose -p analytics-acceptance config --quiet
docker compose -p analytics-acceptance up -d --build --wait --wait-timeout 120
python scripts/check_container.py --project analytics-acceptance
docker compose -p analytics-acceptance logs --tail=50
docker compose -p analytics-acceptance down
```

The script requires an unconfigured workspace. It checks the non-root account, read-only filesystem, health, anonymous management denial and persistence of a temporary marker through restart. It does not create a production administrator or use a live Portainer token. Add `--volumes` only when deliberately deleting this disposable test data. Never reuse the acceptance project against a real stack.

For integration qualification, use a separate test Portainer Server and record its Portainer, Agent and Docker versions. Verify environment switching, available telemetry, dashboard editing/history, sharing/revocation and restart persistence. Synthetic CI and screenshots do not prove exact live-version compatibility.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Remote browser cannot connect | Default publication is host loopback; use a tunnel, HTTPS proxy or deliberate LAN binding |
| Port 8082 unavailable | Check competing listeners or change the host-side published port |
| Cannot connect to Portainer | Verify Server URL, DNS, certificate trust, token permissions and container egress |
| Image tag missing | Build `portainer-analytics:1.0.0` in the same environment used by the stack |
| `Host not allowed` | Configure the external DNS name in `CONSOLE_ALLOWED_HOSTS` |
| Login loops behind a proxy | Verify HTTPS `CONSOLE_PUBLIC_URL`, preserved Host and the actual browser URL |
| Missing optional metrics | Confirm API/runtime capabilities and permissions; missing is not zero |
| Dashboards disappeared | Reattach the original `/data` volume and project/stack name |
| Healthcheck fails | Inspect logs, `/api/health`, dependencies and volume write permissions |

See [README](../README.md), [Metrics](../METRICS.md) and [Security](../SECURITY.md) for product scope and operational boundaries.
