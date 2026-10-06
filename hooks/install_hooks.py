#!/usr/bin/env python3
"""把 hooks 複製到使用者層級的 .claude 資料夾，並合併進 settings.json。

用法：
  python hooks/install_hooks.py [--claude-dir <資料夾>] [--python python|py] [--dry-run]

行為：
  1. 複製 session_start.py、block_dangerous.py 到 <claude-dir>/hooks/（已存在且內容不同時，原檔另存 .bak-日期）。
  2. 讀取 <claude-dir>/settings.json（不存在視為空）；存在時先另存 settings.json.bak-日期。
  3. 在 hooks.SessionStart 與 hooks.PreToolUse 各加一筆；指令已存在就不重複加；既有的其他設定與 hooks 原樣保留。
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
SCRIPTS = ("session_start.py", "block_dangerous.py")
SESSION_MATCHER = "startup|resume|clear|compact"
PRETOOL_MATCHER = "Bash|PowerShell|Edit|Write|MultiEdit"


def command_for(python, claude_dir, script):
    path = (claude_dir / "hooks" / script).as_posix()
    return f'{python} "{path}"'


def add_hook(settings, event, matcher, command):
    """加入一筆 hook；回傳是否有新增。"""
    groups = settings.setdefault("hooks", {}).setdefault(event, [])
    for group in groups:
        for hook in group.get("hooks", []):
            if hook.get("command") == command:
                return False
    groups.append({"matcher": matcher, "hooks": [{"type": "command", "command": command}]})
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--claude-dir", default=str(Path.home() / ".claude"))
    parser.add_argument("--python", default="python", help="hook 指令使用的 Python 指令名稱（python 或 py）")
    parser.add_argument("--dry-run", action="store_true", help="只顯示會做什麼，不寫入")
    args = parser.parse_args(argv)

    claude_dir = Path(args.claude_dir)
    settings_path = claude_dir / "settings.json"
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
                            command_for(args.python, claude_dir, "session_start.py")))
    changed.append(add_hook(settings, "PreToolUse", PRETOOL_MATCHER,
                            command_for(args.python, claude_dir, "block_dangerous.py")))

    plan = [f"複製 {name} 到 {claude_dir / 'hooks'}" for name in SCRIPTS]
    plan.append("settings.json 新增 hook 設定 " + str(sum(changed)) + " 筆（已存在的不重複加）")
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
            shutil.copy2(settings_path, settings_path.with_name(f"settings.json.bak-{stamp}"))
        settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n".join(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
