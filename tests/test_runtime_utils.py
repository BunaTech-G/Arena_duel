import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import runtime_utils


class RuntimeUtilsTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = Path(tempfile.mkdtemp(prefix="arena_duel_runtime_"))

    def tearDown(self):
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_runtime_file_path_prefers_external_file_next_to_exe(self):
        exe_dir = self.temp_root / "portable"
        bundle_dir = self.temp_root / "bundle"
        exe_dir.mkdir(parents=True)
        bundle_dir.mkdir(parents=True)

        external_config = exe_dir / "app_runtime.json"
        bundled_config = bundle_dir / "app_runtime.json"
        external_config.write_text("{}", encoding="utf-8")
        bundled_config.write_text(
            '{"demo_local_storage_force": false}',
            encoding="utf-8",
        )

        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(
                sys,
                "executable",
                str(exe_dir / "ArenaDuel.exe"),
            ),
            mock.patch.object(
                sys,
                "_MEIPASS",
                str(bundle_dir),
                create=True,
            ),
        ):
            resolved_path = runtime_utils.runtime_file_path("app_runtime.json")

        self.assertEqual(Path(resolved_path), external_config)

    def test_runtime_file_path_falls_back_to_bundled_file_when_needed(self):
        exe_dir = self.temp_root / "portable"
        bundle_dir = self.temp_root / "bundle"
        exe_dir.mkdir(parents=True)
        bundle_dir.mkdir(parents=True)

        bundled_config = bundle_dir / "app_runtime.json"
        bundled_config.write_text(
            '{"demo_local_storage_force": true}',
            encoding="utf-8",
        )

        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(
                sys,
                "executable",
                str(exe_dir / "ArenaDuel.exe"),
            ),
            mock.patch.object(
                sys,
                "_MEIPASS",
                str(bundle_dir),
                create=True,
            ),
        ):
            resolved_path = runtime_utils.runtime_file_path("app_runtime.json")

        self.assertEqual(Path(resolved_path), bundled_config)


if __name__ == "__main__":
    unittest.main()
