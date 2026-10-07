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

    def test_no_list_notice_once_and_existing_handoff(self):
        handoff = self.root / "docs/HANDOFF.md"
        handoff.parent.mkdir()
        handoff.write_text("# 現況\n- [ ] 核對", encoding="utf-8")
        command = [sys.executable, str(HERE / "session_start.py"), "--tools-dir", str(self.root / "none")]
        payload = json.dumps({"cwd": str(self.root), "session_id": "notice-session"}).encode()
        result = subprocess.run(command, input=payload, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0)
        first = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("核對", first)
        self.assertIn("尚無 docs/session-start.json", first)
        result = subprocess.run(command, input=payload, capture_output=True, timeout=20)
        second = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("核對", second)
        self.assertNotIn("尚無 docs/session-start.json", second)

    def save_list(self, items, limit=24000):
        target = self.root / session.LIST_FILE
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps({"version": 1, "max_chars": limit, "items": items}), encoding="utf-8")
        return target

    def test_list_full_section_and_path_keep_original_text(self):
        body = "# 文件\n## 定案\n逐條第一款。\n### 細節\n逐條第二款。\n## 歷史\n不載入歷史。\n"
        (self.root / "rules.md").write_text(body, encoding="utf-8")
        (self.root / "full.md").write_text("完整原文\n", encoding="utf-8")
        self.save_list([{"path": "full.md", "reason": "共用規則", "mode": "full"},
                        {"path": "rules.md", "reason": "定案每輪重讀", "mode": "section", "section": "定案"},
                        {"path": "full.md", "reason": "提醒", "mode": "path"}])
        context, errors, _, _ = session.list_context(self.root)
        self.assertFalse(errors)
        self.assertIn("完整原文\n", context)
        self.assertIn("## 定案\n逐條第一款。\n### 細節\n逐條第二款。\n", context)
        self.assertNotIn("不載入歷史", context)
        self.assertIn("請先讀取原檔", context)
        self.assertEqual(session.project_root(self.root / "src"), self.root)

    def test_list_missing_file_marks_reason_and_check_exit(self):
        self.save_list([{"path": "missing.md", "reason": "定案規格", "mode": "full"}])
        context, errors, _, _ = session.list_context(self.root)
        self.assertIn("[缺檔] missing.md — 定案規格", context)
        self.assertEqual(len(errors), 1)
        command = [sys.executable, str(HERE / "session_start.py"), "--cwd", str(self.root), "--tools-dir", str(self.root / "none")]
        result = subprocess.run(command + ["--check"], capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertIn("缺檔", json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])
        result = subprocess.run(command, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0)

    def test_over_limit_lists_path_without_partial_clause(self):
        (self.root / "big.md").write_text("條文原文" * 1000, encoding="utf-8")
        (self.root / "small.md").write_text("小檔原文", encoding="utf-8")
        self.save_list([{"path": "big.md", "reason": "全文", "mode": "full"},
                        {"path": "small.md", "reason": "全文", "mode": "full"}], 2048)
        context, errors, _, limit = session.list_context(self.root)
        self.assertFalse(errors)
        self.assertLessEqual(len(context), limit)
        self.assertIn("big.md", context)
        self.assertIn("[超過長度上限]", context)
        self.assertNotIn("條文原文", context)
        self.assertIn("小檔原文", context)

    def test_bad_schema_and_duplicate_or_missing_section(self):
        for title, body in [("沒有", "## 別節\n內容"), ("同名", "## 同名\n一\n## 同名\n二")]:
            with self.subTest(title=title):
                (self.root / "a.md").write_text(body, encoding="utf-8")
                self.save_list([{"path": "a.md", "reason": "定案", "mode": "section", "section": title}])
                context, errors, _, _ = session.list_context(self.root)
                self.assertTrue(errors)
                self.assertIn("章節", context)
        self.save_list([{"path": "../outside.md", "reason": "錯誤", "mode": "full"}])
        self.assertIn("相對路徑", session.list_context(self.root)[0])

    def test_fenced_heading_is_not_a_section_boundary(self):
        text = "## 定案\n原文\n~~~\n## 假標題\n~~~\n下一款\n## 結尾\n"
        self.assertEqual(session.section_text(text, "定案"), text[:text.index("## 結尾")])

    def test_registry_compact_lists_filename_and_purpose(self):
        target = self.root / "scripts/REGISTRY.md"
        target.parent.mkdir()
        target.write_text("| [tool.py](tool.py) | 一句用途。 | 用法 |\n", encoding="utf-8")
        context = session.registry_context(self.root, self.root / "none")
        self.assertIn("tool.py — 一句用途。", context)
        self.assertNotIn("| 用法 |", context)

    def test_startup_resume_clear_compact_always_reload_required_text(self):
        (self.root / "rule.md").write_text("每輪逐條定案", encoding="utf-8")
        self.save_list([{"path": "rule.md", "reason": "定案不可遺失", "mode": "full"}])
        command = [sys.executable, str(HERE / "session_start.py"), "--tools-dir", str(self.root / "none")]
        for source in ("startup", "resume", "clear", "compact"):
            with self.subTest(source=source):
                payload = json.dumps({"cwd": str(self.root), "session_id": "four-sources", "source": source}).encode()
                result = subprocess.run(command, input=payload, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0)
                context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
                self.assertIn("每輪逐條定案", context)

    def test_total_limit_includes_registry_and_full_skill_marks(self):
        skill = self.root / "skills/handoff-docs/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: handoff-docs\n---\n寫法原文", encoding="utf-8")
        self.save_list([{"path": "skills/handoff-docs/SKILL.md", "reason": "寫法", "mode": "full"}], 2048)
        command = [sys.executable, str(HERE / "session_start.py")]
        payload = json.dumps({"cwd": str(self.root), "session_id": "loaded-list"}).encode()
        result = subprocess.run(command, input=payload, capture_output=True, timeout=20)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertLessEqual(len(context), 2048)
        self.assertIn("寫法原文", context)
        from hook_state import loaded_skills
        self.assertIn("handoff-docs", loaded_skills("loaded-list"))

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

    def test_installer_codex_trust_context_limit_and_idempotency(self):
        target = self.root / "codex-config"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_hooks.main(["--platform", "codex", "--codex-dir", str(target)]), 0)
            before = (target / "hooks.json").read_bytes()
            self.assertEqual(install_hooks.main(["--platform", "codex", "--codex-dir", str(target)]), 0)
        self.assertEqual((target / "hooks.json").read_bytes(), before)
        config = json.loads(before)
        start = config["hooks"]["SessionStart"][0]
        self.assertIn("compact", start["matcher"])
        self.assertEqual(start["hooks"][0]["additionalContextLimit"], 0)
        self.assertIn("PostToolUse", config["hooks"])
        self.assertTrue((target / "hooks/hook_state.py").is_file())
        self.assertTrue((target / "hooks/skill_gate.py").is_file())


if __name__ == "__main__":
    unittest.main()
