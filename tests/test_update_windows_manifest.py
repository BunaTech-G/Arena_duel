from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "update_windows_manifest.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location(
    "update_windows_manifest",
    MODULE_PATH,
)
update_windows_manifest = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(update_windows_manifest)


class UpdateWindowsManifestTests(unittest.TestCase):
    def test_update_manifest_installer_hash_writes_sha256(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "version.json"
            installer_path = Path(temp_dir) / "Setup_ArenaDuel.exe"
            manifest_path.write_text(
                json.dumps(
                    {
                        "version": "1.2.0",
                        "windows_installer_url": ("https://example.com/setup.exe"),
                    }
                ),
                encoding="utf-8",
            )
            installer_path.write_bytes(b"arena-duel-setup")

            installer_hash = update_windows_manifest.update_manifest_installer_hash(
                manifest_path,
                installer_path,
            )

            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(
            installer_hash,
            hashlib.sha256(b"arena-duel-setup").hexdigest(),
        )
        self.assertEqual(
            manifest_data[update_windows_manifest.MANIFEST_HASH_FIELD],
            installer_hash,
        )
        self.assertEqual(manifest_data["version"], "1.2.0")

    def test_update_manifest_installer_hash_rejects_non_object_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "version.json"
            installer_path = Path(temp_dir) / "Setup_ArenaDuel.exe"
            manifest_path.write_text('["not-an-object"]', encoding="utf-8")
            installer_path.write_bytes(b"arena-duel-setup")

            with self.assertRaises(ValueError):
                update_windows_manifest.update_manifest_installer_hash(
                    manifest_path,
                    installer_path,
                )
