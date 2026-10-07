"""任務資料夾派工：設定驗證、中文入口、結果落檔與保留既有紀錄。"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dispatch


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task = self.root / "tasks/合約欄位整理"
        self.task.mkdir(parents=True)
        (self.task / "brief.md").write_text("請依原文整理中文欄位", encoding="utf-8")
        self.save({"version": 1, "effort": "high", "sandbox": "read-only"})

    def save(self, config):
        (self.task / "task.json").write_text(json.dumps(config), encoding="utf-8")

    def test_relative_paths_and_chinese_task_name(self):
        _, config, cwd, out, brief = dispatch.load_task(self.root, "合約欄位整理")
        self.assertEqual(cwd, self.root)
        self.assertEqual(out, self.root / "inbox/codex/合約欄位整理")
        self.assertEqual(config["effort"], "high")
        self.assertEqual(brief, self.task / "brief.md")

    def test_reject_bad_names_and_invalid_settings_before_starting(self):
        for name in ("../任務", r"a\b", "CON", "NUL.txt", "任務.", "任務 ", "a:b"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    dispatch.task_name(name)
        for fields in ({"model": 6}, {"effort": "super"}, {"search": "yes"},
                       {"sandbox": "danger"}, {"timeout": -1}, {"max_wait": float("nan")},
                       {"unknown": True}, {"min_free": "junk"}):
            with self.subTest(fields=fields):
                self.save(dict(version=1, **fields))
                with self.assertRaises(ValueError):
                    dispatch.load_task(self.root, "合約欄位整理")

    def test_settings_reach_engine_without_shell_parsing(self):
        self.save({"version": 1, "model": "example-model", "effort": "high",
                   "sandbox": "read-only", "search": True, "codex_home": "accounts/工作帳號",
                   "min_free": "3G", "max_wait": 30})
        out = self.root / "inbox/codex/合約欄位整理"
        out.mkdir(parents=True)
        # 此測試直接核對送往既有引擎的參數，不啟動 CLI。
        with mock.patch.object(dispatch.Path, "exists", return_value=False), \
                mock.patch.object(dispatch.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps({"ok": True, "id": str(out), "status": "running"}), "")) as sent, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dispatch.run_task(self.root, "合約欄位整理"), 0)
        command = sent.call_args.args[0]
        self.assertEqual(command[command.index("--effort") + 1], "high")
        self.assertEqual(command[command.index("--codex-home") + 1], str(self.root / "accounts/工作帳號"))
        self.assertIn("--search", command)
        self.assertEqual(command[command.index("--min-free") + 1], "3G")
        self.assertEqual(command[command.index("--max-wait") + 1], "30")
        self.assertFalse(sent.call_args.kwargs.get("shell", False))
        self.assertTrue((out / "task-settings.json").is_file())

    def test_existing_record_is_preserved_and_status_does_not_submit(self):
        out = self.root / "inbox/codex/合約欄位整理"
        out.mkdir(parents=True)
        (out / "result.md").write_text("舊回覆", encoding="utf-8")
        with self.assertRaises(ValueError):
            dispatch.run_task(self.root, "合約欄位整理")
        with mock.patch.object(dispatch.subprocess, "call", return_value=0) as called:
            self.assertEqual(dispatch.run_task(self.root, "合約欄位整理", status=True), 0)
        self.assertIn("status", called.call_args.args[0])
        self.assertEqual((out / "result.md").read_text(encoding="utf-8"), "舊回覆")

    @unittest.skipIf(os.name == "nt", "假 shebang CLI 的端到端測試於 Linux；Windows 待實機驗證")
    def test_installed_short_command_detaches_and_saves_unicode_result(self):
        fake = self.root / "bin/codex"
        fake.parent.mkdir()
        fake.write_text("#!" + sys.executable + "\n" +
                        "import json,pathlib,sys,time\n"
                        "prompt=sys.stdin.read()\ntime.sleep(0.5)\n"
                        "pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_text('中文結果',encoding='utf-8')\n"
                        "print(json.dumps({'type':'thread.started','thread_id':'short-task'}))\n"
                        "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':2}}))\n", encoding="utf-8")
        fake.chmod(0o755)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dispatch.install(self.root), 0)
        env = dict(os.environ, PATH=str(fake.parent) + os.pathsep + os.environ["PATH"],
                   AI_OFFICE_STATE=str(self.root / "state"))
        command = [sys.executable, "dispatch.py", "合約欄位整理"]
        sent = subprocess.run(command, cwd=self.root, env=env, capture_output=True, encoding="utf-8", timeout=15)
        self.assertEqual(sent.returncode, 0, sent.stdout + sent.stderr)
        self.assertTrue(json.loads(sent.stdout)["ok"])
        done = subprocess.run(command + ["--wait"], cwd=self.root, env=env, capture_output=True, encoding="utf-8", timeout=15)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        out = self.root / "inbox/codex/合約欄位整理"
        self.assertEqual((out / "result.md").read_text(encoding="utf-8"), "中文結果")
        self.assertEqual(json.loads((out / "summary.json").read_text())["thread_id"], "short-task")
        again = subprocess.run(command, cwd=self.root, env=env, capture_output=True, encoding="utf-8", timeout=15)
        self.assertEqual(again.returncode, 1)
        self.assertEqual((out / "result.md").read_text(encoding="utf-8"), "中文結果")


if __name__ == "__main__":
    unittest.main()
