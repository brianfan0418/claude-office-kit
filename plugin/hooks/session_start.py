#!/usr/bin/env python3
"""SessionStart hook：依專案必讀清單載入原文，供 Codex 與 Claude 共用。

讀取順序：目前資料夾與上層（最多 4 層）中，第一個存在的 docs/HANDOFF.md 或 HANDOFF.md。
輸出：該檔前 60 行，加上全檔中尚未完成的待辦（「- [ ]」開頭的行）。
清單位置 docs/session-start.json；沒有清單維持交接載入，建立清單的提示每 session 一次。
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
import re
from hook_state import notice_once, reset_skills, clear_skill_marks

HEAD_LINES = 60
MAX_TODOS = 20
MAX_LEVELS = 4
STALE_DAYS = 14
MAX_CHARS = 12000
LIST_FILE = Path("docs") / "session-start.json"
DEFAULT_LIMIT = 24000
HARD_LIMIT = 64000


def project_root(start):
    """清單優先；逐層尋找，支援在專案子資料夾開場。"""
    folder = Path(start).resolve()
    for _ in range(MAX_LEVELS):
        if (folder / LIST_FILE).is_file():
            return folder
        if (folder / "docs/HANDOFF.md").is_file() or (folder / "HANDOFF.md").is_file():
            return folder
        if folder.parent == folder:
            break
        folder = folder.parent
    return Path(start).resolve()


def section_text(text, title):
    """ATX 標題精確比對；包含下層章節，保留原文；忽略 fenced code。"""
    headings, fence = [], None
    offset = 0
    for line in text.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
        elif fence is None:
            match = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*#*\s*$", line)
            if match:
                headings.append((offset, len(match.group(1)), match.group(2)))
        offset += len(line)
    matches = [i for i, h in enumerate(headings) if h[2] == title]
    if len(matches) != 1:
        raise ValueError(f"章節「{title}」{'不存在' if not matches else '重名，請改為唯一標題'}")
    i = matches[0]
    start, level, _ = headings[i]
    end = next((h[0] for h in headings[i + 1:] if h[1] <= level), len(text))
    return text[start:end]


def registry_context(root, tools_dir):
    lines, seen, entries = [], set(), set()
    for path in (root / "tools/REGISTRY.md", root / "scripts/REGISTRY.md",
                 root / ".ai-office/tools/REGISTRY.md", tools_dir / "REGISTRY.md"):
        if path.resolve() in seen or not path.is_file():
            continue
        seen.add(path.resolve())
        try:
            rows = re.findall(r"^\| \[([^\]]+)\]\([^\n]+?\) \| ((?:\\\||[^|])+) \|", path.read_text(encoding="utf-8-sig"), re.M)
        except OSError:
            continue
        rows = [(name, purpose) for name, purpose in rows if (name, purpose) not in entries]
        if rows:
            entries.update(rows)
            lines.append(f"工具登記表：{path}（寫新腳本前建議先查，已有的直接使用）")
            lines.extend(f"{name} — {purpose.strip().replace(chr(92) + '|', '|')}" for name, purpose in rows)
    return "\n".join(lines)


def list_context(root, reserve=0):
    """回傳原文、問題、實際全文載入的 skills 與總長上限。"""
    path = root / LIST_FILE
    try:
        if path.stat().st_size > 256000:
            raise ValueError("清單超過 256 KB")
        config = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(config, dict) or type(config.get("version")) is not int or config.get("version") != 1:
            raise ValueError("version 應為 1")
        limit = config.get("max_chars", DEFAULT_LIMIT)
        if type(limit) is not int or not 2048 <= limit <= HARD_LIMIT:
            raise ValueError(f"max_chars 應為 2048 至 {HARD_LIMIT} 的整數")
        items = config.get("items")
        if not isinstance(items, list) or len(items) > 100:
            raise ValueError("items 應為至多 100 項的陣列")
    except (OSError, ValueError) as exc:
        return f"[清單錯誤] {LIST_FILE.as_posix()}：{exc}；請修正後重新載入。", [str(exc)], set(), DEFAULT_LIMIT
    rows, problems = [], []
    for i, item in enumerate(items, 1):
        try:
            if not isinstance(item, dict):
                raise ValueError("每項應為物件")
            rel, why, mode = (item.get(k) for k in ("path", "reason", "mode"))
            if not all(isinstance(v, str) and v.strip() for v in (rel, why, mode)):
                raise ValueError("需要 path、reason、mode")
            if mode not in ("full", "section", "path"):
                raise ValueError("mode 應為 full、section 或 path")
            file = Path(rel.replace("\\", "/"))
            if file.is_absolute() or ".." in file.parts or re.match(r"^[A-Za-z]:", rel):
                raise ValueError("path 請用專案內相對路徑")
            file = root / file
            header = f"{rel} — {why}（{mode}）"
            if not file.is_file():
                raise ValueError(f"[缺檔] {rel} — {why}")
            if mode == "path":
                rows.append((header + "；請先讀取原檔。", "", None))
                continue
            if file.stat().st_size > 2 * 1024 * 1024:
                rows.append((header + "；檔案超過 2 MB，請讀取原檔。", "", None))
                continue
            text = file.read_text(encoding="utf-8-sig")
            if mode == "section":
                title = item.get("section")
                if not isinstance(title, str) or not title.strip():
                    raise ValueError("section 模式需填 section 標題")
                text = section_text(text, title)
            skill = None
            match = re.search(r"(?:^|/)skills/(handoff-docs|project-docs)/SKILL\.md$", rel.replace("\\", "/"))
            if match and mode == "full":
                skill = match.group(1)
            rows.append((header, text, skill))
        except (OSError, ValueError) as exc:
            msg = f"[清單第 {i} 項] {exc}"
            problems.append(msg)
            rows.append((msg, "", None))
    title = "開場必讀清單（由專案 AI 維護；以下章節及全文照原文載入）："
    # 先替每項路徑／缺檔訊息保留空間，超量時不截斷條文。
    reserved = len(title) + sum(len(h) + 45 for h, _, _ in rows) + 200
    if reserved + reserve > limit:
        msg = f"[超過長度上限] 清單的路徑與理由已超過 {limit} 字元；請先讀 {LIST_FILE.as_posix()} 及各原檔。缺檔／格式／章節問題共 {len(problems)} 項；請執行 --check 核對。"
        return msg, problems, set(), limit
    remaining = limit - reserved - reserve
    parts, loaded = [title], set()
    for header, body, skill in rows:
        if body and len(body) <= remaining:
            parts.append(header + "\n" + body)
            remaining -= len(body)
            if skill:
                loaded.add(skill)
        elif body:
            parts.append(header + "；[超過長度上限] 未載入原文，請先讀取原檔。")
        else:
            parts.append(header)
    return "\n\n".join(parts), problems, loaded, limit


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
                    lines.append("工作線：" + "；".join(f"{Path(row.get('id', '?')).name} — {row.get('status', 'unknown')}" for row in rows[:5]))
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-dir", type=Path, default=Path(os.environ.get("AI_OFFICE_TOOLS", str(Path(__file__).resolve().parent.parent / "tools"))))
    parser.add_argument("--cwd", type=Path, help="手動核對的專案資料夾；指定時不讀 stdin")
    parser.add_argument("--text", action="store_true", help="手動讀取純文字；hook 請使用預設 JSON")
    parser.add_argument("--check", action="store_true", help="清單、檔案或章節有誤時回傳 1；hook 預設仍回傳 context")
    args = parser.parse_args(argv)
    data = {"cwd": str(args.cwd)} if args.cwd else read_input()
    start = data.get("cwd") or os.getcwd()
    root = project_root(start)
    registry = registry_context(root, args.tools_dir)
    extra = management_context(root, args.tools_dir, data.get("session_id"))
    supplements = "\n\n".join(p for p in (registry, extra) if p)
    problems, loaded, limit = [], set(), DEFAULT_LIMIT
    if (root / LIST_FILE).is_file():
        try:
            candidate = json.loads((root / LIST_FILE).read_text(encoding="utf-8-sig")).get("max_chars", DEFAULT_LIMIT)
            if type(candidate) is int and 2048 <= candidate <= HARD_LIMIT:
                limit = candidate
        except (OSError, ValueError, AttributeError):
            pass
        allowance = min(6000, limit // 3)
        if len(supplements) > allowance:
            kept = []
            for line in supplements.splitlines():
                if sum(len(row) + 1 for row in kept) + len(line) + 100 > allowance:
                    break
                kept.append(line)
            supplements = "\n".join(kept) + "\n[摘要超過長度上限] 其餘工具與工作線請查上述登記表及狀態工具。"
        context, problems, loaded, limit = list_context(root, len(supplements) + 4)
    else:
        path = find_handoff(start)
        context = build_context(path) if path else ""
        notice = notice_once(data.get("session_id"), root,
                             "尚無 docs/session-start.json；建議由專案 AI 參考工具包範本建立必讀文件清單。")
        supplements = "\n\n".join(p for p in (supplements, notice) if p)
    if len(context or "") + len(supplements) + 4 > limit:
        supplements = "工具及工作摘要超過剩餘長度；請查 tools/REGISTRY.md、派工狀態與文件落差工具。"
    context = "\n\n".join(part for part in (context, supplements) if part)
    if data.get("session_id"):
        try:
            clear_skill_marks(data["session_id"])
            reset_skills(data["session_id"], loaded)
        except OSError:
            context += "\n[載入紀錄無法寫入] 請核對 AI_OFFICE_STATE 權限。"
    if not context:
        return 0
    if args.text:
        sys.stdout.buffer.write(context.encode("utf-8"))
        if args.check and problems:
            sys.stderr.write(json.dumps({"problems": problems}) + "\n")
        return 1 if args.check and problems else 0
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    sys.stdout.write(json.dumps(out))
    return 1 if args.check and problems else 0


if __name__ == "__main__":
    sys.exit(main())
