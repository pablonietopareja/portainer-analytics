# Deployment guide

I designed Portainer Analytics to run either directly under Python or in a small, non-root container. The runtime is configured through its own browser interface and stores application state in SQLite. Docker/Portainer source packaging and native AMD64/ARM64 container acceptance are covered by the repository CI; connecting a particular Portainer installation requires the environment-specific steps below.

## 1. Before deploying

Confirm that your target is a Docker environment, that Portainer Server is reachable **from the console container**, and that you have a Portainer API token authorized to read the intended environments. An Agent port or Agent address is **not** the Portainer Server API URL.

Use Linux Docker Engine with Compose v2 for container deployment. AMD64 and 64-bit ARM64 builds have passed native CI acceptance. A Raspberry Pi must run a 64-bit OS for the ARM64 target. Port 8082 must be available unless you deliberately change the exposed port.

## 2. Docker Compose

From the repository root:

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=50
```

Open `http://localhost:8082` or the trusted gateway address on port `8082`. First-use setup requests an administrator password of at least 12 characters, the Portainer Server URL and an API token. The application validates the connection before creating the workspace.

The Compose service runs under UID/GID `10001:10001`, with a read-only root filesystem, limited temporary filesystem, dropped Linux capabilities and a dedicated `analytics-data` volume mounted at `/data`. It does not mount `/var/run/docker.sock` and does not need privileged access.

## 3. Portainer-only image build and stack deployment

If you want to build and deploy entirely through Portainer, create the upload archive locally first:

```sh
python scripts/build_release.py
```

Then, in the desired **Docker Standalone** environment:

1. Open **Images → Build a new image → Upload**.
2. Select `dist/portainer-analytics-alpha-3-build-context.tar`.
3. Enter image tag **`portainer-analytics:alpha-3`** and Dockerfile path **`Dockerfile`**.
4. Build the image and confirm it appears in that environment's **Images** list.
5. Open **Stacks → Add stack → Upload** and select `portainer-stack.yml`.
6. Disable automatic image re-pulling and deploy the stack in the **same** environment where the image was built.
7. Check that the container becomes healthy and open port `8082`.

The generated `.tar` is a Docker **build context**, not a saved image archive for **Images → Import**. The build host needs access to the pinned base image and Python package index. Images created on one standalone Docker endpoint are not automatically available on another.

If Portainer reports HTTP 500 while building or deploying, inspect the actual failing request and Docker/Portainer logs. A frequent configuration error is tagging the image `latest` while the stack requests `alpha-3`.

## 4. Isolated container acceptance

For regression testing on a **fresh, disposable** Docker host/workspace, use:

```sh
docker compose -p analytics-acceptance config --quiet
docker compose -p analytics-acceptance up -d --build --wait --wait-timeout 120
python scripts/check_container.py --project analytics-acceptance
docker compose -p analytics-acceptance logs --tail=50
```

The script is intentionally limited to an unconfigured workspace. It checks the non-root account, read-only filesystem, health status, denial of anonymous management access and persistence of a temporary marker through restart. It does not create a production administrator or exercise a live Portainer token.

The GitHub Actions workflow has passed this acceptance sequence on both native Linux AMD64 and ARM64 runners. To qualify your own integration, connect a **test Portainer server** and check environment switching, container stats, dashboard editing, historical samples, sharing/revocation, theme behavior and persistence after restart. Record the exact Portainer, Agent and Docker versions in your deployment notes.

When finished, stop only the disposable test stack:

```sh
docker compose -p analytics-acceptance down
```

Add `--volumes` only if you deliberately want to delete that test workspace's data. Never reuse the acceptance project name against an existing production stack without reviewing the consequences.

## 5. Persistent storage and upgrades

The named volume `analytics-data` is mounted at `/data`. Compose and Portainer commonly prefix the actual Docker volume name with the project/stack name. Keep the original stack name or explicitly reattach its original volume during upgrades; otherwise you will see a new, empty workspace.

Before upgrades, stop application writes and make a safe SQLite backup (or use SQLite's backup API). Preserve the existing volume while replacing the application image. For local builds use `docker compose up -d --build`; for Portainer, build a new tag, update the existing stack's `image:` value and leave image re-pulling disabled when using the locally built image.

Do not add `build: .` to a Portainer stack unless a real build context exists on the target daemon. Do not place tokens, live databases or backups inside your Git repository or Docker build context.

## 6. HTTP, HTTPS and network boundaries

For access outside a controlled LAN, deploy an HTTPS reverse proxy and set:

```text
CONSOLE_PUBLIC_URL=https://analytics.example.com
CONSOLE_ALLOWED_HOSTS=analytics.example.com
```

Preserve the Host header through the proxy. The public HTTPS origin enables Secure session cookies; browsers must use that HTTPS address. The built-in service still listens over HTTP behind the proxy. Apply additional ingress restrictions, authentication controls and rate limits as appropriate.

Avoid publicly exposing the unconfigured first-use screen. Keep application storage and Portainer tokens private. A shared dashboard URL is a read credential: revoke or rotate it if it should no longer grant access.

## 7. Troubleshooting

| Symptom | Check |
| --- | --- |
| Port 8082 is unavailable | Another service may already be listening; change the published port or stop the conflicting service |
| Cannot connect to Portainer | Use the Portainer **Server** API URL, not an Agent address; verify DNS, TLS trust, token and network access |
| No image with tag `alpha-3` | Build the image in the same Docker environment and use the exact image tag requested by the stack |
| `Host not allowed` | Add the external DNS hostname to `CONSOLE_ALLOWED_HOSTS` or use an accepted private LAN hostname/address |
| Login loops behind a proxy | Configure the correct HTTPS `CONSOLE_PUBLIC_URL`, preserve Host and use the external HTTPS endpoint |
| Missing optional Agent/host metrics | Verify Docker and Agent capability, permissions and runtime support; missing is not zero |
| Dashboards have disappeared | Check whether a new named volume or stack name was used instead of the original `/data` volume |
| Container fails its healthcheck | Inspect `docker compose logs`, `/api/health`, dependency availability and data-volume write permissions |

For architectural scope see [README.md](../README.md), metric semantics in [METRICS.md](../METRICS.md), and the exact recorded test outcomes in [RELEASE_AUDIT.md](../RELEASE_AUDIT.md).
