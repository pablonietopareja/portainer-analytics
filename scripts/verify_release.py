"""Check repository boundaries, declared assets, manifests and local documentation links."""

from __future__ import annotations

import ast
import json
import re
from urllib.parse import unquote, urlsplit

import yaml
from build_release import ROOT, RUNTIME, read_files, source_files


def main():
    payload = read_files(source_files())
    for name, data in payload.items():
        if name.endswith(".png"):
            continue
        text = data.decode("utf-8")
        if re.search(r"[A-Za-z]:[\\/]Users[\\/][^\s]+", text):
            raise ValueError(f"Personal path in {name}")
        if name.endswith(".py"):
            ast.parse(text)
        if name.endswith(".md"):
            for target in re.findall(r"\]\(([^\s)]+)\)", text):
                parsed = urlsplit(target)
                if parsed.scheme or target.startswith("#"):
                    continue
                path = (ROOT / name).parent / unquote(parsed.path)
                if not path.resolve().is_relative_to(ROOT) or not path.exists():
                    raise ValueError(f"Broken or external local link in {name}: {target}")
    for page in ("web/index.html", "web/shared.html"):
        for asset in re.findall(r'(?:src|href)="([^"#]+)"', payload[page].decode()):
            if asset == "data:,":  # Explicit empty favicon; no network dependency.
                continue
            if urlsplit(asset).scheme:
                raise ValueError(f"External interface dependency in {page}")
            if not (ROOT / "web" / asset.lstrip("/").split("?")[0]).is_file():
                raise ValueError(f"Missing interface asset: {asset}")
    image = "portainer-analytics:" + payload["VERSION"].decode().strip().replace(".", "-")
    for name in ("compose.yaml", "portainer-stack.yml"):
        compose = yaml.safe_load(payload[name])
        service = compose["services"]["portainer-analytics"]
        if service["image"] != image or service["ports"] != ["8082:8082"]:
            raise ValueError(f"Image tag or port mismatch in {name}")
        if service.get("privileged") or service.get("pull_policy") != "never":
            raise ValueError(f"Unsafe or inconsistent deployment in {name}")
        if service["volumes"] != ["analytics-data:/data"] or not service["read_only"]:
            raise ValueError(f"Invalid persistence or filesystem policy in {name}")
        if name == "portainer-stack.yml" and "build" in service:
            raise ValueError("Portainer stack must use its prebuilt local image")
    dockerfile = payload["Dockerfile"].decode()
    for line in dockerfile.splitlines():
        if line.startswith("COPY ") and "--from=" not in line:
            for source in line.split()[1:-1]:
                if source not in RUNTIME and not any(
                    key.startswith(source + "/") for key in payload
                ):
                    raise ValueError(f"Missing Docker COPY source: {source}")
    package = json.loads(payload["package.json"])
    lock = json.loads(payload["package-lock.json"])
    if package["devDependencies"] != lock["packages"][""]["devDependencies"]:
        raise ValueError("Node dependency manifest differs from its lockfile")
    workflow = yaml.safe_load(payload[".github/workflows/ci.yml"])
    if workflow.get("permissions") != {"contents": "read"}:
        raise ValueError("CI must use read-only repository permissions")
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "uses" in step and not re.fullmatch(r"[^@]+@[a-f0-9]{40}", step["uses"]):
                raise ValueError("CI action must be pinned to a commit")
    print(f"PASS: {len(payload)} source files, assets, local links, Compose and pinned CI actions.")


if __name__ == "__main__":
    main()
