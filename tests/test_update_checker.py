"""Tests for update checking, download selection, and self-update scripts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gui_app.about_tab import AboutTabMixin
from gui_app.self_update import build_windows_update_script, windows_update_target_path
from gui_app.update_preferences import (
    is_auto_update_check_enabled,
    load_update_preferences,
    set_auto_update_check_enabled,
    update_preferences_path,
)
from gui_app.update_checker import (
    ReleaseAsset,
    UpdateInfo,
    compare_versions,
    download_release_asset,
    sanitize_filename,
    unique_path,
)


class _StatusVar:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _Button:
    def __init__(self) -> None:
        self.state = ""

    def configure(self, **kwargs) -> None:
        if "state" in kwargs:
            self.state = kwargs["state"]


class _AboutTabHarness(AboutTabMixin):
    def __init__(self) -> None:
        self.update_status_var = _StatusVar()
        self.check_update_button = _Button()
        self.download_update_button = _Button()
        self.download_calls = 0

    def download_latest_update_async(self) -> None:
        self.download_calls += 1


class UpdateCheckerTests(unittest.TestCase):
    """Validate update behavior without making network requests or replacing executables."""

    def test_update_preferences_can_disable_startup_auto_check(self) -> None:
        with TemporaryDirectory() as temp_dir:
            prefs_path = Path(temp_dir) / "update_preferences.json"
            with patch.dict("os.environ", {"FILE_TOOLBOX_UPDATE_PREFS_PATH": str(prefs_path)}):
                self.assertEqual(update_preferences_path(), prefs_path)
                self.assertTrue(is_auto_update_check_enabled())

                set_auto_update_check_enabled(False)

                self.assertFalse(is_auto_update_check_enabled())
                self.assertTrue(load_update_preferences()["skip_auto_update_check"])

                set_auto_update_check_enabled(True)

                self.assertTrue(is_auto_update_check_enabled())
                self.assertNotIn("skip_auto_update_check", load_update_preferences())

    def test_silent_update_check_asks_before_downloading(self) -> None:
        # 自动检测到新版本时也必须先询问用户，避免用户想停留在特定版本时被直接更新。
        info = UpdateInfo(
            current_version="1.2.3",
            latest_version="1.2.4",
            release_name="v1.2.4",
            release_url="https://example.test/release",
            published_at="",
            assets=[ReleaseAsset("FileToolbox.exe", "https://example.test/app.exe")],
            is_update_available=True,
        )
        harness = _AboutTabHarness()

        with TemporaryDirectory() as temp_dir:
            prefs_path = Path(temp_dir) / "update_preferences.json"
            with patch.dict("os.environ", {"FILE_TOOLBOX_UPDATE_PREFS_PATH": str(prefs_path)}):
                with patch("gui_app.about_tab.messagebox.askyesno", return_value=False) as ask:
                    harness._handle_update_result(info, silent=True)

                self.assertFalse(is_auto_update_check_enabled())

        ask.assert_called_once()
        self.assertEqual(harness.download_calls, 0)
        self.assertEqual(harness.download_update_button.state, "normal")
        self.assertIn("已跳过", harness.update_status_var.value)

    def test_confirmed_update_check_starts_download(self) -> None:
        info = UpdateInfo(
            current_version="1.2.3",
            latest_version="1.2.4",
            release_name="v1.2.4",
            release_url="https://example.test/release",
            published_at="",
            assets=[ReleaseAsset("FileToolbox.exe", "https://example.test/app.exe")],
            is_update_available=True,
        )
        harness = _AboutTabHarness()

        with TemporaryDirectory() as temp_dir:
            prefs_path = Path(temp_dir) / "update_preferences.json"
            with patch.dict("os.environ", {"FILE_TOOLBOX_UPDATE_PREFS_PATH": str(prefs_path)}):
                set_auto_update_check_enabled(False)
                with patch("gui_app.about_tab.messagebox.askyesno", return_value=True):
                    harness._handle_update_result(info, silent=True)

                self.assertTrue(is_auto_update_check_enabled())

        self.assertEqual(harness.download_calls, 1)

    def test_update_asset_selection_and_path_helpers(self) -> None:
        # 通过用例：同一个 Release 里有多个平台产物时，应按当前系统选择下载包。
        assets = [
            ReleaseAsset("v1.2.0-FileToolbox-macos.zip", "https://example.test/mac.zip"),
            ReleaseAsset("v1.2.0-FileToolbox.exe", "https://example.test/win.exe"),
        ]
        info = UpdateInfo(
            current_version="1.1.0",
            latest_version="1.2.0",
            release_name="v1.2.0",
            release_url="https://example.test/release",
            published_at="",
            assets=assets,
            is_update_available=True,
        )

        with patch.object(sys, "platform", "win32"):
            self.assertEqual(info.preferred_asset_name, "v1.2.0-FileToolbox.exe")
        with patch.object(sys, "platform", "darwin"):
            self.assertEqual(info.preferred_asset_name, "v1.2.0-FileToolbox-macos.zip")

        self.assertGreater(compare_versions("1.2.0", "1.1.9"), 0)
        self.assertEqual(sanitize_filename('bad:name*.exe'), "bad_name_.exe")
        with TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "FileToolbox.exe"
            existing.write_text("old", encoding="utf-8")
            self.assertEqual(unique_path(existing).name, "FileToolbox_2.exe")

    def test_update_download_rejects_release_without_assets(self) -> None:
        # 失败用例：Release 没有任何资产时不能假装下载成功，应提示用户打开 Release 页面人工查看。
        info = UpdateInfo(
            current_version="1.1.0",
            latest_version="1.2.0",
            release_name="v1.2.0",
            release_url="https://example.test/release",
            published_at="",
            assets=[],
            is_update_available=True,
        )

        with self.assertRaises(RuntimeError):
            download_release_asset(info)

    def test_unknown_version_string_compares_as_zero(self) -> None:
        # 失败/边界用例：无法解析数字的版本号按 0 处理，不应抛异常影响启动检测。
        self.assertEqual(compare_versions("dev", "0.0.0"), 0)
        self.assertLess(compare_versions("dev", "1.0.0"), 0)

    def test_windows_self_update_uses_new_versioned_exe_name(self) -> None:
        # 失败用例：旧逻辑把新 exe 复制到旧路径，导致内容已更新但文件名仍是旧版本号。
        current_app = Path(r"C:\Tools\v1.2.0-FileToolbox.exe")
        asset_path = Path(r"C:\Users\tester\Downloads\v1.2.1-FileToolbox.exe")

        target = windows_update_target_path(asset_path, current_app)
        script = build_windows_update_script(
            asset_path=asset_path,
            current_app=current_app,
            target_app=target,
            pid=1234,
            script_path=Path(r"C:\Temp\FileToolbox_update.bat"),
            vbs_path=Path(r"C:\Temp\FileToolbox_update.vbs"),
            log_path=Path(r"C:\Temp\FileToolbox_update.log"),
        )

        self.assertEqual(target, Path(r"C:\Tools\v1.2.1-FileToolbox.exe"))
        self.assertIn('copy /Y "%NEW_EXE%" "%TARGET_EXE%"', script)
        self.assertIn("Copy failed, retry", script)
        self.assertIn('del "%OLD_EXE%"', script)
        self.assertIn('start "" /D "%TARGET_DIR%" "%TARGET_EXE%"', script)
        self.assertIn("Old exe still exists after retries", script)
        self.assertNotIn("pause", script.lower())


if __name__ == "__main__":
    unittest.main()
