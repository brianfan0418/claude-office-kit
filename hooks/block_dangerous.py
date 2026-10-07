#!/usr/bin/env python3
"""PreToolUse hook：攔截高風險指令，並保護 Claude 自己的設定。

掛在 Bash、PowerShell、Edit、Write。攔截項目：
  1. 遞迴刪除（rm -r、Remove-Item -Recurse、del /s、rd /s）
  2. 格式化或清除磁碟
  3. git push --force（含 --force-with-lease、-f、+分支）
  4. git reset --hard
  5. 以指令修改 .claude/settings.json 或 .claude/hooks/ 底下的檔案
  6. 前景等待派工或 sleep 輪詢（可用工具的背景執行功能等待）
Edit、Write 工具要修改上述設定檔時，不直接拒絕，改為請使用者在畫面上確認。

輸出格式依 Claude Code 官方文件（https://code.claude.com/docs/en/hooks）：
exit 0 並在 stdout 輸出 hookSpecificOutput.permissionDecision（deny 或 ask）。
只用 Python 標準庫。
"""
import json
import re
import sys

TRASH_HINT = (
    "改用資源回收筒：先列出要刪的項目給使用者確認，再移到資源回收筒。"
    "PowerShell 例：Add-Type -AssemblyName Microsoft.VisualBasic; "
    "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory('<資料夾>','OnlyErrorDialogs','SendToRecycleBin')"
    "（刪單一檔案改用 DeleteFile）。"
)

# 一段指令：以 ; && || 換行 與管線切開，避免把別段的旗標算進來
SEGMENT_SPLIT = re.compile(r"&&|\|\||[;\n|]")

# 刪除動詞（Unix 與 PowerShell 別名）
DELETE_VERBS = r"(?:remove-item|ri|rm|del|erase|rd|rmdir)"
# 遞迴旗標：Unix 短旗標組（-r、-rf、-fr）、--recursive、PowerShell -Recurse 及其縮寫
RECURSIVE_FLAG = r"(?:-[rRfivIdx]*[rR][rRfivIdx]*(?=\s|$)|--recursive\b|-rec\w*)"
RECURSIVE_DELETE = re.compile(
    rf"(?:^|\s|[(\"'])(?<!git )(?<!docker )(?<!npm )(?:{DELETE_VERBS})\b[^\n]*?\s{RECURSIVE_FLAG}", re.I)
CMD_RECURSIVE = re.compile(r"(?:^|\s)(?:del|erase|rd|rmdir)\b[^\n]*?\s/s\b", re.I)

FORMAT_DISK = re.compile(
    r"(?:^|\s)format(?:\.com)?\s+[a-z]:"
    r"|\bformat-volume\b|\bclear-disk\b|\bremove-partition\b|\binitialize-disk\b"
    r"|(?:^|\s)diskpart\b|\bmkfs(?:\.\w+)?\b|\bdd\b[^\n]*\bof=/dev/",
    re.I,
)

GIT_FORCE_PUSH = re.compile(
    r"\bgit\b[^\n]*?\bpush\b[^\n]*?(?:\s--force\S*|\s-[a-zA-Z]*f[a-zA-Z]*(?=\s|$)|\s\+\S)", re.I)
GIT_RESET_HARD = re.compile(r"\bgit\b[^\n]*?\breset\b[^\n]*?\s--hard\b", re.I)

# 受保護的設定：settings.json（含 settings.local.json）與 hooks 資料夾
PROTECTED = r"\.claude[/\\](?:settings(?:\.local)?\.json(?![\w.-])|hooks(?:[/\\]|(?![\w.-])))"
PROTECTED_RE = re.compile(PROTECTED, re.I)
REDIRECT_TO_PROTECTED = re.compile(r">>?\s*[\"']?[^\s\"'|;&]*" + PROTECTED, re.I)
COPY_VERBS = re.compile(r"^\s*(?:cp|copy|copy-item|xcopy|robocopy)\b", re.I)
WRITE_VERBS = re.compile(
    r"\b(?:set-content|add-content|out-file|tee-object|tee|sed\s+-i|mv|move|move-item|ren|rename|rename-item"
    r"|cp|copy|copy-item|xcopy|robocopy|rm|del|erase|ri|remove-item|rd|rmdir|truncate|chmod|icacls|attrib|new-item"
    r"|writealltext|writeallbytes|write_text|write_bytes|\.write\s*\(|open\s*\([^)]*[\"'][wa+])",
    re.I,
)

