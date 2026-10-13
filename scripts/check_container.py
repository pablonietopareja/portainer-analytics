"""Acceptance smoke test for an isolated, freshly deployed Compose workspace."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

VERSION = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()


def get(path):
    with urllib.request.urlopen("http://127.0.0.1:8082" + path, timeout=5) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", required=True, help="Fresh Compose test project, not a user workspace"
    )
    args = parser.parse_args()
    command = ["docker", "compose", "-p", args.project]

    def run(*arguments):
        return subprocess.check_output(command + list(arguments), text=True, timeout=90).strip()

    cid = run("ps", "-q", "portainer-analytics")
    info = json.loads(subprocess.check_output(["docker", "inspect", cid], text=True, timeout=15))[0]
    if info["Config"]["User"] != "10001:10001" or not info["HostConfig"]["ReadonlyRootfs"]:
        raise SystemExit("FAIL: container permissions differ from the deployment policy")
    if info["State"]["Health"]["Status"] != "healthy":
        raise SystemExit("FAIL: container is not healthy")
    policy = info["HostConfig"]
    if (
        policy["Privileged"]
        or policy["CapDrop"] != ["ALL"]
        or "no-new-privileges:true" not in policy["SecurityOpt"]
        or any(mount["Destination"] == "/var/run/docker.sock" for mount in info["Mounts"])
    ):
        raise SystemExit("FAIL: container hardening differs from the deployment policy")
    if (
        info["Config"]["Labels"].get("org.opencontainers.image.version") != VERSION
        or info["Config"]["Image"] != "portainer-analytics:" + VERSION
        or get("/api/health").get("version") != VERSION
    ):
        raise SystemExit("FAIL: image or health version differs from VERSION")
    session = get("/api/session")
    if session.get("version") != VERSION:
        raise SystemExit("FAIL: session version differs from VERSION")
    if not session.get("setup_required"):
        raise SystemExit("Refusing to test a configured workspace; use a fresh test volume")
    try:
        get("/api/snapshot")
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
    else:
        raise SystemExit("FAIL: anonymous management API access succeeded")
    # This marker belongs only to the disposable acceptance-test workspace.
    run(
        "exec",
        "-T",
        "portainer-analytics",
        "python",
        "-c",
        "from pathlib import Path; Path('/data/acceptance-marker').write_text('synthetic')",
    )
    run("restart", "portainer-analytics")
    for attempt in range(30):
        try:
            get("/api/health")
            break
        except OSError, ValueError:
            time.sleep(1)
    else:
        raise SystemExit("FAIL: container did not recover after restart")
    value = run(
        "exec",
        "-T",
        "portainer-analytics",
        "python",
        "-c",
        "from pathlib import Path; p=Path('/data/acceptance-marker'); print(p.read_text()); p.unlink()",
    )
    if value != "synthetic" or not get("/api/session").get("setup_required"):
        raise SystemExit("FAIL: restart did not preserve the fresh workspace volume")
    print(
        "PASS: release versions, non-root/read-only image, hardening, health, "
        "anonymous denial and volume persistence."
    )


if __name__ == "__main__":
    main()
