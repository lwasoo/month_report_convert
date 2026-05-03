from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gui_app.self_update import build_windows_update_script, windows_update_target_path
from gui_app.update_checker import (
    ReleaseAsset,
    UpdateInfo,
    compare_versions,
    download_release_asset,
    sanitize_filename,
    unique_path,
)


class UpdateCheckerTests(unittest.TestCase):
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
        self.assertIn('del "%OLD_EXE%"', script)
        self.assertIn('start "" "%TARGET_EXE%"', script)
        self.assertNotIn("pause", script.lower())


if __name__ == "__main__":
    unittest.main()
