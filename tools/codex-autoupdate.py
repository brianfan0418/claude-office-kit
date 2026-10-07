"""選用的 Codex npm 更新、實測與回退；模型變更更新知識並寫收件匣通知。

用法：python tools/codex-autoupdate.py --knowledge FILE [--inbox DIR] [--dry-run] [--refresh-only] [--cache FILE] [--codex-home DIR] [--npm-prefix DIR]
不修改預設模型、帳號或排程；升級實測會使用目前帳號的一次短回覆額度。
來源：官方 Codex CLI 安裝與 App Server 文件；Windows 通知選擇見 README-ai-management.md。
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid
from codex_rpc import AppServer
from office_common import active_jobs, cli, emit, read_json, runtime_lock, state_dir, write_json, write_text
import registry

BEGIN = "<!-- CODEX-MODELS:BEGIN -->"
END = "<!-- CODEX-MODELS:END -->"
VERSION = r"\d+\.\d+\.\d+"


def command(args, timeout=180, **kwargs):
    return subprocess.run(args, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout, **kwargs)


def installed_version():
    result = command(cli("codex") + ["--version"], timeout=20)
    match = re.search(VERSION, result.stdout)
    if result.returncode or not match:
        raise RuntimeError("無法確認目前 Codex CLI 版本")
    return match[0]


def direct_codex_busy():
    """除了本工具登記的派工，也保守檢查直接執行的 Codex CLI。"""
    if os.name == "nt":
        query = "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^codex(?:\\.exe)?$' -or ($_.Name -eq 'node.exe' -and $_.CommandLine -match 'codex[\\/]bin[\\/]codex.js') }; @($p | Select-Object ProcessId) | ConvertTo-Json -Compress"
        result = command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query], timeout=30)
        if result.returncode:
            raise RuntimeError("無法查詢 Windows 行程；本輪未升級")
        return bool(json.loads(result.stdout or "[]"))
    proc = Path("/proc")
    if not proc.exists():
        raise RuntimeError("此平台無法檢查直接執行的 CLI；可先使用 --refresh-only")
    for path in proc.glob("[0-9]*/cmdline"):
        try:
            args = path.read_bytes().split(b"\0")
        except OSError:
            continue
        if any(Path(arg.decode(errors="replace")).name in ("codex", "codex.exe", "codex.js") for arg in args[:2]):
            return True
    return False


def npm_install(version, prefix=None):
    if not re.fullmatch(VERSION, version):
        raise ValueError("npm 版本格式不符")
    cmd = cli("npm") + ["install", "--global"]
    if prefix:
        cmd += ["--prefix", str(prefix)]
    return command(cmd + ["@openai/codex@" + version], timeout=600)


def smoke(home=None):
    scratch = state_dir() / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if home:
        env["CODEX_HOME"] = str(home)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="smoke-") as folder:
        result_path = Path(folder) / "result.md"
        result = command(cli("codex") + ["exec", "--skip-git-repo-check", "-C", folder, "-s", "read-only",
                                         "-c", 'approval_policy="never"', "--json", "-o", str(result_path), "只回覆 OK，不使用工具。"],
                         timeout=180, env=env)
        content = result_path.read_text(encoding="utf-8").strip() if result_path.exists() else ""
        return result.returncode == 0 and content == "OK"


def normalize_cache(data):
    rows = []
    for model in data["models"]:
        if model.get("visibility") != "list":
            continue
        rows.append({"slug": model["slug"], "description": model.get("description", "未提供"),
                     "default": model.get("default_reasoning_level", "未提供"),
                     "efforts": [r["effort"] for r in model.get("supported_reasoning_levels", [])]})
    return rows


def normalize_live(data):
    return [{"slug": model.get("model") or model["id"], "description": model.get("description", "未提供"),
             "default": model.get("defaultReasoningEffort", "未提供"),
             "efforts": [r["reasoningEffort"] for r in model.get("supportedReasoningEfforts", [])]}
            for model in data if not model.get("hidden")]


def validate_models(rows):
    if not rows or len({r["slug"] for r in rows}) != len(rows):
        raise ValueError("模型清單為空或重複，未更新知識")
    for row in rows:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", row["slug"]):
            raise ValueError("模型識別碼格式不符")
    return rows


def model_section(rows, source, date, version):
    lines = [BEGIN, f"資料日期：{date}；CLI 版本：{version}；來源：{source}。",
             "以下為帳號／客戶端回傳的可見清單快照，企業管理員可限制實際存取。", "",
             "| 模型 | 回傳的用途描述 | CLI 預設強度 | 支援強度 |", "|---|---|---|---|"]
    for row in rows:
        lines.append("| " + " | ".join(registry.cell(value).replace("<", "&lt;").replace(">", "&gt;") for value in (row["slug"], row["description"], row["default"], "、".join(row["efforts"]) or "未提供")) + " |")
    return "\n".join(lines + [END])


def update_knowledge(path, rows, source, date, version):
    text = path.read_text(encoding="utf-8-sig")
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
        raise ValueError("知識檔缺少唯一的 CODEX-MODELS 標記；請先使用工具包範本")
    _, _, errors = registry.generate("knowledge", path.parent)
    if errors:
        raise ValueError("知識索引 metadata 不完整，未修改文件：" + "；".join(errors))
    section = model_section(rows, source, date, version)
    updated = text[:text.index(BEGIN)] + section + text[text.index(END) + len(END):]
    updated = re.sub(r"(?m)^updated:.*$", "updated: " + date, updated, count=1)
    if text != updated:
        write_text(path, updated)
    target, index, errors = registry.generate("knowledge", path.parent)
    if errors:
        raise ValueError("知識索引 metadata 不完整：" + "；".join(errors))
    write_text(target, index)


def notify(inbox, title, info):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = inbox / f"codex-{stamp}-{uuid.uuid4().hex[:8]}.md"
    write_text(path, f"# {title}\n\n" + "\n".join(f"- {key}：{value}" for key, value in info.items()) + "\n")
    return str(path)


def upgrade(old, new, home, prefix):
    """升級與失敗回退都核對實際 CLI 版本；不盲目重跑不明的安裝。"""
    try:
        result = npm_install(new, prefix)
        if result.returncode:
            raise RuntimeError("npm 升級失敗：" + (result.stderr or result.stdout or "無錯誤輸出")[-1500:])
        if installed_version() != new:
            raise RuntimeError("npm 執行完成，但 CLI 版本與新版不符")
        if not smoke(home):
            raise RuntimeError("新版 CLI 的短回覆實測失敗")
        return {"ok": True, "from": old, "to": new, "smoke": "passed"}
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            # npm 子行程可能仍在安裝；不在狀態不明時覆蓋安裝。
            return {"ok": False, "from": old, "to": new, "error": "升級或實測逾時；請核對安裝行程與版本後再處理", "rollback": "not-run"}
        try:
            rollback = npm_install(old, prefix)
            verified = rollback.returncode == 0 and installed_version() == old
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            verified = False
        return {"ok": False, "from": old, "to": new, "error": str(exc), "rollback": "verified" if verified else "failed-or-unknown"}


def perform(args):
    if args.cache and not args.refresh_only:
        raise ValueError("--cache 僅能搭配 --refresh-only，避免用舊快照判斷升級")
    if not args.knowledge.is_file():
        raise ValueError("--knowledge 必須指向已採用的 codex-models.md")
    old_state = read_json(state_dir() / "autoupdate.json", {})
    report = {"ok": True, "upgraded": False}
    if not args.refresh_only:
        pending = state_dir() / "update-pending.json"
        if pending.exists():
            raise RuntimeError("上次升級尚無完成紀錄；請核對 update-pending.json 與實際版本")
        old = installed_version()
        result = command(cli("npm") + ["view", "@openai/codex", "version", "--json"], timeout=60)
        new = json.loads(result.stdout) if result.returncode == 0 else None
        if not isinstance(new, str) or not re.fullmatch(VERSION, new):
            raise RuntimeError("npm 未提供可辨識的正式版版本")
        report.update(current=old, latest=new)
        if tuple(map(int, new.split("."))) > tuple(map(int, old.split("."))):
            if active_jobs() or direct_codex_busy():
                return dict(report, deferred=True, note="有 Codex 工作執行中，本輪未升級；可於下次重跑")
            if args.dry_run:
                return dict(report, would_upgrade=True)
            prefix = args.npm_prefix
            if prefix is None:
                p = command(cli("npm") + ["prefix", "--global"], timeout=20)
                if p.returncode or not p.stdout.strip():
                    raise RuntimeError("無法確認 npm 全域安裝位置")
                prefix = Path(p.stdout.strip()).resolve()
            executable = Path(shutil.which("codex")).resolve()
            if prefix.resolve() not in executable.parents:
                raise RuntimeError("目前 Codex 不在指定 npm prefix；未升級，請核對安裝方式")
            # 先留意圖紀錄；中斷後須核對狀態，不在下次執行盲目重做。
            write_json(pending, {"from": old, "to": new, "pid": os.getpid()})
            report["upgrade"] = upgrade(old, new, args.codex_home, prefix)
            write_json(state_dir() / "last-upgrade.json", report["upgrade"])
            if report["upgrade"].get("ok") or report["upgrade"].get("rollback") == "verified":
                pending.unlink(missing_ok=True)
            if not report["upgrade"]["ok"]:
                report["ok"] = False
                report["notification"] = notify(args.inbox, "Codex 更新未完成", report["upgrade"])
                return report
            report["upgraded"] = True
    if args.cache:
        data = json.loads(args.cache.read_text(encoding="utf-8-sig"))
        rows = validate_models(normalize_cache(data))
        date = str(data.get("fetched_at", ""))[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError("cache 缺少可辨識的 fetched_at 日期")
        source, version = "models_cache.json（可見條目；本機觀察）", data.get("client_version", "未知")
    else:
        with AppServer(args.codex_home) as server:
            rows = validate_models(normalize_live(server.models()))
        date = datetime.now(timezone.utc).date().isoformat()
        source, version = "官方 App Server model/list", installed_version()
    before = {r["slug"] for r in old_state.get("models", [])}
    current = {r["slug"] for r in rows}
    report.update(added=sorted(current - before), removed=sorted(before - current), model_count=len(rows), dry_run=args.dry_run)
    if args.dry_run:
        return report
    update_knowledge(args.knowledge, rows, source, date, version)
    changed = rows != old_state.get("models")
    if changed or report["upgraded"]:
        report["notification"] = notify(args.inbox, "Codex 模型或版本已更新", {"CLI": version, "新增": report["added"], "移除": report["removed"],
                                                                               "知識檔": str(args.knowledge), "說明": "清單已更新；新模型用途請依官方文件核對。預設模型維持原設定。"})
    write_json(state_dir() / "autoupdate.json", {"models": rows, "date": date, "cli_version": version})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge", type=Path, required=True)
    parser.add_argument("--inbox", type=Path, default=state_dir() / "inbox")
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--npm-prefix", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--refresh-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    for name in ("knowledge", "inbox", "codex_home", "npm_prefix", "cache"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.expanduser().resolve())
    try:
        if args.dry_run:
            report = perform(args)
        else:
            with runtime_lock():
                report = perform(args)
        emit(report)
        return 0 if report["ok"] else 1
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as exc:
        emit({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
