"""block_dangerous.py 的單元測試。執行：python -m unittest hooks/test_block_dangerous.py"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import block_dangerous  # noqa: E402


def verdict(command, tool="Bash"):
    return block_dangerous.evaluate({"tool_name": tool, "tool_input": {"command": command}})


class ShouldBlock(unittest.TestCase):
    CASES = [
        ("rm -rf node_modules", "Bash"),
        ("rm -fr ./build", "Bash"),
        ("rm -r -f 專案資料夾", "Bash"),
        ("rm --recursive --force data", "Bash"),
        ("Remove-Item -Recurse -Force C:\\Users\\me\\AI工作區\\projects", "PowerShell"),
        ("Remove-Item C:\\temp\\x -Recurse", "PowerShell"),
        ("ri .\\old -r -fo", "PowerShell"),
        ("Get-ChildItem *.tmp | Remove-Item -Recurse", "PowerShell"),
        ("del /s /q C:\\data\\*", "Bash"),
        ("rd /s /q C:\\data", "Bash"),
        ("cmd /c rmdir /s /q D:\\backup", "PowerShell"),
        ("format D: /fs:NTFS", "PowerShell"),
        ("Format-Volume -DriveLetter E -FileSystem NTFS", "PowerShell"),
        ("diskpart", "PowerShell"),
        ("git push --force origin main", "Bash"),
        ("git push -f", "Bash"),
        ("git push origin +main", "Bash"),
        ("git push --force-with-lease origin main", "Bash"),
        ("git reset --hard HEAD~1", "Bash"),
        ("git -C C:\\repo reset --hard origin/main", "PowerShell"),
        ("echo {} > C:\\Users\\me\\.claude\\settings.json", "PowerShell"),
        ("Set-Content -Path $env:USERPROFILE\\.claude\\settings.json -Value '{}'", "PowerShell"),
        ("sed -i 's/a/b/' ~/.claude/settings.json", "Bash"),
        ("Copy-Item new.json C:\\Users\\me\\.claude\\settings.json", "PowerShell"),
        ("Set-Content C:\\Users\\me\\.claude\\hooks\\block_dangerous.py 'pass'", "PowerShell"),
        ("echo x | Out-File ~/.claude/hooks/session_start.py", "PowerShell"),
        ("Remove-Item C:\\Users\\me\\.claude\\hooks\\block_dangerous.py", "PowerShell"),
    ]

    def test_blocked(self):
        for command, tool in self.CASES:
            with self.subTest(command=command):
                result = verdict(command, tool)
                self.assertIsNotNone(result, f"應被攔截：{command}")
                self.assertEqual(result[0], "deny")
                self.assertTrue(result[1])

    def test_delete_message_mentions_recycle_bin(self):
        self.assertIn("資源回收筒", verdict("rm -rf x")[1])


class ShouldAllow(unittest.TestCase):
    CASES = [
        ("ls -la", "Bash"),
        ("Get-ChildItem -Recurse -Filter *.md", "PowerShell"),
        ("Remove-Item C:\\temp\\one.txt", "PowerShell"),
        ("rm notes.txt", "Bash"),
        ("del report.docx", "PowerShell"),
        ("git push origin main", "Bash"),
        ("git push --follow-tags", "Bash"),
        ("git push -u origin feature", "Bash"),
        ("git reset --soft HEAD~1", "Bash"),
        ("git reset HEAD file.txt", "Bash"),
        ("git rm -r --cached build", "Bash"),
        ("git status && git commit -m 'force a review'", "Bash"),
        ("Get-ChildItem -Force", "PowerShell"),
        ("Remove-Item -Force old.log", "PowerShell"),
        ("cat ~/.claude/settings.json", "Bash"),
        ("Get-Content $env:USERPROFILE\\.claude\\settings.json", "PowerShell"),
        ("Copy-Item C:\\Users\\me\\.claude\\settings.json C:\\backup\\settings.json.bak", "PowerShell"),
        ("python -m unittest hooks/test_block_dangerous.py", "Bash"),
        ("echo format the report", "Bash"),
        ("python hooks/session_start.py", "Bash"),
    ]

    def test_allowed(self):
        for command, tool in self.CASES:
            with self.subTest(command=command):
                self.assertIsNone(verdict(command, tool), f"不應攔截：{command}")

    def test_other_tools_ignored(self):
        self.assertIsNone(block_dangerous.evaluate({"tool_name": "Read", "tool_input": {"file_path": "x"}}))
        self.assertIsNone(block_dangerous.evaluate({"tool_name": "Write", "tool_input": {"file_path": "C:\\a\\notes.md"}}))

    def test_missing_input(self):
        self.assertIsNone(block_dangerous.evaluate({}))
        self.assertIsNone(block_dangerous.evaluate({"tool_name": "Bash", "tool_input": None}))


class SelfProtectionTools(unittest.TestCase):
    def test_edit_settings_asks(self):
        for path in ("C:\\Users\\me\\.claude\\settings.json", "/Users/u/.claude/hooks/block_dangerous.py"):
            with self.subTest(path=path):
                result = block_dangerous.evaluate({"tool_name": "Edit", "tool_input": {"file_path": path}})
                self.assertEqual(result[0], "ask")

    def test_write_other_claude_files_allowed(self):
        result = block_dangerous.evaluate(
            {"tool_name": "Write", "tool_input": {"file_path": "C:\\Users\\me\\.claude\\CLAUDE.md"}})
        self.assertIsNone(result)


class CommandLineInterface(unittest.TestCase):
    def run_hook(self, payload):
        return subprocess.run([sys.executable, os.path.join(HERE, "block_dangerous.py")],
                              input=json.dumps(payload).encode("utf-8"), capture_output=True)

    def test_deny_output_format(self):
        done = self.run_hook({"tool_name": "Bash", "tool_input": {"command": "rm -rf /tmp/x"}})
        self.assertEqual(done.returncode, 0)
        out = json.loads(done.stdout.decode("utf-8"))["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("資源回收筒", out["permissionDecisionReason"])

    def test_allow_prints_nothing(self):
        done = self.run_hook({"tool_name": "Bash", "tool_input": {"command": "echo hi"}})
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, b"")


class ForegroundWait(unittest.TestCase):
    def test_short_task_commands_wait_and_data(self):
        for command in ("python dispatch.py 合約欄位整理 --wait",
                        'py -3 "C:/AI tools/dispatch.py" 合約欄位整理 --wait',
                        "python dispatch.py 任務 --help && python dispatch.py 任務 --wait"):
            with self.subTest(command=command):
                self.assertEqual(verdict(command)[0], "deny")
        for command in ("python dispatch.py 合約欄位整理", "python dispatch.py 合約欄位整理 --status",
                        "python dispatch.py --list", "echo 'python dispatch.py 任務 --wait'",
                        "cat > brief.md <<'END'\npython dispatch.py 任務 --wait\nEND"):
            with self.subTest(command=command):
                self.assertIsNone(verdict(command))
        self.assertIsNone(block_dangerous.evaluate({"tool_name": "Bash", "tool_input": {
            "command": "python dispatch.py 合約欄位整理 --wait", "run_in_background": True}}))

    def test_codex_protected_patch_denies_and_read_allows(self):
        patch = {"tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch\n*** Update File: .codex/hooks.json\n+x\n*** End Patch"}}
        self.assertEqual(block_dangerous.evaluate(patch, "codex")[0], "deny")
        self.assertIsNone(block_dangerous.evaluate({"tool_name": "Bash", "tool_input": {"command": "cat .codex/hooks.json"}}, "codex"))
        self.assertEqual(block_dangerous.evaluate({"tool_name": "Write", "tool_input": {"file_path": ".codex/config.toml"}}, "codex")[0], "deny")

    def test_block_waits(self):
        cases = [
            ("python tools/codex-run.py wait inbox/codex/task", "Bash"),
            ('py -3 "C:\\AI tools\\codex-run.py" wait "C:\\AI\\out"', "PowerShell"),
            ("python tools/codex-queue.py --brief task.md --out result", "Bash"),
            ("while true; do sleep 10; done", "Bash"),
            ("while ($true) { Start-Sleep -Seconds 10 }", "PowerShell"),
            ("python tools/codex-run.py wait --help && python tools/codex-run.py wait out", "Bash"),
        ]
        for command, tool in cases:
            with self.subTest(command=command):
                self.assertEqual(verdict(command, tool)[0], "deny")

    def test_allow_data_status_and_background(self):
        cases = [
            "python tools/codex-run.py status out",
            "python tools/codex-run.py submit --brief task.md --out result",
            "echo 'python tools/codex-run.py wait out'",
            "cat > note.txt <<'EOF'\npython tools/codex-run.py wait out\nEOF",
            'Write-Output "while ($true) { Start-Sleep 10 }"',
            "python tools/codex-run.py wait --help",
        ]
        for command in cases:
            with self.subTest(command=command):
                self.assertIsNone(verdict(command))
        self.assertIsNone(block_dangerous.evaluate({"tool_name": "Bash", "tool_input": {
            "command": "python tools/codex-run.py wait out", "run_in_background": True}}))

    def test_invalid_input_does_not_crash(self):
        done = subprocess.run([sys.executable, os.path.join(HERE, "block_dangerous.py")],
                              input=b"not json", capture_output=True)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, b"")


if __name__ == "__main__":
    unittest.main()
