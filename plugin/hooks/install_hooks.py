#!/usr/bin/env python3
"""備份合併 Claude 或 Codex 的開場、防護及寫法 hooks，不設排程或代為信任。

用法：
  python hooks/install_hooks.py [--platform claude|codex] [--claude-dir DIR|--codex-dir DIR] [--python python|py] [--dry-run]

行為：
  1. 複製三個 hooks 與共用 hook_state.py（既有不同內容另存 .bak-日期）。
  2. 讀取 Claude settings.json 或 Codex hooks.json；存在時先備份。
  3. 合併 SessionStart、PreToolUse 與 PostToolUse，已存在不重複。
  4. settings.json 不是合法的 JSON 時，停止且不修改任何檔案（結束碼 2）。
結束碼 0 表示完成或已經是最新。只用 Python 標準庫。
"""
import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = ("session_start.py", "block_dangerous.py", "skill_gate.py", "hook_state.py")
SESSION_MATCHER = "startup|resume|clear|compact"
PRETOOL_MATCHER = "Bash|PowerShell|Edit|Write|MultiEdit|apply_patch|Agent|spawn_agent|exec_command"


def command_for(python, claude_dir, script, platform="claude"):
    path = (claude_dir / "hooks" / script).as_posix()
    command = f'{python} "{path}"'
    if script == "session_start.py":
        command += f' --tools-dir "{(HERE.parent / "tools").as_posix()}"'
    if script == "block_dangerous.py" and platform == "codex":
        command += " --platform codex"
    return command


def add_hook(settings, event, matcher, command):
    """加入一筆 hook；回傳是否有新增。"""
    groups = settings.setdefault("hooks", {}).setdefault(event, [])
    for group in groups:
        for hook in group.get("hooks", []):
            if hook.get("command") == command:
                # 升級 matcher 亦須生效，包含 compact 與新增工具。
                if group.get("matcher") != matcher:
                    group["matcher"] = matcher
                    return True
                return False
            # 本安裝器舊版的同一指令升級為附 tools-dir 的版本，避免兩次開場輸出。
            if event == "SessionStart" and command.startswith(hook.get("command", "") + " --tools-dir "):
                hook["command"] = command
                group["matcher"] = matcher
                return True
    groups.append({"matcher": matcher, "hooks": [{"type": "command", "command": command}]})
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--claude-dir", default=str(Path.home() / ".claude"))
    parser.add_argument("--platform", choices=("claude", "codex"), default="claude")
    parser.add_argument("--codex-dir", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--python", default="python", help="hook 指令使用的 Python 指令名稱（python 或 py）")
    parser.add_argument("--dry-run", action="store_true", help="只顯示會做什麼，不寫入")
    args = parser.parse_args(argv)

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

    changed = []
    changed.append(add_hook(settings, "SessionStart", SESSION_MATCHER,
                            command_for(args.python, claude_dir, "session_start.py", args.platform)))
    changed.append(add_hook(settings, "PreToolUse", PRETOOL_MATCHER,
                            command_for(args.python, claude_dir, "block_dangerous.py", args.platform)))
    changed.append(add_hook(settings, "PreToolUse", PRETOOL_MATCHER,
                            command_for(args.python, claude_dir, "skill_gate.py")))
    changed.append(add_hook(settings, "PostToolUse", "Skill|Read|Bash|PowerShell|exec_command",
                            command_for(args.python, claude_dir, "skill_gate.py")))
    if args.platform == "codex":
        for group in settings["hooks"]["SessionStart"]:
            for hook in group.get("hooks", []):
                if "session_start.py" in hook.get("command", ""):
                    if hook.get("additionalContextLimit") != 0:
                        hook["additionalContextLimit"] = 0
                        changed.append(True)

    plan = [f"複製 {name} 到 {claude_dir / 'hooks'}" for name in SCRIPTS]
    plan.append(settings_path.name + " 新增或更新 hook 設定 " + str(sum(changed)) + " 筆（已存在的不重複加）")
    if args.platform == "codex":
        plan.append("採用後請在 Codex /hooks 審閱並信任；本安裝器不代為信任或設定排程。")
    if args.dry_run:
        print("\n".join(["（dry-run，未寫入）"] + plan))
        return 0

    (claude_dir / "hooks").mkdir(parents=True, exist_ok=True)
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
