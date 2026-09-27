import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "omarchy-runtime-update.pkg/usr/local/lib/try-omarchy/update-from-github.py"
SPEC = importlib.util.spec_from_file_location("update_from_github", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class UpdateContractTests(unittest.TestCase):
    class Response:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def geturl(self):
            return "https://github.com/JoyfulOak/omarchy-vm-update/releases/download/v4.0.4/test"

        def read(self, _size):
            body, self.body = self.body, b""
            return body

    def test_stable_version_ordering(self):
        self.assertEqual(MODULE.parse_version("v4.0.4"), (4, 0, 4))
        self.assertLess(MODULE.parse_version("v4.0.4"), MODULE.parse_version("v4.0.10"))
        with self.assertRaises(SystemExit):
            MODULE.parse_version("v4.0.4-rc1")

    def test_latest_release_requires_published_stable_tag(self):
        with patch.object(MODULE, "read_json", return_value={
            "tag_name": "v4.0.4", "draft": False, "prerelease": False
        }):
            self.assertEqual(MODULE.latest_upstream_release("omacom/omarchy"), ("v4.0.4", (4, 0, 4)))
        with patch.object(MODULE, "read_json", return_value={
            "tag_name": "v4.0.5-rc1", "draft": False, "prerelease": True
        }):
            with self.assertRaises(SystemExit):
                MODULE.latest_upstream_release("omacom/omarchy")

    def test_manifest_contract_and_architecture(self):
        manifest = {
            "schemaVersion": 1,
            "omarchyVersion": "4.0.4",
            "packageName": "try-omarchy-runtime",
            "packageVersion": "4.0.4-6",
            "architecture": "any",
            "runtimeAsset": MODULE.ASSET_NAME,
        }
        self.assertEqual(MODULE.validate_manifest(manifest, "v4.0.4"), "4.0.4-6")
        malformed = dict(manifest, architecture="x86_64")
        with self.assertRaises(SystemExit):
            MODULE.validate_manifest(malformed, "v4.0.4")

    def test_release_requires_exact_manifest_and_package_assets(self):
        def asset(name):
            return {
                "name": name,
                "digest": "sha256:" + "a" * 64,
                "size": 10,
                "browser_download_url": f"https://github.com/JoyfulOak/omarchy-vm-update/releases/download/v4.0.4/{name}",
            }

        release = {
            "tag_name": "v4.0.4", "draft": False, "prerelease": False,
            "html_url": "https://github.com/JoyfulOak/omarchy-vm-update/releases/tag/v4.0.4",
            "assets": [asset(MODULE.MANIFEST_ASSET_NAME), asset(MODULE.ASSET_NAME)],
        }
        with patch.object(MODULE, "read_json", return_value=release):
            result = MODULE.matching_runtime_release("JoyfulOak/omarchy-vm-update", "v4.0.4")
        self.assertEqual(result[1]["name"], MODULE.MANIFEST_ASSET_NAME)
        with patch.object(MODULE, "read_json", return_value=dict(release, assets=[asset(MODULE.ASSET_NAME)])):
            with self.assertRaises(SystemExit):
                MODULE.matching_runtime_release("JoyfulOak/omarchy-vm-update", "v4.0.4")

    def test_checksum_mismatch_aborts_download(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(MODULE, "request", return_value=self.Response(b"payload")):
                with self.assertRaises(SystemExit):
                    MODULE.download("https://github.com/example/file", 7, "0" * 64, Path(directory) / "file")

    def test_install_failure_is_reported(self):
        with patch.object(MODULE.subprocess, "run", side_effect=MODULE.subprocess.CalledProcessError(1, "pacman")):
            with self.assertRaises(SystemExit):
                MODULE.install_package(Path("/tmp/package.pkg.tar.zst"))

    def test_update_script_preserves_home_and_omits_unreviewed_steps(self):
        script = (ROOT / "omarchy-runtime-update.pkg/usr/bin/omarchy-update").read_text()
        self.assertNotIn("omarchy-update-pkg-prune", script)
        self.assertNotIn("omarchy-migrate", script)
        self.assertNotIn("omarchy-hook post-update", script)
        self.assertNotIn("omarchy-update-aur-pkgs", script)
        self.assertNotIn("omarchy-update-mise", script)
        self.assertNotIn("omarchy-update-orphan-pkgs", script)
        self.assertNotIn("continuing with Arch updates", script)


if __name__ == "__main__":
    unittest.main()
