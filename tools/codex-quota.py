"""查詢目前 Codex 登入帳號的官方使用限制；無資料時明示未知。

用法：python tools/codex-quota.py [--codex-home DIR] [--json] [--timeout 40]
來源：https://learn.chatgpt.com/docs/app-server （account/rateLimits/read）
"""
import argparse
from datetime import datetime
from pathlib import Path
from codex_rpc import AppServer
from office_common import emit


def windows(result):
    buckets = result.get("rateLimitsByLimitId") or {"codex": result.get("rateLimits")}
    for name, bucket in buckets.items():
        if not bucket:
            continue
        for label in ("primary", "secondary"):
            window = bucket.get(label)
            if window:
                yield name, label, window


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=lambda s: Path(s).expanduser().resolve())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=float, default=40)
    args = parser.parse_args(argv)
    try:
        with AppServer(args.codex_home, args.timeout) as server:
            result = server.request("account/rateLimits/read")
        known = list(windows(result))
        output = {"ok": True, "available": bool(known), "source": "account/rateLimits/read", "data": result}
        if not known:
            output["note"] = "伺服器未提供限制視窗；即時剩餘額度未知，請查帳號或企業管理介面。"
        if args.json:
            emit(output)
        else:
            for bucket, label, window in known:
                reset = window.get("resetsAt")
                when = datetime.fromtimestamp(reset).astimezone().isoformat(timespec="minutes") if reset else "未知"
                print(f"{bucket}/{label}：已用 {window.get('usedPercent', '未知')}%；視窗 {window.get('windowDurationMins', '未知')} 分鐘；重置 {when}")
            if not known:
                print(output["note"])
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        emit({"ok": False, "available": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
