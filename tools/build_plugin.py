#!/usr/bin/env python3
"""從 repo 的資源原始檔重建外掛副本，不安裝至使用者設定。

用法：python tools/build_plugin.py [--out plugin] [--check]
--check 只比對副本；缺檔、內容不同或有過期副本時結束碼為 1。
維護 skills、hooks 或附帶工具後重跑；直接修改副本會在下次重建被覆寫。
"""
import argparse
import json
from pathlib import Path
import registry

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "plugin"
TOOL_FILES = ("convert_docs.py", "README-convert-docs.md",
              "outlook-watch.py", "README-outlook-watch.md", "README-ai-management.md",
              "office_common.py", "codex_rpc.py", "win_memory.py", "codex-quota.py", "claude-quota.py",
              "codex-autoupdate.py", "codex-run.py", "codex-queue.py", "dispatch-status.py",
              "official-docs-fetch.py", "doc-audit.py", "registry.py", "REGISTRY.md")


def expected_files():
    files = {}
    for path in sorted((ROOT / "skills").rglob("*")):
        if path.is_file():
            rel = path.relative_to(ROOT).as_posix()
            content = path.read_text(encoding="utf-8")
            files[rel] = content.replace("<工具包資料夾>", "${CLAUDE_PLUGIN_ROOT}").encode()
    for name in ("session_start.py", "block_dangerous.py"):
        files[f"hooks/{name}"] = (ROOT / "hooks" / name).read_bytes()
    for name in TOOL_FILES:
        files[f"tools/{name}"] = (ROOT / "tools" / name).read_bytes()
    # 外掛只附選定工具，登記表也依實際封裝內容產生。
    _, tool_index, errors = registry.generate("tools", ROOT / "tools",
                                            [ROOT / "tools" / name for name in TOOL_FILES if name.endswith(".py")])
    if errors:
        raise ValueError("外掛工具缺 metadata：" + "；".join(errors))
    files["tools/REGISTRY.md"] = tool_index.encode("utf-8")
    for path in sorted((ROOT / "knowledge").glob("*.md")):
        files["knowledge/" + path.name] = path.read_bytes()
    manifest = {"name": "office-work-kit", "version": "0.2.0",
                "description": "文件證據、交接、派工記錄、模型知識與選用工作管理工具。",
                "repository": "https://github.com/brianfan0418/claude-office-kit",
                "license": "MIT", "author": {"name": "Office kit contributors"}}
    hooks = {"hooks": {
        "SessionStart": [{"matcher": "startup|resume|clear|compact", "hooks": [
            {"type": "command", "command": 'python "${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py"'}]}],
        "PreToolUse": [{"matcher": "Bash|PowerShell|Edit|Write|MultiEdit", "hooks": [
            {"type": "command", "command": 'python "${CLAUDE_PLUGIN_ROOT}/hooks/block_dangerous.py"'}]}]}}
    for rel, value in ((".claude-plugin/plugin.json", manifest), ("hooks/hooks.json", hooks)):
        files[rel] = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    files["README.md"] = (
        "# claude-office-kit 外掛\n\n"
        "本目錄由 `tools/build_plugin.py` 產生；維護原始資源後重建，勿直接修改副本。\n\n"
        "安裝前先了解使用者工作與環境，逐項決定採用哪些 skills 與 hooks，"
        "在封裝副本裁減未採用項目；完整兩種介面用法、官方依據與復原方式見 "
        "[採用指南](https://github.com/brianfan0418/claude-office-kit/blob/main/GUIDE-FOR-CLAUDE.md)。\n\n"
        "新增工作管理資源見 [工具說明](tools/README-ai-management.md)：模型與額度查詢、"
        "CLI 更新及收件匣通知、官方文件下載、背景派工及狀態、文件落差與登記表。"
        "模型知識見 [knowledge/codex-models.md](knowledge/codex-models.md)。Codex 與 Claude 均可協助選用，"
        "工具不設定排程；執行資料請存授權工作區，維持外掛安裝目錄唯讀。\n\n"
        "外掛結構已依官方格式封裝；本套 Python hooks 在 Cowork、Windows COM、"
        "主機 Codex 登入與 OCR／GPU 的整合未驗證。轉檔與工具依賴不會自動安裝。\n"
    ).encode()
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = expected_files()
    actual = {p.relative_to(args.out).as_posix() for p in args.out.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts} if args.out.exists() else set()
    stale = sorted(actual - expected.keys())
    if stale:
        print("有未列入原始資源的檔案，未修改；請先核對：" + "、".join(stale))
        return 1
    mismatches = []
    for rel, content in expected.items():
        dest = args.out / rel
        if not dest.is_file() or dest.read_bytes() != content:
            mismatches.append(rel)
            if not args.check:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
    if args.check and mismatches:
        print("外掛副本不同步：" + "、".join(mismatches))
        return 1
    print(f"外掛副本{'核對' if args.check else '重建'}完成：{len(expected)} 個檔案")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
