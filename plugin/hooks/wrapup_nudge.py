"""UserPromptSubmit：官方 context >=70%，尚缺寫法 skill 時同對話提醒一次。

用量由 context_status.py 接收 Claude statusLine 保存；沒有數值就不推算。
依據：https://code.claude.com/docs/en/hooks#userpromptsubmit
"""
import json
import math
import sys
from hook_state import loaded_skills, read_state, state_path, write_state

SKILLS = {"handoff-docs", "project-docs"}


def evaluate(data):
    if data.get("hook_event_name") != "UserPromptSubmit":
        return None
    session = data.get("session_id")
    if not isinstance(session, str) or not session:
        return None
    usage = read_state(state_path(session, "context-usage"))
    percent, measured = usage.get("percent"), usage.get("measured_at")
    boundary = read_state(state_path(session, "context-boundary")).get("since", 0)
    if (usage.get("source") != "claude-statusline"
            or type(percent) not in (int, float) or not math.isfinite(percent) or not 70 <= percent <= 100
            or type(measured) not in (int, float) or not math.isfinite(measured)
            or type(boundary) not in (int, float) or not math.isfinite(boundary) or measured <= boundary):
        return None
    missing = SKILLS - loaded_skills(session)
    marker = state_path(session, "wrapup-nudge")
    if not missing or read_state(marker).get("nudged"):
        return None
    write_state(marker, {"nudged": True})
    return (f"context 已達 {percent:g}%；建議先完整載入寫法 skill "
            + "、".join(sorted(missing)) +
            "，並把 docs/HANDOFF.md 更新到可接手狀態：目前進度、已定案事項、驗證證據、"
            "未完成項目與下一個可執行動作。這是同一對話的一次提醒，不表示工作已完成。")


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        context = evaluate(data) if isinstance(data, dict) else None
    except (OSError, ValueError, TypeError):
        return 0
    if context:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit", "additionalContext": context}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
