"""接收 Claude Code 官方 statusLine JSON，保存同 session 的 context 百分比。

依據：https://code.claude.com/docs/en/statusline#context-window-fields
可作 statusLine；--record-only 供既有狀態列整合，--forward 可沿用原指令。
只保存百分比與時間，不讀 transcript 或保存提示、文件、登入資料。
"""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from hook_state import state_path, write_state


def forward_argv(command):
    """依官方 Windows 慣例使用 Git Bash 或 PowerShell，不交給 cmd.exe。"""
    if os.name != "nt":
        return [shutil.which("bash") or "/bin/sh", "-c", command]
    candidates = []
    found = shutil.which("bash")
    if found:
        candidates.append(Path(found))
    git = shutil.which("git")
    if git:
        candidates.extend(Path(git).parent.parent / sub for sub in ("bin/bash.exe", "usr/bin/bash.exe"))
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(key)
        if base:
            candidates.append(Path(base) / ("Programs/Git/bin/bash.exe" if key == "LOCALAPPDATA" else "Git/bin/bash.exe"))
    for path in candidates:
        # System32 的 bash 可能是 WSL 啟動器，不能當成 Windows Git Bash。
        if path.is_file() and "system32" not in str(path).lower():
            return [str(path), "-c", command]
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise OSError("找不到 Git Bash 或 PowerShell，請保留原狀態列並核對環境")
    return [powershell, "-NoProfile", "-NonInteractive", "-Command", command]


def record(data, now=None):
    session = data.get("session_id")
    if not isinstance(session, str) or not session:
        return None
    window = data.get("context_window") or {}
    percent = window.get("used_percentage") if isinstance(window, dict) else None
    if (type(percent) not in (int, float) or not math.isfinite(percent)
            or not 0 <= percent <= 100 or not isinstance(window.get("current_usage"), dict)):
        percent = None  # 官方 current_usage 在首次 API 回應前及壓縮後為 null。
    write_state(state_path(session, "context-usage"), {
        "source": "claude-statusline", "percent": percent,
        "measured_at": time.time() if now is None else now})
    return percent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-only", action="store_true")
    parser.add_argument("--forward", type=Path, help="安裝器備存的原 statusLine 設定 JSON")
    args = parser.parse_args(argv)
    raw = sys.stdin.buffer.read()
    percent = None
    try:
        data = json.loads(raw.decode("utf-8-sig"))
        if isinstance(data, dict):
            percent = record(data)
    except (OSError, ValueError, TypeError):
        pass  # 狀態列失敗不阻止工作，也不把未知用量寫成 0。
    if args.forward:
        try:
            original = json.loads(args.forward.read_text(encoding="utf-8-sig"))
            command = original["command"]
            if not isinstance(command, str) or not command:
                raise ValueError("原 statusLine 指令缺失")
            # 原本就是使用者設定的 shell 指令，不插入 JSON 內容或任務文字。
            result = subprocess.run(forward_argv(command), input=raw, capture_output=True, timeout=5)
            sys.stdout.buffer.write(result.stdout)
            sys.stderr.buffer.write(result.stderr)
            return result.returncode
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            print(f"原 statusLine 無法執行：{exc}", file=sys.stderr)
            return 1
    if not args.record_only:
        sys.stdout.write("context " + (f"{percent:g}%" if percent is not None else "unknown") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
