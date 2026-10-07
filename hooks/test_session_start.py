"""開場 hook 的交接、摘要、重複抑制及無事項輸出測試。"""
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session_start as session
import install_hooks


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = mock.patch.dict(os.environ, {"AI_OFFICE_STATE": str(self.root / "state"), "AI_OFFICE_JOBS": str(self.root / "inbox/codex")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_find_handoff_above_current_folder(self):
        handoff = self.root / "docs/HANDOFF.md"
        handoff.parent.mkdir()
        handoff.write_text("# 狀態\n- [ ] 待辦", encoding="utf-8")
        self.assertEqual(session.find_handoff(self.root / "src" / "child"), handoff)
        self.assertIn("待辦", session.build_context(handoff))

    def test_no_files_no_output(self):
        result = subprocess.run([sys.executable, str(HERE / "session_start.py")], input=json.dumps({"cwd": str(self.root)}).encode(), capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_status_and_audit_summary_once_per_session(self):
        job = self.root / "inbox/codex/task"
        job.mkdir(parents=True)
        (job / "job.json").write_text(json.dumps({"pid": -1, "status": "running"}), encoding="utf-8")
        (self.root / "README.md").write_text("[broken](missing.md)", encoding="utf-8")
        tools = HERE.parent / "tools"
        first = session.management_context(self.root, tools, "same-session")
        self.assertIn("interrupted", first)
        self.assertIn("文件落差", first)
        self.assertEqual(session.management_context(self.root, tools, "same-session"), "")
        self.assertTrue(session.management_context(self.root, tools, "new-session"))

    def test_adopted_tools_missing_or_timeout_is_quiet(self):
        self.assertEqual(session.management_context(self.root, self.root / "missing"), "")
        with mock.patch.object(session.subprocess, "run", side_effect=subprocess.TimeoutExpired("python", 8)):
            self.assertEqual(session.management_context(self.root, HERE.parent / "tools"), "")

    def test_installer_upgrades_session_command_instead_of_duplication(self):
        old = 'python "C:/AI/.claude/hooks/session_start.py"'
        settings = {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": old}]}]}}
        self.assertTrue(install_hooks.add_hook(settings, "SessionStart", "startup", old + ' --tools-dir "C:/AI/kit/tools"'))
        self.assertEqual(len(settings["hooks"]["SessionStart"]), 1)
        self.assertFalse(install_hooks.add_hook(settings, "SessionStart", "startup", old + ' --tools-dir "C:/AI/kit/tools"'))

    def test_installer_dry_run_does_not_write(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_hooks.main(["--claude-dir", str(self.root / "config"), "--dry-run"]), 0)
        self.assertFalse((self.root / "config").exists())


if __name__ == "__main__":
    unittest.main()
