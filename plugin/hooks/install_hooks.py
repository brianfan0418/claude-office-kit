#!/usr/bin/env python3
"""備份合併 Claude 或 Codex 的開場、防護及寫法 hooks，不設排程或代為信任。

用法：
  python hooks/install_hooks.py [--platform claude|codex] [--claude-dir DIR|--codex-dir DIR] [--python python|py] [--dry-run]

行為：
  1. 複製 hooks 與共用狀態（既有不同內容另存 .bak-日期）。
  2. 讀取 Claude settings.json 或 Codex hooks.json；存在時先備份。
  3. 合併開場、工具事件；Claude 加每輪收尾提醒，已存在不重複。
  4. --with-context-status 選用 Claude 官方用量；備存並轉交原 statusLine，不設排程。
  5. settings.json 不是合法的 JSON 時，停止且不修改任何檔案（結束碼 2）。
結束碼 0 表示完成或已經是最新。只用 Python 標準庫。
"""
import argparse
import base64
import datetime
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = ("session_start.py", "block_dangerous.py", "skill_gate.py", "hook_state.py",
           "context_status.py", "wrapup_nudge.py")
SESSION_MATCHER = "startup|resume|clear|compact"
PRETOOL_MATCHER = "Bash|PowerShell|Edit|Write|MultiEdit|apply_patch|Agent|spawn_agent|exec_command"


def python_argv(value):
    """完整路徑是一個參數；短啟動器可附 -3，例如 py -3。"""
    if "\n" in value or "\r" in value:
        raise ValueError("--python 不可包含換行")
    value = value.strip()
    if not value:
        raise ValueError("--python 請提供 Python 指令或完整執行檔路徑")
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    if not value.strip():
        raise ValueError("--python 不可為空路徑")
    if "/" in value or "\\" in value:
        return [value.replace("\\", "/")]
    argv = shlex.split(value)
    if not argv or not argv[0]:
        raise ValueError("--python 不可為空指令")
    return argv


def command_for(python, claude_dir, script, platform="claude", shell="bash"):
    path = (claude_dir / "hooks" / script).as_posix()
    argv = python_argv(python)
    if shell == "powershell":
        # & 是 PowerShell 呼叫字串路徑的運算子；單引號內不展開變數。
        command = "& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in argv)
    else:
        command = " ".join(shlex.quote(arg) for arg in argv)
    def quoted(value):
        # 保持腳本路徑的雙引號格式，供既有 wrapper 辨識與升級。
        if shell == "powershell":
            value = value.replace("`", "``").replace("$", "`$").replace('"', '`"')
        else:
            value = re.sub(r'([\\$`\"])', r'\\\1', value)
        return '"' + value + '"'
    command += " " + quoted(path)
    if script == "session_start.py":
        command += " --tools-dir " + quoted((HERE.parent / "tools").as_posix())
    if script == "block_dangerous.py" and platform == "codex":
        command += " --platform codex"
    return command


