#!/usr/bin/env python3
"""SessionStart hook：開場把目前專案的交接檔放進 Claude 的 context。

讀取順序：目前資料夾與上層（最多 4 層）中，第一個存在的 docs/HANDOFF.md 或 HANDOFF.md。
輸出：該檔前 60 行，加上全檔中尚未完成的待辦（「- [ ]」開頭的行）。
交接檔缺少或為空且沒有其他摘要時，不輸出任何東西。
如已採用工作管理工具，另附派工及文件落差摘要；無事項時省略，同一 session 相同摘要只輸出一次。
只用 Python 標準庫；輸出為純 ASCII 的 JSON（中文以 \\uXXXX 跳脫），不受 Windows 主控台編碼影響。
"""
import argparse
import hashlib
import json
import os
import sys
import subprocess
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
        parts += ["", f"這份交接檔已 {int(age_days)} 天沒有更新；依它行動之前，建議用檔案修改時間與實際內容核對；有 Git 時可加查 git log。"]
    return "\n".join(parts)[:MAX_CHARS]


def management_context(root, tools_dir, session=None):
    """只查本機紀錄；工具未採用或查詢失敗時略過，不查帳號或連網。"""
    lines = []
    jobs = Path(os.environ.get("AI_OFFICE_JOBS", str(root / "inbox" / "codex")))
    queries = [("dispatch-status.py", [str(jobs), "--json"]), ("doc-audit.py", [str(root), "--json"])]
    for name, args in queries:
        script = tools_dir / name
        if not script.is_file():
            continue
        try:
            result = subprocess.run([sys.executable, str(script), *args], capture_output=True, encoding="utf-8", timeout=8)
            info = json.loads(result.stdout)
            if name == "dispatch-status.py":
                rows = [row for row in info.get("jobs", []) if row.get("status") != "done"]
                if rows:
                    counts = {status: sum(r.get("status") == status for r in rows) for status in sorted({r.get("status", "unknown") for r in rows})}
                    lines.append("派工狀態：" + "；".join(f"{status} {count}" for status, count in counts.items()))
            elif info.get("count"):
                lines.append(f"文件落差 {info['count']} 項：" + "；".join(info.get("findings", [])[:3])[:500])
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    if lines and session:
        state = Path(os.environ.get("AI_OFFICE_STATE", str(Path.home() / ".ai-office-state")))
        key = hashlib.sha256((str(session) + str(root)).encode()).hexdigest()
        path = state / "session-brief" / (key + ".json")
        try:
            previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            fresh = [line for line in lines if line not in previous]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(list(dict.fromkeys(previous + lines))), encoding="utf-8")
            return "\n".join(fresh)
        except (OSError, ValueError):
            pass
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-dir", type=Path, default=Path(os.environ.get("AI_OFFICE_TOOLS", str(Path(__file__).resolve().parent.parent / "tools"))))
    args = parser.parse_args()
    data = read_input()
    start = data.get("cwd") or os.getcwd()
    path = find_handoff(start)
    context = build_context(path) if path else ""
    root = path.parent.parent if path and path.parent.name == "docs" else path.parent if path else Path(start)
    extra = management_context(root, args.tools_dir, data.get("session_id"))
    context = "\n\n".join(part for part in (context, extra) if part)
    if not context:
        return 0
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