REASON_SELF = (
    "這會修改約束 Claude 行為的設定（.claude/settings.json 或 hooks）。"
    "請先向使用者說明要改什麼與原因，取得同意後，由使用者在畫面上確認 Edit 工具的變更；不要用指令繞過。"
)

FG_WAIT = re.compile(
    r"\bcodex-run\.py\s+wait\b|\bcodex-queue\.py\s+--"
    r"|\b(?:for|while|until)\b.*?\bdo\b.*?\bsleep\s+\d"
    r"|\b(?:while|foreach|for)\s*\(.*?\).*?\bStart-Sleep\b", re.I | re.S)


def foreground_wait(command, background=False):
    """忽略 heredoc／here-string 與文字參數；保留引號中的工具路徑。"""
    if background:
        return False
    view = re.sub(r"(<<-?\s*(['\"]?)(\w+)\2[^\n]*)\n.*?\n\s*\3[ \t]*(?=\n|$)", r"\1", command, flags=re.S)
    view = re.sub(r"(?ms)@(['\"])\r?\n.*?^\1@", " ", view)

    def quoted(match):
        value = match.group(2)
        # Windows 常以引號包工具的完整路徑，這仍是要執行的指令。
        if re.fullmatch(r"[^\r\n]*[/\\]codex-(?:run|queue)\.py", value, re.I) or value in ("codex-run.py", "codex-queue.py"):
            return " " + re.split(r"[/\\]", value)[-1] + " "
        return " "

    view = re.sub(r"(['\"])(.*?)(?<!\\)\1", quoted, view, flags=re.S)
    # help 只顯示用法，沒有等待。
    view = "\n".join(part for part in re.split(r"&&|\|\||[;\n]", view)
                     if not re.search(r"\s--help\b", part))
    return bool(FG_WAIT.search(view))


def writes_protected(command):
    """指令是否真的要寫入受保護的設定；只是讀取或把它當來源備份不算。"""
    for seg in SEGMENT_SPLIT.split(command):
        if REDIRECT_TO_PROTECTED.search(seg):
            return True
        if not PROTECTED_RE.search(seg) or not WRITE_VERBS.search(seg):
            continue
        if COPY_VERBS.match(seg):
            tokens = seg.split()
            if not PROTECTED_RE.search(tokens[-1]):
                continue
        return True
    return False


def check_command(command):
    """回傳攔截原因；放行回傳 None。"""
    flat = re.sub(r"[ \t]+", " ", command)
    for seg in SEGMENT_SPLIT.split(flat):
        if RECURSIVE_DELETE.search(seg) or CMD_RECURSIVE.search(seg):
            return "已攔截：遞迴刪除。" + TRASH_HINT
    if FORMAT_DISK.search(flat):
        return "已攔截：格式化或清除磁碟。這類動作需要使用者本人在場確認，請說明目的後由使用者自己執行。"
    if GIT_FORCE_PUSH.search(flat):
        return ("已攔截：git push --force 會覆蓋遠端歷史。改用一般的 git push；"
                "遠端有衝突時先 git pull 合併，或請使用者決定如何處理。")
    if GIT_RESET_HARD.search(flat):
        return ("已攔截：git reset --hard 會丟掉尚未提交的修改。"
                "先用 git status 與 git diff 確認內容，需要暫存改用 git stash，需要還原單一檔案改用 git restore <檔案>。")
    if writes_protected(command):
        return "已攔截。" + REASON_SELF
    return None


def evaluate(data):
    """回傳 (decision, reason)；放行回傳 None。"""
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    if tool in ("Bash", "PowerShell"):
        if foreground_wait(tool_input.get("command") or "", tool_input.get("run_in_background", False)):
            return ("deny", "已攔截：前景等待派工或輪詢。建議用工具的背景執行功能（run_in_background: true）等待 codex-run.py；查單次進度可用 status。PowerShell 可在獨立終端等待，讓目前對話保持可用。")
        reason = check_command(tool_input.get("command") or "")
        return ("deny", reason) if reason else None
    if tool in ("Edit", "Write", "MultiEdit"):
        path = str(tool_input.get("file_path") or "").replace("\\", "/")
        if PROTECTED_RE.search(path.replace("/", "\\")) or PROTECTED_RE.search(path):
            return ("ask", REASON_SELF)
    return None


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
        data = json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError):
        return 0
    verdict = evaluate(data)
    if verdict is None:
        return 0
    decision, reason = verdict
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
