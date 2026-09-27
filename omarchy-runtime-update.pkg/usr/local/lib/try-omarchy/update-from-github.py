#!/usr/bin/env python3
"""Install the runtime package matching Omarchy's latest stable release."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


SPEC = Path("/usr/share/try-omarchy/build-spec.json")
ASSET_NAME = "omarchy-runtime-update.pkg.tar.zst"
MAX_ASSET_BYTES = 128 * 1024 * 1024
USER_AGENT = "Omarchy-VM-Update"
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
PACKAGE_VERSION_RE = re.compile(r"^(\d+\.\d+\.\d+)-(\d+)$")


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"Omarchy VM update: {message}")


def request(url: str, *, accept: str = "application/vnd.github+json"):
    req = urllib.request.Request(
        url,
        headers={"Accept": accept, "User-Agent": USER_AGENT},
    )
    return urllib.request.urlopen(req, timeout=30)


def read_json(url: str) -> dict:
    try:
        with request(url) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        fail(f"could not read GitHub release metadata: {error}")
    if not isinstance(payload, dict):
        fail("GitHub returned malformed release metadata")
    return payload


def load_channel() -> tuple[str, str, str, str]:
    try:
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        update_settings = spec["updates"]
        upstream_repo = update_settings["upstreamGitHubRepository"]
        update_repo = update_settings["githubRepository"]
        asset_name = update_settings["runtimeAsset"]
        bootstrap_version = update_settings["bootstrapRuntimePackageVersion"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        fail(f"guest update channel is not configured: {error}")

    for repo in (upstream_repo, update_repo):
        if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            fail("a configured GitHub repository is invalid")
    if asset_name != ASSET_NAME:
        fail("guest update asset name does not match the supported package contract")
    if not isinstance(bootstrap_version, str) or not PACKAGE_VERSION_RE.fullmatch(bootstrap_version):
        fail("bootstrap runtime package version is invalid")
    return upstream_repo, update_repo, asset_name, bootstrap_version


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION_RE.fullmatch(value)
    if match is None:
        fail(f"Omarchy release version is not a stable x.y.z version: {value!r}")
    return tuple(int(part) for part in match.groups())


def latest_upstream_release(upstream_repo: str) -> tuple[str, tuple[int, int, int]]:
    release = read_json(f"https://api.github.com/repos/{upstream_repo}/releases/latest")
    tag = release.get("tag_name")
    if not isinstance(tag, str):
        fail("latest Omarchy release has no tag")
    version = parse_version(tag)
    if release.get("draft") is not False or release.get("prerelease") is not False:
        fail("latest Omarchy release is not a published stable release")
    return tag if tag.startswith("v") else f"v{tag}", version


def matching_runtime_release(update_repo: str, tag: str) -> tuple[dict, dict, str]:
    encoded_tag = urllib.parse.quote(tag, safe="")
    release = read_json(
        f"https://api.github.com/repos/{update_repo}/releases/tags/{encoded_tag}"
    )
    if release.get("tag_name") != tag:
        fail(f"{update_repo} has no runtime release matching Omarchy {tag}")
    if release.get("draft") is not False or release.get("prerelease") is not False:
        fail(f"runtime release {tag} is not a published stable release")
    html_url = urllib.parse.urlparse(release.get("html_url", ""))
    if html_url.scheme != "https" or html_url.hostname != "github.com":
        fail("GitHub runtime release URL is invalid")

    assets = release.get("assets")
    if not isinstance(assets, list):
        fail(f"runtime release {tag} has no asset list")
    matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == ASSET_NAME]
    if len(matches) != 1:
        fail(f"runtime release {tag} must contain exactly one {ASSET_NAME} asset")
    asset = matches[0]
    digest = asset.get("digest")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        fail("GitHub did not provide a SHA-256 digest for the runtime package")
    size = asset.get("size")
    if not isinstance(size, int) or size <= 0 or size > MAX_ASSET_BYTES:
        fail("GitHub runtime package size is invalid or exceeds the safety limit")
    download_url = asset.get("browser_download_url", "")
    parsed_asset_url = urllib.parse.urlparse(download_url)
    expected_path = f"/{update_repo}/releases/download/{tag}/{ASSET_NAME}"
    if (
        parsed_asset_url.scheme != "https"
        or parsed_asset_url.hostname != "github.com"
        or parsed_asset_url.path != expected_path
    ):
        fail("GitHub runtime package URL does not match the configured release")
    return release, asset, digest.removeprefix("sha256:")


def installed_package_version() -> str:
    try:
        result = subprocess.run(
            ["pacman", "-Q", "try-omarchy-runtime"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        fail(f"could not read the installed Try Omarchy runtime version: {error}")
    fields = result.stdout.strip().split()
    if len(fields) != 2 or fields[0] != "try-omarchy-runtime" or not PACKAGE_VERSION_RE.fullmatch(fields[1]):
        fail("installed Try Omarchy runtime package version is malformed")
    return fields[1]


def compare_package_versions(left: str, right: str) -> int:
    try:
        result = subprocess.run(
            ["vercmp", left, right],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        fail(f"Arch version comparison failed: {error}")
    try:
        return int(result.stdout.strip())
    except ValueError:
        fail("Arch version comparison returned an invalid result")


def download(url: str, expected_size: int, expected_sha256: str, path: Path) -> None:
    digest = hashlib.sha256()
    count = 0
    try:
        with request(url, accept="application/octet-stream") as response, path.open("wb") as target:
            final_url = urllib.parse.urlparse(response.geturl())
            if (
                final_url.scheme != "https"
                or final_url.hostname != "github.com"
                and not (final_url.hostname or "").endswith(".githubusercontent.com")
            ):
                fail("GitHub redirected the package download to an unsupported host")
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                count += len(block)
                if count > expected_size or count > MAX_ASSET_BYTES:
                    fail("downloaded package is larger than GitHub's release metadata")
                digest.update(block)
                target.write(block)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        fail(f"could not download the GitHub runtime package: {error}")
    if count != expected_size:
        fail(f"download size mismatch: expected {expected_size} bytes, received {count}")
    if digest.hexdigest() != expected_sha256:
        fail("downloaded runtime package SHA-256 does not match GitHub release metadata")


def package_identity(path: Path, expected_tag: str) -> str:
    try:
        result = subprocess.run(
            ["pacman", "-Qip", "--color", "never", str(path)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        fail(f"pacman could not inspect the downloaded package: {error}")
    fields = {}
    for line in result.stdout.splitlines():
        match = re.fullmatch(r"(Name|Version|Architecture)\s*:\s*(.+?)\s*", line)
        if match:
            fields[match.group(1)] = match.group(2)
    name, version, architecture = (
        fields.get("Name", ""),
        fields.get("Version", ""),
        fields.get("Architecture", ""),
    )
    tag_version = expected_tag.removeprefix("v")
    if name != "try-omarchy-runtime" or not PACKAGE_VERSION_RE.fullmatch(version):
        fail("GitHub asset is not a valid try-omarchy-runtime package")
    if not version.startswith(tag_version + "-"):
        fail(f"runtime package version {version} does not match Omarchy release {expected_tag}")
    if architecture not in {"any", "aarch64"} or platform.machine() not in {"aarch64", "arm64"}:
        fail("GitHub runtime package is not compatible with this ARM64 guest")
    return version


def install_package(path: Path) -> None:
    try:
        subprocess.run(["sudo", "pacman", "-U", "--noconfirm", str(path)], check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        fail(f"pacman could not install the GitHub runtime package: {error}")


def main() -> None:
    upstream_repo, update_repo, _asset_name, bootstrap_version = load_channel()
    tag, upstream_version = latest_upstream_release(upstream_repo)
    current_package_version = installed_package_version()
    current_upstream_version = parse_version(current_package_version.split("-", 1)[0])
    if upstream_version < current_upstream_version:
        fail(
            f"GitHub's latest Omarchy release {tag} is older than installed runtime "
            f"{current_package_version}"
        )
    same_release_as_installed = upstream_version == current_upstream_version
    if same_release_as_installed and compare_package_versions(
        current_package_version, bootstrap_version
    ) >= 0:
        print(f"Omarchy VM runtime is current ({current_package_version}, Omarchy {tag}).")
        return

    _release, asset, digest = matching_runtime_release(update_repo, tag)
    print(f"Update Omarchy VM runtime for Omarchy {tag} from {update_repo}…")
    with tempfile.TemporaryDirectory(prefix="omarchy-vm-update-") as temporary:
        package = Path(temporary) / ASSET_NAME
        download(asset["browser_download_url"], asset["size"], digest, package)
        actual_version = package_identity(package, tag)
        version_order = compare_package_versions(actual_version, current_package_version)
        if version_order <= 0:
            if same_release_as_installed:
                fail(
                    f"bootstrap runtime package {actual_version} is not newer than installed "
                    f"package {current_package_version}"
                )
            fail(
                f"runtime package {actual_version} is not newer than installed "
                f"package {current_package_version}"
            )
        if same_release_as_installed and compare_package_versions(
            actual_version, bootstrap_version
        ) < 0:
            fail(f"bootstrap runtime package must be at least {bootstrap_version}")
        install_package(package)
    print(f"Omarchy VM runtime updated to {actual_version}.")


if __name__ == "__main__":
    main()
