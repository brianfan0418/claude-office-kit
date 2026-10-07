"""寫規則／專案文件或派工前檢查寫法 skills，成功讀取後記錄於同 session。

PreToolUse 未載入時 deny；PostToolUse 記錄 Skill、Read 或完整 cat/Get-Content。
依官方 hooks 的成功事件，不解析未保證穩定的 transcript 格式。
"""
import json
import re
import sys
from hook_state import loaded_skills, mark_skill
from block_dangerous import command_view

SKILLS = ("handoff-docs", "project-docs")
RULE = re.compile(r"(?:^|/)(?:CLAUDE|AGENTS)\.md$|(?:^|/)skills/[^/]+/|(?:^|/)(?:\.claude|\.codex)/rules/", re.I)
PROJECT = re.compile(r"(?:^|/)docs/(?:HANDOFF|ROADMAP|CHANGELOG)\.md$|(?:^|/)docs/(?:decisions|specs)/|(?:^|/)docs/session-start\.json$", re.I)
DISPATCH = re.compile(r"\bcodex-run\.py\s+submit\b|\bcodex-queue\.py\b|\bdispatch\.py\b", re.I)
BG_WAIT = re.compile(r"\bcodex-run\.py\s+(?:submit|wait)\b|\bcodex-queue\.py\b|\bdispatch\.py\b", re.I)
LABEL = re.compile(r"([^（）\r\n]+)（([A-Za-z0-9][A-Za-z0-9._/-]*)・([A-Za-z0-9][A-Za-z0-9._-]*)）")


def background_label_error(data):
    """只核對有背景參數的 shell 派工／等待，不把文件中的範例當成命令。"""
    inp = data.get("tool_input") or {}
    if data.get("tool_name") not in ("Bash", "PowerShell") or inp.get("run_in_background") is not True:
        return None
    command = inp.get("command") or ""
    parts = re.split(r"&&|\|\||[;\n]", command_view(command))
    if not any(BG_WAIT.search(part) and not re.search(r"\s--(?:help|status|list|install)\b", part)
               for part in parts):
        return None
    label = inp.get("description")
    match = LABEL.fullmatch(label.strip()) if isinstance(label, str) else None
    if match:
        task = match[1].strip()
        if task and not re.search(r"[/\\]|^[A-Za-z]:|\b(?:python\d*|py|dispatch\.py|codex-run\.py)\b", task, re.I):
            return None
    return ("背景派工與背景等待的 description 請寫「任務名（模型・強度）」，"
            "例如「合約欄位整理（gpt-6.1-sol・high）」；請核對任務設定中的模型與強度，"
            "畫面描述不放程式名稱、路徑或參數。補好 description 後可重試。")


def required(data):
    tool, inp = data.get("tool_name", ""), data.get("tool_input") or {}
    if tool in ("Agent", "spawn_agent"):
        return {"handoff-docs"}
    command = inp.get("command") or inp.get("cmd") or ""
    if tool in ("Bash", "PowerShell", "exec_command"):
        for part in re.split(r"&&|\|\||[;\n]", command_view(command)):
            if DISPATCH.search(part) and not re.search(r"\s--(?:help|status|list|install)\b", part):
                return {"handoff-docs"}
        if not re.search(r">|\b(?:Set-Content|Add-Content|Out-File|tee|sed\s+-i)\b|\.write_(?:text|bytes)\b|open\([^\n]*[\"'][wa]", command, re.I):
            return set()
        paths = re.findall(r"[^\s\"'<>;()]+(?:\.md|\.json)|[^\s\"'<>;()]*skills/[^\s\"'<>;()]+", command)
    elif tool == "apply_patch":
        paths = re.findall(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", command, re.M)
    elif tool in ("Write", "Edit", "MultiEdit"):
        paths = [inp.get("file_path", "")]
    else:
        return set()
    need = set()
    for path in paths:
        path = str(path).replace("\\", "/")
        if not path.startswith("/") and not re.match(r"^[A-Za-z]:", path) and data.get("cwd"):
            path = str(data["cwd"]).replace("\\", "/").rstrip("/") + "/" + path
        if PROJECT.search(path):
            need.update(SKILLS)
        elif RULE.search(path):
            need.add("handoff-docs")
    return need


def success(response):
    if isinstance(response, dict):
        if response.get("is_error") or response.get("isError") or response.get("error"):
            return False
        if response.get("success") is False or response.get("ok") is False:
            return False
        code = response.get("exit_code", response.get("exitCode"))
        if code is not None and code != 0:
            return False
    if isinstance(response, str):
        codes = re.findall(r"(?:exit code|Process exited with code)\s*:?\s*(-?\d+)", response, re.I)
        if any(int(code) != 0 for code in codes):
            return False
    return response is not None


def observed_skill(data):
    inp = data.get("tool_input") or {}
    response = data.get("tool_response")
    if not success(response):
        return set()
    tool = data.get("tool_name", "")
    if tool == "Skill":
        name = str(inp.get("skill", "")).rsplit(":", 1)[-1]
        return {name} if name in SKILLS else set()
    path = str(inp.get("file_path", "")).replace("\\", "/")
    if tool == "Read" and not inp.get("offset") and not inp.get("limit"):
        rendered = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        if "truncated" in rendered.lower():
            return set()
        file = response.get("file", {}) if isinstance(response, dict) else {}
        if isinstance(file, dict) and "numLines" in file and "totalLines" in file and file["numLines"] < file["totalLines"]:
            return set()
        return {s for s in SKILLS if path.endswith("/" + s + "/SKILL.md")
                and re.search(r"name:\s*[\"']?" + re.escape(s) + r"\b", rendered)}
    if tool in ("Bash", "PowerShell", "exec_command"):
        command = inp.get("command") or inp.get("cmd") or ""
        if not re.match(r"^\s*(?:cat\s+|Get-Content\s+)", command, re.I) or re.search(r"[|;&]|\s-(?:TotalCount|Tail)\b", command, re.I):
            return set()
        tokens = re.findall(r"[\"']([^\"']+)[\"']|([^\s]+)", command)
        paths = [(a or b).replace("\\", "/") for a, b in tokens]
        rendered = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        return {s for s in SKILLS if any(p.endswith("/" + s + "/SKILL.md") for p in paths)
                and re.search(r"name:\s*[\"']?" + re.escape(s) + r"\b", rendered)
                and "truncated" not in rendered.lower()}
    return set()


def evaluate(data):
    session = data.get("session_id")
    if data.get("hook_event_name") == "PostToolUse":
        for skill in observed_skill(data):
            mark_skill(session, skill)
        return None
    label_error = background_label_error(data)
    if label_error:
        return label_error
    missing = required(data) - loaded_skills(session)
    if missing:
        return ("本對話尚未載入寫法 skill：" + "、".join(sorted(missing)) +
                "。建議先以 Skill 工具載入，或完整讀取對應 skills/<名稱>/SKILL.md，再重試；專案文件需加讀 project-docs。")
    return None


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        reason = evaluate(data)
    except (OSError, ValueError, TypeError) as exc:
        print(f"skill-gate 無法核對：{exc}", file=sys.stderr)
        return 2
    if reason:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                           "permissionDecision": "deny", "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
