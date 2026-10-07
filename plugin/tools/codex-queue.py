"""選用的資源等待派工：可用記憶體達門檻後送出並等待結果。

用法：python tools/codex-queue.py --min-free 2G [--max-wait 60] --brief FILE --out DIR [其他 submit 選項]
建議由 AI 的背景執行功能啟動；不使用 systemd 或自動設定排程。
"""
import argparse
from pathlib import Path
import subprocess
import sys
import time
from office_common import available_memory, emit, memory_bytes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-free", default="2G", type=memory_bytes)
    parser.add_argument("--max-wait", type=float, default=60)
    args, dispatch = parser.parse_known_args(argv)
    deadline = time.monotonic() + args.max_wait * 60
    while available_memory() < args.min_free:
        if time.monotonic() >= deadline:
            emit({"ok": False, "timed_out": True, "error": "資源等待逾時，尚未送出工作"})
            return 2
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    run = Path(__file__).with_name("codex-run.py")
    sent = subprocess.run([sys.executable, str(run), "submit", *dispatch], capture_output=True, encoding="utf-8")
    if sent.returncode:
        print(sent.stdout or sent.stderr, end="")
        return sent.returncode
    import json
    info = json.loads(sent.stdout)
    return subprocess.call([sys.executable, str(run), "wait", info["id"]])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)})
        raise SystemExit(1)
