"""官方 statusLine 用量、每輪一次提醒、壓縮失效與安裝設定的回歸測試。"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_status
import hook_state
import install_hooks
import session_start
import wrapup_nudge


class WrapupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patch = mock.patch.dict(os.environ, {"AI_OFFICE_STATE": str(self.root / "state"),
                                             "PYTHONDONTWRITEBYTECODE": "1"})
        patch.start()
        self.addCleanup(patch.stop)
        self.event = {"hook_event_name": "UserPromptSubmit", "session_id": "one", "cwd": str(self.root)}

    def status(self, percent, session="one", usage=None, now=None):
        return context_status.record({"session_id": session, "context_window": {
            "used_percentage": percent, "current_usage": {} if usage is None else usage}}, now)

    def test_threshold_and_same_session_only_once(self):
        self.status(69.99)
        self.assertIsNone(wrapup_nudge.evaluate(self.event))
        self.status(70)
        text = wrapup_nudge.evaluate(self.event)
        self.assertIn("70%", text)
        self.assertIn("handoff-docs", text)
        self.assertIn("project-docs", text)
        self.assertIn("可接手", text)
        self.assertIsNone(wrapup_nudge.evaluate(self.event))
        self.assertIsNone(wrapup_nudge.evaluate(dict(self.event, session_id="two")))
        self.status(80, "two")
        self.assertIsNotNone(wrapup_nudge.evaluate(dict(self.event, session_id="two")))

    def test_both_loaded_suppress_and_one_missing_is_named(self):
        self.status(90)
        hook_state.mark_skill("one", "handoff-docs")
        hook_state.mark_skill("one", "project-docs")
        self.assertIsNone(wrapup_nudge.evaluate(self.event))
        hook_state.clear_skill_marks("one")
        hook_state.mark_skill("one", "handoff-docs")
        text = wrapup_nudge.evaluate(self.event)
        self.assertIn("project-docs", text)
        self.assertNotIn("handoff-docs", text)

    def test_missing_unknown_and_invalid_metrics_never_become_zero(self):
        self.assertIsNone(wrapup_nudge.evaluate(self.event))
        for percent in [None, "90", True, -1, 101, float("nan"), float("inf")]:
            with self.subTest(percent=percent):
                self.assertIsNone(self.status(percent))
                self.assertIsNone(wrapup_nudge.evaluate(self.event))
        context_status.record({"session_id": "one", "context_window": {
            "used_percentage": 90, "current_usage": None}})
        self.assertIsNone(wrapup_nudge.evaluate(self.event))
        self.assertIsNone(context_status.record({"context_window": {"used_percentage": 90}}))
        self.assertIsNone(wrapup_nudge.evaluate(dict(self.event, session_id="")))

    def test_reset_waits_for_new_metrics_and_does_not_repeat_nudge(self):
        self.status(90)
        hook_state.reset_context("one")
        self.assertIsNone(wrapup_nudge.evaluate(self.event))
        self.status(75)
        self.assertIsNotNone(wrapup_nudge.evaluate(self.event))
        hook_state.reset_context("one")
        self.status(85)
        self.assertIsNone(wrapup_nudge.evaluate(self.event))

    def test_session_start_invalidates_pre_compact_usage(self):
        self.status(95)
        payload = dict(self.event, hook_event_name="SessionStart", source="compact")
        result = subprocess.run([sys.executable, str(Path(session_start.__file__)),
                                 "--tools-dir", str(self.root / "no-tools")],
                                input=json.dumps(payload), capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(wrapup_nudge.evaluate(self.event))
        self.status(20)
        self.assertIsNone(wrapup_nudge.evaluate(self.event))

    def test_corrupt_and_other_source_or_events_are_ignored(self):
        path = hook_state.state_path("one", "context-usage")
        hook_state.write_state(path, {"source": "guessed-transcript", "percent": 95, "measured_at": time.time()})
        self.assertIsNone(wrapup_nudge.evaluate(self.event))
        path.write_text("invalid", encoding="utf-8")
        self.assertIsNone(wrapup_nudge.evaluate(self.event))
        self.status(95)
        self.assertIsNone(wrapup_nudge.evaluate(dict(self.event, hook_event_name="SessionStart")))

    def test_cli_emits_official_additional_context_and_ascii_json(self):
        self.status(72.5)
        result = subprocess.run([sys.executable, str(Path(wrapup_nudge.__file__))],
                                input=json.dumps(self.event), capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.isascii())
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "UserPromptSubmit")
        self.assertIn("72.5%", output["additionalContext"])

    def test_status_command_records_and_forwards_original_json(self):
        original_script = self.root / "old.py"
        original_script.write_text("import json, sys\nprint('original:' + json.load(sys.stdin)['session_id'])\n", encoding="utf-8")
        original = self.root / "original.json"
        original.write_text(json.dumps({"type": "command",
                                       "command": f'"{sys.executable}" "{original_script}"'}), encoding="utf-8")
        payload = {"session_id": "one", "context_window": {"used_percentage": 80, "current_usage": {}}}
        result = subprocess.run([sys.executable, str(Path(context_status.__file__)), "--forward", str(original)],
                                input=json.dumps(payload), capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "original:one\n")
        self.assertIsNotNone(wrapup_nudge.evaluate(self.event))

    def test_installer_opt_in_preserves_original_and_is_idempotent(self):
        target = self.root / "config"
        target.mkdir()
        old = {"type": "command", "command": "echo original", "padding": 2}
        (target / "settings.json").write_text(json.dumps({"statusLine": old}), encoding="utf-8")
        args = ["--claude-dir", str(target), "--with-context-status"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_hooks.main(args + ["--dry-run"]), 0)
            self.assertFalse((target / "hooks").exists())
            self.assertEqual(install_hooks.main(args), 0)
            before = (target / "settings.json").read_bytes()
            self.assertEqual(install_hooks.main(args), 0)
        self.assertEqual((target / "settings.json").read_bytes(), before)
        config = json.loads(before)
        self.assertIn("UserPromptSubmit", config["hooks"])
        self.assertIn("context_status.py", config["statusLine"]["command"])
        self.assertIn("--forward", config["statusLine"]["command"])
        self.assertEqual(config["statusLine"]["padding"], 2)
        self.assertEqual(json.loads((target / "hooks/statusline-original.json").read_text()), old)
        self.assertTrue(list(target.glob("settings.json.bak-*")))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_hooks.main(args + ["--python", "py -3"]), 0)
        changed = json.loads((target / "settings.json").read_text())
        self.assertTrue(changed["statusLine"]["command"].startswith("py -3 "))
        self.assertEqual(json.loads((target / "hooks/statusline-original.json").read_text()), old)

    def test_installer_without_metric_opt_in_and_invalid_original(self):
        target = self.root / "config"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_hooks.main(["--claude-dir", str(target)]), 0)
        self.assertNotIn("statusLine", json.loads((target / "settings.json").read_text()))
        invalid = self.root / "invalid"
        invalid.mkdir()
        original = json.dumps({"statusLine": "bad"})
        (invalid / "settings.json").write_text(original)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(install_hooks.main(["--claude-dir", str(invalid), "--with-context-status"]), 2)
        self.assertFalse((invalid / "hooks").exists())
        self.assertEqual((invalid / "settings.json").read_text(), original)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
            install_hooks.main(["--platform", "codex", "--codex-dir", str(self.root / "codex"),
                                "--with-context-status"])
        self.assertEqual(exc.exception.code, 2)
        self.assertFalse((self.root / "codex").exists())

    def test_windows_forward_uses_git_bash_or_powershell(self):
        # 替換模組的 os，避免修改 pathlib 在 Linux 的平台判斷。
        with mock.patch.object(context_status, "os", mock.Mock(name="nt", environ={})):
            context_status.os.name = "nt"
            with mock.patch.object(context_status.shutil, "which", side_effect=lambda name: "C:/Git/bin/bash.exe" if name == "bash" else None), \
                    mock.patch.object(Path, "is_file", return_value=True):
                self.assertEqual(context_status.forward_argv("echo original"),
                                 ["C:/Git/bin/bash.exe", "-c", "echo original"])
            with mock.patch.object(context_status.shutil, "which", side_effect=lambda name: "powershell.exe" if name == "powershell" else None):
                self.assertEqual(context_status.forward_argv("Write-Output original"),
                                 ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Write-Output original"])
            with mock.patch.object(context_status.shutil, "which", return_value=None), self.assertRaises(OSError):
                context_status.forward_argv("echo original")


if __name__ == "__main__":
    unittest.main()
