"""兩端 hooks 共用的 session 狀態；只保存載入標記與提醒，不保存文件內容。"""
import hashlib
import json
import os
from pathlib import Path
import uuid


def state_path(session, kind, extra=""):
    root = Path(os.environ.get("AI_OFFICE_STATE", str(Path.home() / ".ai-office-state")))
    key = hashlib.sha256((str(session) + "\n" + str(extra)).encode()).hexdigest()
    return root / kind / (key + ".json")


def read_state(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def notice_once(session, root, notice):
    if not session:
        return notice  # 沒有 session id 時不把不同對話誤當同一次。
    path = state_path(session, "session-notices", root)
    try:
        data = read_state(path)
        if notice in data.get("notices", []):
            return ""
        data.setdefault("notices", []).append(notice)
        write_state(path, data)
    except OSError:
        pass
    return notice


def reset_skills(session, loaded=()):
    if session:
        write_state(state_path(session, "skill-gate"), {"loaded": list(loaded)})


def mark_skill(session, skill):
    if session:
        # 各 skill 分檔，避免平行 PostToolUse 互相覆寫。
        write_state(state_path(session, "skill-loaded", skill), {"loaded": True})


def clear_skill_marks(session):
    if session:
        for skill in ("handoff-docs", "project-docs"):
            state_path(session, "skill-loaded", skill).unlink(missing_ok=True)


def loaded_skills(session):
    if not session:
        return set()
    loaded = set(read_state(state_path(session, "skill-gate")).get("loaded", []))
    return loaded | {s for s in ("handoff-docs", "project-docs")
                     if read_state(state_path(session, "skill-loaded", s)).get("loaded")}
