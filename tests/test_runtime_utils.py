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
        runtime_utils.clear_runtime_override()

    def tearDown(self):
        runtime_utils.clear_runtime_override()
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

    def test_load_runtime_config_merges_user_override_after_base_file(self):
        base_config = self.temp_root / "app_runtime.json"
        base_config.write_text(
            '{"tcp_port": 5000, "debug_console_logs": false}',
            encoding="utf-8",
        )

        with (
            mock.patch.object(
                runtime_utils,
                "runtime_file_path",
                return_value=str(base_config),
            ),
            mock.patch.object(
                runtime_utils,
                "runtime_user_dir",
                return_value=self.temp_root,
            ),
        ):
            runtime_utils.save_runtime_user_overrides(
                {
                    "tcp_port": 6200,
                    "debug_console_logs": True,
                }
            )
            resolved_config = runtime_utils.load_runtime_config()

        self.assertEqual(resolved_config["tcp_port"], 6200)
        self.assertTrue(resolved_config["debug_console_logs"])

    def test_save_runtime_user_overrides_writes_json_file(self):
        with mock.patch.object(
            runtime_utils,
            "runtime_user_dir",
            return_value=self.temp_root,
        ):
            override_path = Path(
                runtime_utils.save_runtime_user_overrides(
                    {
                        "lan_bind_host": "0.0.0.0",
                        "tcp_port": 5500,
                    }
                )
            )

        self.assertTrue(override_path.exists())
        self.assertIn(
            '"tcp_port": 5500',
            override_path.read_text(encoding="utf-8"),
        )

    def test_load_persisted_runtime_config_ignores_session_overrides(self):
        base_config = self.temp_root / "app_runtime.json"
        base_config.write_text(
            '{"db_host": "sanctum.local"}',
            encoding="utf-8",
        )

        with (
            mock.patch.object(
                runtime_utils,
                "runtime_file_path",
                return_value=str(base_config),
            ),
            mock.patch.object(
                runtime_utils,
                "runtime_user_dir",
                return_value=self.temp_root,
            ),
        ):
            runtime_utils.set_runtime_override("db_host", "192.168.1.77")
            persisted_config = runtime_utils.load_persisted_runtime_config()
            effective_config = runtime_utils.load_runtime_config()

        self.assertEqual(persisted_config["db_host"], "sanctum.local")
        self.assertEqual(effective_config["db_host"], "192.168.1.77")

    def test_clear_runtime_user_overrides_removes_user_file(self):
        with mock.patch.object(
            runtime_utils,
            "runtime_user_dir",
            return_value=self.temp_root,
        ):
            override_path = Path(
                runtime_utils.save_runtime_user_overrides(
                    {"demo_local_storage_force": True}
                )
            )
            runtime_utils.clear_runtime_user_overrides()

        self.assertFalse(override_path.exists())


if __name__ == "__main__":
    unittest.main()
