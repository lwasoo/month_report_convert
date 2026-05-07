"""Tests for routing shared converter logs into GUI runtime queues."""

from __future__ import annotations

import unittest

from report_converter.common import log, route_logs_to


class GuiLogBridgeTests(unittest.TestCase):
    """Cover the bridge between package-level logging and GUI log widgets."""

    def test_common_log_can_be_routed_to_gui_queue(self) -> None:
        # GUI 日志桥接用例：底层 log 仍然打印终端，同时可转发到 GUI 运行日志。
        rows: list[tuple[str, str, str]] = []
        with route_logs_to(lambda message, level, formatted: rows.append((message, level, formatted))):
            log("AI 辅助识别准备: 全文 10 段", level="INFO")

        self.assertEqual(rows[0][0], "AI 辅助识别准备: 全文 10 段")
        self.assertEqual(rows[0][1], "INFO")
        self.assertIn("[INFO] AI 辅助识别准备", rows[0][2])


if __name__ == "__main__":
    unittest.main()
