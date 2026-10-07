"""含空白的 Python 執行檔與 hook 指令引用的回歸測試。"""
import os
import base64
import contextlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_hooks


class InstallCommandTests(unittest.TestCase):
    def test_existing_duplicates_are_consolidated_and_user_groups_preserved(self):
        import context_status
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "config"
            target.mkdir()
            user = {"type": "command", "command": 'python "C:/User/hooks/skill_gate.py"', "timeout": 3}
            mixed = {"matcher": "Write", "hooks": [user], "description": "user group"}
            settings = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]}}
            events = (("SessionStart", "session_start.py"), ("PreToolUse", "block_dangerous.py"),
                      ("PreToolUse", "skill_gate.py"), ("PostToolUse", "skill_gate.py"),
                      ("UserPromptSubmit", "wrapup_nudge.py"))
            for event, script in events:
                bash = install_hooks.command_for("py -3", target, script)
                ps = install_hooks.command_for("python", target, script, shell="powershell") + "; exit $LASTEXITCODE"
                encoded = "powershell.exe -NoProfile -NonInteractive -EncodedCommand " + base64.b64encode(ps.encode("utf-16-le")).decode()
                group = {"matcher": "Write", "hooks": [{"type": "command", "command": ps, "shell": "powershell", "timeout": 8},
                                                        {"type": "command", "command": bash, "shell": "bash"},
                                                        {"type": "command", "command": encoded}]}
                if event == "PreToolUse" and script == "skill_gate.py":
                    group = dict(mixed, hooks=[user, *group["hooks"]])
                settings["hooks"].setdefault(event, []).append(group)
            file = target / "settings.json"
            file.write_text(json.dumps(settings), encoding="utf-8")
            args = ["--claude-dir", str(target), "--python", "python"]
            with mock.patch.object(install_hooks, "os", SimpleNamespace(name="nt")), \
                    mock.patch.object(context_status, "forward_argv", return_value=["bash.exe"]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install_hooks.main(args + ["--dry-run"]), 0)
                self.assertEqual(json.loads(file.read_text()), settings)
                self.assertEqual(install_hooks.main(args), 0)
                before = file.read_bytes()
                self.assertEqual(install_hooks.main(args), 0)
                self.assertEqual(file.read_bytes(), before)
            result = json.loads(before)
            self.assertEqual(result["hooks"]["Stop"], settings["hooks"]["Stop"])
            self.assertIn(mixed, result["hooks"]["PreToolUse"])
            for event, script in events:
                handlers = [h for group in result["hooks"][event] for h in group["hooks"]
                            if install_hooks.hook_script(h) == install_hooks.script_identity(target / "hooks" / script)]
                self.assertEqual(len(handlers), 1, (event, script))
                self.assertEqual(handlers[0]["shell"], "bash")
                if script != "skill_gate.py":
                    self.assertEqual(handlers[0]["timeout"], 8)

    def test_script_identity_handles_shell_forms_and_rejects_literal_mentions(self):
        target = Path("C:/Office/hooks/skill_gate.py")
        forms = [
            {"type": "command", "command": 'python "C:/Office/hooks/skill_gate.py"'},
            {"type": "command", "command": "& 'py' '-3' \"c:\\office\\hooks\\skill_gate.py\"; exit $LASTEXITCODE", "shell": "powershell"},
            {"type": "command", "command": "C:/Program Files/Python/python.exe", "args": ["C:/Office/hooks/./skill_gate.py"]}]
        for hook in forms:
            with self.subTest(hook=hook):
                self.assertEqual(install_hooks.hook_script(hook), install_hooks.script_identity(target))
        for command in ('echo "C:/Office/hooks/skill_gate.py"',
                        'python -c "C:/Office/hooks/skill_gate.py"',
                        'powershell.exe -EncodedCommand malformed!'):
            self.assertIsNone(install_hooks.hook_script({"type": "command", "command": command}))

    def check_shell_switch(self, first, second):
        import context_status
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "config folder"
            target.mkdir()
            user_hook = {"type": "command", "command": "echo user hook", "timeout": 9}
            original_status = {"type": "command", "command": "echo original", "padding": 2}
            file = target / "settings.json"
            file.write_text(json.dumps({"env": {"USER_SETTING": "keep"}, "statusLine": original_status,
                "hooks": {"PreToolUse": [{"matcher": "Write", "hooks": [user_hook]}]}}), encoding="utf-8")
            args = ["--claude-dir", str(target), "--python", "C:/Program Files/Python/python.exe", "--with-context-status"]
            for executable in (first, first, second, first, second, second):
                with mock.patch.object(install_hooks, "os", SimpleNamespace(name="nt")), \
                        mock.patch.object(context_status, "forward_argv", return_value=[executable]), \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(install_hooks.main(args), 0)
                settings = json.loads(file.read_text(encoding="utf-8"))
                handlers = [h for groups in settings["hooks"].values() for group in groups for h in group["hooks"]]
                self.assertEqual(len(handlers), 6, executable)
                self.assertEqual(settings["env"], {"USER_SETTING": "keep"})
                self.assertIn({"matcher": "Write", "hooks": [user_hook]}, settings["hooks"]["PreToolUse"])
                shell = "bash" if executable == "bash.exe" else "powershell"
                for handler in (h for h in handlers if h != user_hook):
                    self.assertEqual(handler["shell"], shell)
                    if shell == "powershell":
                        self.assertTrue(handler["command"].endswith("; exit $LASTEXITCODE"))
                self.assertEqual(json.loads((target / "hooks/statusline-original.json").read_text()), original_status)
            before = file.read_bytes()
            with mock.patch.object(install_hooks, "os", SimpleNamespace(name="nt")), \
                    mock.patch.object(context_status, "forward_argv", return_value=[second]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install_hooks.main(args), 0)
            self.assertEqual(file.read_bytes(), before)

    def test_powershell_to_git_bash_replaces_same_project_hooks(self):
        self.check_shell_switch("powershell.exe", "bash.exe")

    def test_git_bash_to_powershell_replaces_same_project_hooks(self):
        self.check_shell_switch("bash.exe", "powershell.exe")

    def test_reinstall_replaces_old_unquoted_interpreter(self):
        python = "C:/Program Files/Python/python.exe"
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            old = python + ' "' + (target / "hooks/skill_gate.py").as_posix() + '"'
            config = {"hooks": {"PreToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": old}]}]}}
            file = target / "settings.json"
            file.write_text(json.dumps(config), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install_hooks.main(["--claude-dir", str(target), "--python", python]), 0)
            handlers = [h for group in json.loads(file.read_text())["hooks"]["PreToolUse"] for h in group["hooks"]
                        if "skill_gate.py" in h["command"]]
            self.assertEqual(len(handlers), 1)
            self.assertEqual(shlex.split(handlers[0]["command"])[0], python)

    def test_launchers_and_powershell_call_operator(self):
        root = Path("C:/Users/Office/.claude")
        self.assertTrue(install_hooks.command_for("py -3", root, "skill_gate.py").startswith("py -3 "))
        command = install_hooks.command_for(r"C:\Program Files\Python\python.exe", root, "skill_gate.py", shell="powershell")
        self.assertTrue(command.startswith("& 'C:/Program Files/Python/python.exe' "))
        for invalid in ("", '""', "\npython", "'unterminated"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                install_hooks.python_argv(invalid)

    def test_windows_installer_shells_and_codex_encoded_command(self):
        import context_status
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for platform, executable in (("claude", "bash.exe"), ("claude", "powershell.exe"), ("codex", "powershell.exe")):
                with self.subTest(platform=platform, executable=executable):
                    target = root / (platform + executable) / "config folder"
                    args = ["--platform", platform, "--" + platform + "-dir", str(target),
                            "--python", "C:/Program Files/Python/python.exe"]
                    if platform == "claude":
                        args.append("--with-context-status")
                    with mock.patch.object(install_hooks, "os", SimpleNamespace(name="nt")), \
                            mock.patch.object(context_status, "forward_argv", return_value=[executable]), \
                            contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(install_hooks.main(args), 0)
                        file = target / ("settings.json" if platform == "claude" else "hooks.json")
                        before = file.read_bytes()
                        self.assertEqual(install_hooks.main(args), 0)
                        self.assertEqual(file.read_bytes(), before)
                    config = json.loads(before)
                    handler = config["hooks"]["SessionStart"][0]["hooks"][0]
                    if platform == "codex":
                        self.assertEqual(handler["additionalContextLimit"], 0)
                        parts = handler["command"].split()
                        self.assertEqual(parts[:4], ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand"])
                        decoded = base64.b64decode(parts[-1]).decode("utf-16-le")
                        self.assertIn("& 'C:/Program Files/Python/python.exe'", decoded)
                        self.assertTrue(decoded.endswith("; exit $LASTEXITCODE"))
                    elif executable == "powershell.exe":
                        self.assertEqual(handler["shell"], "powershell")
                        self.assertTrue(handler["command"].endswith("; exit $LASTEXITCODE"))
                        self.assertTrue(config["statusLine"]["command"].startswith("& 'C:/Program Files/Python/python.exe' "))
                    else:
                        self.assertEqual(handler["shell"], "bash")
                        self.assertEqual(shlex.split(handler["command"])[0], "C:/Program Files/Python/python.exe")

    def test_windows_python_path_is_one_argument(self):
        python = "C:/Program Files/Python/python.exe"
        command = install_hooks.command_for(python, Path("C:/Users/Office/.claude"), "skill_gate.py")
        self.assertEqual(shlex.split(command)[0], python)

    @unittest.skipIf(os.name == "nt", "POSIX shell 實測；Windows 另以替身驗證")
    def test_spaced_interpreter_executes_hook(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            interpreter = root / "Python folder/python"
            interpreter.parent.mkdir()
            interpreter.symlink_to(sys.executable)
            hook = root / "config/hooks/probe.py"
            hook.parent.mkdir(parents=True)
            hook.write_text("print('executed')\n", encoding="utf-8")
            command = install_hooks.command_for(str(interpreter), root / "config", "probe.py")
            result = subprocess.run(command, shell=True, capture_output=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "executed\n")


if __name__ == "__main__":
    unittest.main()
