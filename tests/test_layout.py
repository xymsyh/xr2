"""验证重构后的真实模块连接、路径隔离与入口行为。"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from xiaoxiao_reader import paths
from xiaoxiao_reader.config import 初始化配置, 读取配置


class LayoutTests(unittest.TestCase):
    def test_runtime_files_are_separate_from_source_and_dictionary(self):
        for name in ("位置记录文件", "翻译记录文件", "翻译缓存文件", "语音缓存目录", "预渲染日志文件"):
            self.assertTrue(getattr(paths, name).is_relative_to(paths.RUNTIME_DIR), name)
        self.assertEqual(paths.配置路径.parent, paths.ROOT / "config")
        self.assertEqual(paths.数据库路径.parent, paths.ROOT / "data")

    def test_first_run_creates_nested_config_with_default_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "config" / "配置.ini"
            self.assertTrue(初始化配置(target))
            self.assertEqual(list(读取配置(target)["按键映射"].values()), ["f8", "f9", "f10"])

    def test_entry_help_works_from_another_directory_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-B", str(paths.ROOT / "启动.py"), "--help"],
                cwd=directory, capture_output=True, encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("预渲染", result.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_actual_module_import_does_not_open_devices_or_register_keys(self):
        try:
            import keyboard
            import pygame
        except ImportError:
            self.skipTest("安装 requirements.txt 后检查完整模块连接")
        with patch.object(pygame.mixer, "init") as mixer, patch.object(keyboard, "on_press_key") as hook:
            import xiaoxiao_reader.app as app
            import xiaoxiao_reader.prerender as prerender
            from xiaoxiao_reader import runtime, speech, translation, storage, ui
            self.assertIs(app.翻译队列, runtime.翻译队列)
            self.assertIs(ui.OCR请求队列, runtime.OCR请求队列)
            self.assertIs(prerender.翻译缓存, storage.翻译缓存)
            self.assertIs(translation.翻译缓存, storage.翻译缓存)
            self.assertIs(speech.runtime, runtime)
            mixer.assert_not_called()
            hook.assert_not_called()


if __name__ == "__main__":
    unittest.main()