def add_hook(settings, event, matcher, command, shell=None, legacy_commands=()):
    """加入一筆 hook；回傳是否有新增。"""
    groups = settings.setdefault("hooks", {}).setdefault(event, [])
    for group in groups:
        for hook in group.get("hooks", []):
            if hook.get("command") in legacy_commands and hook.get("command") != command:
                hook["command"] = command
                group["matcher"] = matcher
                if shell:
                    hook["shell"] = shell
                return True
            if hook.get("command") == command:
                # 升級 matcher 亦須生效，包含 compact 與新增工具。
                if group.get("matcher") != matcher or (shell and hook.get("shell") != shell):
                    group["matcher"] = matcher
                    if shell:
                        hook["shell"] = shell
                    return True
                return False
            # 本安裝器舊版的同一指令升級為附 tools-dir 的版本，避免兩次開場輸出。
            if event == "SessionStart" and command.startswith(hook.get("command", "") + " --tools-dir "):
                hook["command"] = command
                group["matcher"] = matcher
                return True
    handler = {"type": "command", "command": command}
    if shell:
        handler["shell"] = shell
    groups.append({"matcher": matcher, "hooks": [handler]})
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--claude-dir", default=str(Path.home() / ".claude"))
    parser.add_argument("--platform", choices=("claude", "codex"), default="claude")
    parser.add_argument("--codex-dir", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--python", default="python", help="Python 指令（python／py -3）或完整執行檔路徑，路徑有空白時加引號")
    parser.add_argument("--dry-run", action="store_true", help="只顯示會做什麼，不寫入")
    parser.add_argument("--with-context-status", action="store_true", help="Claude 選用官方 context 收尾提醒；沿用既有 statusLine")
    args = parser.parse_args(argv)
    try:
        python_argv(args.python)
    except ValueError as exc:
        parser.error(str(exc))
    if args.with_context_status and args.platform != "claude":
        parser.error("Codex 的官方 context 百分比取得方式未確認，不能設定 Claude statusLine。")

    claude_dir = args.codex_dir if args.platform == "codex" else Path(args.claude_dir)
    settings_path = claude_dir / ("hooks.json" if args.platform == "codex" else "settings.json")
    stamp = datetime.date.today().strftime("%Y%m%d")

    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            print(f"停止：{settings_path} 不是合法的 JSON（{exc}）。未修改任何檔案。", file=sys.stderr)
            return 2
        if not isinstance(settings, dict):
            print(f"停止：{settings_path} 的最上層不是物件。未修改任何檔案。", file=sys.stderr)
            return 2

    shell = "bash"
    if os.name == "nt":
        from context_status import forward_argv
        shell = "bash" if Path(forward_argv("")[0]).name.lower() in ("bash", "bash.exe") else "powershell"
    def hook_command(script):
        # Codex 未有 Claude 的 shell 欄位，Windows 明確啟動 PowerShell。
        if os.name == "nt" and args.platform == "codex":
            text = command_for(args.python, claude_dir, script, args.platform, "powershell") + "; exit $LASTEXITCODE"
            encoded = base64.b64encode(text.encode("utf-16-le")).decode("ascii")
            return "powershell.exe -NoProfile -NonInteractive -EncodedCommand " + encoded
        text = command_for(args.python, claude_dir, script, args.platform, shell)
        return text + "; exit $LASTEXITCODE" if shell == "powershell" else text
    def install_hook(event, matcher, script):
        legacy = f'{args.python} "{(claude_dir / "hooks" / script).as_posix()}"'
        legacy_commands = [legacy]
        if script == "session_start.py":
            legacy_commands.append(legacy + f' --tools-dir "{(HERE.parent / "tools").as_posix()}"')
        elif script == "block_dangerous.py" and args.platform == "codex":
            legacy_commands.append(legacy + " --platform codex")
        return add_hook(settings, event, matcher, hook_command(script),
                        shell if args.platform == "claude" and os.name == "nt" else None, legacy_commands)
    changed = []
    changed.append(install_hook("SessionStart", SESSION_MATCHER, "session_start.py"))
    changed.append(install_hook("PreToolUse", PRETOOL_MATCHER, "block_dangerous.py"))
    changed.append(install_hook("PreToolUse", PRETOOL_MATCHER, "skill_gate.py"))
    changed.append(install_hook("PostToolUse", "Skill|Read|Bash|PowerShell|exec_command", "skill_gate.py"))
    original_status = None
    original_path = claude_dir / "hooks" / "statusline-original.json"
    if args.platform == "claude":
        changed.append(install_hook("UserPromptSubmit", "", "wrapup_nudge.py"))
        if args.with_context_status:
            old = settings.get("statusLine")
            command = command_for(args.python, claude_dir, "context_status.py", shell=shell)
            if old is not None and (not isinstance(old, dict) or old.get("type") != "command"
                                    or not isinstance(old.get("command"), str) or not old["command"].strip()):
                print("停止：現有 statusLine 不是有效的 command；未修改任何檔案。", file=sys.stderr)
                return 2
            owned = (re.fullmatch(r'.+?\s+"' + re.escape((claude_dir / "hooks" / "context_status.py").as_posix())
                                 + r'"(?P<forward> --forward "[^"\r\n]+")?', old["command"]) if old else None)
            if owned:
                # 更新 Python 指令也不可把 wrapper 備存成自己的 original。
                command += owned["forward"] or ""
                if command != old["command"]:
                    settings["statusLine"] = dict(old, command=command)
                    changed.append(True)
            else:
                if old:
                    original_status = old.copy()
                    command += f' --forward "{original_path.as_posix()}"'
                settings["statusLine"] = dict(old or {}, type="command", command=command)
                changed.append(True)
    if args.platform == "codex":
        for group in settings["hooks"]["SessionStart"]:
            for hook in group.get("hooks", []):
                if "session_start.py" in hook.get("command", "") or hook.get("command") == hook_command("session_start.py"):
                    if hook.get("additionalContextLimit") != 0:
                        hook["additionalContextLimit"] = 0
                        changed.append(True)

    plan = [f"複製 {name} 到 {claude_dir / 'hooks'}" for name in SCRIPTS]
    plan.append(settings_path.name + " 新增或更新 hook 設定 " + str(sum(changed)) + " 筆（已存在的不重複加）")
    if args.platform == "codex":
        plan.append("採用後請在 Codex /hooks 審閱並信任；本安裝器不代為信任或設定排程。")
    elif args.with_context_status:
        plan.append("statusLine 接收官方 context；原狀態列已存在時備存並轉交，同對話 >=70% 提醒一次。")
    else:
        plan.append("收尾 hook 沒有官方用量時不提醒；需要時另選 --with-context-status。")
    if args.dry_run:
        print("\n".join(["（dry-run，未寫入）"] + plan))
        return 0

    (claude_dir / "hooks").mkdir(parents=True, exist_ok=True)
    if original_status is not None:
        if original_path.exists():
            shutil.copy2(original_path, original_path.with_name(f"{original_path.name}.bak-{stamp}"))
        original_path.write_text(json.dumps(original_status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in SCRIPTS:
        src, dst = HERE / name, claude_dir / "hooks" / name
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            shutil.copy2(dst, dst.with_name(f"{dst.name}.bak-{stamp}"))
        shutil.copy2(src, dst)
    if any(changed):
        if settings_path.exists():
            shutil.copy2(settings_path, settings_path.with_name(f"{settings_path.name}.bak-{stamp}"))
        settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n".join(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
