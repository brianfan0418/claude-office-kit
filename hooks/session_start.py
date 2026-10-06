#!/usr/bin/env python3
"""SessionStart hook：開場把目前專案的交接檔放進 Claude 的 context。

讀取順序：目前資料夾與上層（最多 4 層）中，第一個存在的 docs/HANDOFF.md 或 HANDOFF.md。
輸出：該檔前 60 行，加上全檔中尚未完成的待辦（「- [ ]」開頭的行）。
找不到交接檔、或檔案是空的時候不輸出任何東西。
只用 Python 標準庫；輸出為純 ASCII 的 JSON（中文以 \\uXXXX 跳脫），不受 Windows 主控台編碼影響。
"""
import json
import os
import sys
import time
from pathlib import Path

HEAD_LINES = 60
MAX_TODOS = 20
MAX_LEVELS = 4
STALE_DAYS = 14
MAX_CHARS = 12000


def read_input():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
        return json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError):
        return {}


def find_handoff(start):
    """從 start 往上找，回傳第一個存在的交接檔路徑；找不到回傳 None。"""
    folder = Path(start)
    for _ in range(MAX_LEVELS):
        for rel in (Path("docs") / "HANDOFF.md", Path("HANDOFF.md")):
            candidate = folder / rel
            if candidate.is_file():
                return candidate
        if folder.parent == folder:
            break
        folder = folder.parent
    return None


def build_context(path):
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    lines = text.splitlines()
    if not any(line.strip() for line in lines):
        return None
    parts = [f"開場自動載入的交接檔：{path}（前 {HEAD_LINES} 行）", "", "\n".join(lines[:HEAD_LINES])]
    rest = [line.strip() for line in lines[HEAD_LINES:] if line.lstrip().startswith("- [ ]")]
    if rest:
        parts += ["", f"前 {HEAD_LINES} 行之後的未完成待辦（共 {len(rest)} 項，列出前 {MAX_TODOS} 項）："]
        parts += rest[:MAX_TODOS]
    try:
        age_days = (time.time() - path.stat().st_mtime) / 86400
    except OSError:
        age_days = 0
    if age_days > STALE_DAYS:
        parts += ["", f"這份交接檔已 {int(age_days)} 天沒有更新；依它行動之前，先用 git log 與實際檔案確認內容仍然正確。"]
    return "\n".join(parts)[:MAX_CHARS]


def main():
    data = read_input()
    start = data.get("cwd") or os.getcwd()
    path = find_handoff(start)
    if path is None:
        return 0
    context = build_context(path)
    if not context:
        return 0
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
