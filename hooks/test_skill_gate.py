"""寫法 skill gate：兩端事件、成功載入、壓縮失效及常見不該擋的操作。"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_gate as gate
import hook_state


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patch = mock.patch.dict(os.environ, {"AI_OFFICE_STATE": self.temp.name})
        patch.start()
        self.addCleanup(patch.stop)

    def event(self, tool, inp, event="PreToolUse", response=None, session="one"):
        return {"session_id": session, "hook_event_name": event, "tool_name": tool,
                "tool_input": inp, "tool_response": response}

    def load(self, name, session="one"):
        self.assertIsNone(gate.evaluate(self.event("Skill", {"skill": "office-work-kit:" + name},
                                           "PostToolUse", {"success": True}, session)))

    def test_rules_block_then_successful_skill_allows_retry(self):
        data = self.event("Write", {"file_path": r"C:\work\AGENTS.md"})
        self.assertIn("handoff-docs", gate.evaluate(data))
        self.load("handoff-docs")
        self.assertIsNone(gate.evaluate(data))
        self.assertIsNotNone(gate.evaluate(dict(data, session_id="another")))

    def test_project_handoff_needs_both_and_codex_apply_patch(self):
        data = self.event("apply_patch", {"command": "*** Begin Patch\n*** Update File: docs/HANDOFF.md\n+x\n*** End Patch"})
        self.assertEqual(gate.required(data), set(gate.SKILLS))
        self.load("handoff-docs")
        self.assertIn("project-docs", gate.evaluate(data))
        self.load("project-docs")
        self.assertIsNone(gate.evaluate(data))

    def test_dispatch_needs_only_handoff_docs(self):
        data = self.event("Bash", {"command": "python dispatch.py 合約欄位整理"})
        self.assertEqual(gate.required(data), {"handoff-docs"})
        self.assertIsNotNone(gate.evaluate(data))
        self.load("handoff-docs")
        self.assertIsNone(gate.evaluate(data))
        self.assertEqual(gate.required(self.event("spawn_agent", {})), {"handoff-docs"})

    def test_read_and_codex_cat_success_record_loading(self):
        self.assertIsNone(gate.evaluate(self.event("Read", {"file_path": "skills/handoff-docs/SKILL.md"},
                                                  "PostToolUse", {"file": {"content": "name: handoff-docs"}})))
        self.assertIn("handoff-docs", hook_state.loaded_skills("one"))
        event = self.event("Bash", {"command": "cat skills/project-docs/SKILL.md"},
                          "PostToolUse", "Process exited with code 0\n---\nname: project-docs\n---\n內容")
        gate.evaluate(event)
        self.assertEqual(hook_state.loaded_skills("one"), set(gate.SKILLS))

    def test_failed_partial_and_echo_reads_do_not_record(self):
        events = [
            self.event("Skill", {"skill": "handoff-docs"}, "PostToolUse", {"is_error": True}),
            self.event("Skill", {"skill": "handoff-docs"}, "PostToolUse", {"success": False}),
            self.event("Read", {"file_path": "skills/handoff-docs/SKILL.md", "limit": 10}, "PostToolUse", "內容"),
            self.event("Read", {"file_path": "skills/handoff-docs/SKILL.md"}, "PostToolUse", {"file": {"numLines": 10, "totalLines": 100}}),
            self.event("Bash", {"command": "cat skills/handoff-docs/SKILL.md"}, "PostToolUse", {"exit_code": 1, "stdout": "name: handoff-docs"}),
            self.event("Bash", {"command": "echo 'name: handoff-docs' skills/handoff-docs/SKILL.md"}, "PostToolUse", "name: handoff-docs"),
            self.event("Bash", {"command": "cat skills/handoff-docs/SKILL.md | head"}, "PostToolUse", "name: handoff-docs"),
            self.event("Bash", {"command": "cat skills/handoff-docs/SKILL.md"}, "PostToolUse", "name: handoff-docs\nWarning: output truncated"),
        ]
        for event in events:
            with self.subTest(event=event):
                self.assertEqual(gate.observed_skill(event), set())
        self.assertFalse(hook_state.loaded_skills("one"))

    def test_compact_reset_requires_reload(self):
        self.load("handoff-docs")
        hook_state.clear_skill_marks("one")
        hook_state.reset_skills("one")
        self.assertNotIn("handoff-docs", hook_state.loaded_skills("one"))

    def test_ordinary_docs_and_status_are_allowed(self):
        for tool, inp in [("Write", {"file_path": "notes.md"}), ("Edit", {"file_path": "app.py"}),
                          ("Bash", {"command": "python dispatch.py 合約欄位整理 --status"}),
                          ("Bash", {"command": "python dispatch.py --list"}),
                          ("Bash", {"command": "python dispatch.py --help"}),
                          ("Bash", {"command": "echo 'python dispatch.py 任務'"}),
                          ("Bash", {"command": "cat > brief.md <<'END'\npython dispatch.py 任務\nEND"}),
                          ("Read", {"file_path": "docs/HANDOFF.md"})]:
            with self.subTest(tool=tool, inp=inp):
                self.assertIsNone(gate.evaluate(self.event(tool, inp)))

    def test_shell_project_docs_require_two_skills(self):
        self.assertEqual(gate.required(self.event("PowerShell", {"command": "Set-Content docs/HANDOFF.md '新內容'"})), set(gate.SKILLS))
        data = self.event("Bash", {"command": "python dispatch.py --help && python dispatch.py 任務"})
        self.assertEqual(gate.required(data), {"handoff-docs"})

    def test_background_dispatch_and_wait_reject_bad_labels(self):
        self.load("handoff-docs")
        cases = [
            ("Bash", "python dispatch.py 合約欄位整理", None),
            ("Bash", "python dispatch.py 合約欄位整理 --wait", "合約欄位整理"),
            ("PowerShell", 'python "C:/AI/dispatch.py" 合約欄位整理', "合約欄位整理(gpt-6.1-sol/high)"),
            ("Bash", "python codex-run.py wait --out inbox/test", "合約欄位整理（・high）"),
            ("Bash", "python codex-queue.py --brief brief.md", " （gpt-6.1-sol・high）"),
            ("Bash", "python dispatch.py 任務", "python dispatch.py 任務（gpt-6.1-sol・high）"),
            ("Bash", "python dispatch.py 任務", "C:/work/任務（gpt-6.1-sol・high）"),
            ("Bash", "python dispatch.py 任務", "任務（gpt-6.1-sol・high）\n其他文字"),
        ]
        for tool, command, label in cases:
            with self.subTest(tool=tool, label=label):
                data = self.event(tool, {"command": command, "run_in_background": True, "description": label})
                self.assertIn("任務名（模型・強度）", gate.evaluate(data))

    def test_background_dispatch_and_wait_allow_correct_labels(self):
        self.load("handoff-docs")
        cases = [
            ("Bash", "python dispatch.py 合約欄位整理", "合約欄位整理（gpt-6.1-sol・high）"),
            ("Bash", "python dispatch.py 合約欄位整理 --wait", "合約欄位整理（gpt-6.1-sol・high）"),
            ("PowerShell", 'python "C:/AI/dispatch.py" 文件比對 --wait', "文件比對（gpt-6-astra・medium）"),
            ("Bash", "python codex-run.py wait --out inbox/test", "文件核對（gpt-6.1-sol・xhigh）"),
        ]
        for tool, command, label in cases:
            with self.subTest(tool=tool, label=label):
                self.assertIsNone(gate.evaluate(self.event(tool, {
                    "command": command, "run_in_background": True, "description": label})))

    def test_label_guard_ignores_examples_queries_and_codex_without_field(self):
        self.load("handoff-docs")
        for command in ["python dispatch.py 任務 --status", "python dispatch.py --list",
                        "python dispatch.py --help", "echo 'python dispatch.py 任務'",
                        "cat <<'END'\npython dispatch.py 任務 --wait\nEND", "python ordinary.py"]:
            with self.subTest(command=command):
                self.assertIsNone(gate.evaluate(self.event("Bash", {
                    "command": command, "run_in_background": True})))
        self.assertIsNone(gate.evaluate(self.event("Bash", {"command": "python dispatch.py 任務"})))
        self.assertIn("description", gate.evaluate(self.event("Bash", {
            "command": "python dispatch.py --help && python dispatch.py 任務", "run_in_background": True})))
        self.assertIsNone(gate.evaluate(self.event("Bash", {
            "command": "python dispatch.py 任務", "run_in_background": True},
            "PostToolUse", {"exit_code": 0})))


if __name__ == "__main__":
    unittest.main()
