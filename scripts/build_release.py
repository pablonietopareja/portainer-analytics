"""Create deterministic source and Docker-context archives without local state."""

from __future__ import annotations

import ast
import hashlib
import io
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    "portainer_console.py",
    "engine.py",
    "persistence.py",
    "dashboard_metrics.py",
    "telemetry.py",
    "requirements.txt",
    "Dockerfile",
    ".dockerignore",
    "VERSION",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
)
SOURCE = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "RELEASE_AUDIT.md",
    "METRICS.md",
    "compose.yaml",
    "portainer-stack.yml",
    ".env.example",
    ".gitignore",
    ".gitleaks.toml",
    ".gitattributes",
    "requirements.in",
    "requirements-dev.in",
    "requirements-dev.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
)
DIRECTORIES = {
    "web": {".js", ".css", ".html"},
    "tests": {".py", ".cjs"},
    "scripts": {".py"},
    "docs": {".md", ".json", ".png"},
    "imgs": {".png"},
    ".github/workflows": {".yml", ".yaml"},
}


def release_name(version):
    """Validate a stable semantic version before deriving archive filenames."""
    component = r"(?:0|[1-9][0-9]*)"
    if not re.fullmatch(rf"{component}\.{component}\.{component}", version):
        raise ValueError("Unsupported release version; expected MAJOR.MINOR.PATCH")
    return "portainer-analytics-" + version


def source_files():
    names = set(RUNTIME + SOURCE)
    for directory, suffixes in DIRECTORIES.items():
        for path in (ROOT / directory).rglob("*"):
            if "__pycache__" not in path.parts and path.suffix in suffixes and path.is_file():
                names.add(path.relative_to(ROOT).as_posix())
    return sorted(names)


def read_files(names):
    root = ROOT.resolve()
    result = {}
    for name in names:
        if (
            not name
            or PurePosixPath(name).is_absolute()
            or PureWindowsPath(name).drive
            or any(part in ("", ".", "..") for part in name.split("/"))
            or "\\" in name
        ):
            raise ValueError(f"Invalid or missing release file: {name}")
        source = root / name
        if source.is_symlink() or not source.resolve().is_relative_to(root) or not source.is_file():
            raise ValueError(f"Invalid or missing release file: {name}")
        data = source.read_bytes()
        if re.search(
            rb"ptr_[A-Za-z0-9_-]{35,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data
        ):
            raise ValueError(f"Credential-like content in {name}; values are not printed")
        if source.suffix == ".py":
            ast.parse(data.decode("utf-8"))
        result[name] = data
    return result


def write_tar(path, payload):
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(payload.items()):
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode, entry.mtime = len(data), 0o644, 0
            archive.addfile(entry, io.BytesIO(data))
    with tarfile.open(path) as archive:
        if set(archive.getnames()) != set(payload):
            raise ValueError("Build-context file list differs")
        for name, data in payload.items():
            if archive.extractfile(name).read() != data:
                raise ValueError(f"Build-context checksum differs: {name}")


def write_zip(archive_path, source):
    """Write and verify a source archive with fixed timestamps and permissions."""
    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for key, data in sorted(source.items()):
            info = zipfile.ZipInfo(key, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(archive_path) as archive:
        if set(archive.namelist()) != set(source):
            raise ValueError("Source archive file list differs")
        for key, data in source.items():
            if archive.read(key) != data:
                raise ValueError(f"Source archive checksum differs: {key}")


def main():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    name = release_name(version)
    source = read_files(source_files())
    runtime = {
        key: value for key, value in source.items() if key in RUNTIME or key.startswith("web/")
    }
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    context = output / (name + "-build-context.tar")
    write_tar(context, runtime)
    archive_path = output / (name + "-source.zip")
    write_zip(archive_path, source)
    checksums = ""
    for path in (context, archive_path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksums += f"{digest}  {path.name}\n"
        print(f"Created {path.name} ({path.stat().st_size} bytes)")
    (output / "SHA256SUMS").write_text(checksums, encoding="utf-8", newline="\n")
    print(f"Verified {len(source)} source files and {len(runtime)} Docker-context files.")
    print("These are local build artifacts. Check RELEASE_AUDIT.md before publication.")


if __name__ == "__main__":
    main()
