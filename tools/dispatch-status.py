"""列出指定資料夾中的派工狀態、缺報告、失敗與中斷工作。

用法：python tools/dispatch-status.py [ROOT] [--json]
ROOT 預設為 AI_OFFICE_JOBS，未設定則為目前資料夾的 inbox/codex。
"""
import argparse
import importlib.util
import os
from pathlib import Path
from office_common import emit

spec = importlib.util.spec_from_file_location("office_codex_run", Path(__file__).with_name("codex-run.py"))
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def jobs(root):
    paths = {p.parent for p in Path(root).rglob("job.json") if "scratch" not in p.relative_to(root).parts}
    return [run.job_status(path) for path in sorted(paths)]


def brief(root):
    rows = jobs(root)
    counts = {name: sum(r["status"] == name for r in rows) for name in ("starting", "running", "failed", "interrupted", "missing-report", "unknown")}
    parts = [f"{key} {count}" for key, count in counts.items() if count]
    return "派工狀態：" + "；".join(parts) if parts else ""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path(os.environ.get("AI_OFFICE_JOBS", "inbox/codex")))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    rows = jobs(args.root)
    problems = sum(r["status"] not in ("done", "starting", "running") for r in rows)
    if args.json:
        emit({"jobs": rows, "problems": problems})
    else:
        for row in rows:
            print(f"{row['status']}：{row['id']}" + (f"；{row['error']}" if row.get("error") else ""))
        if not rows:
            print("指定資料夾沒有派工紀錄。")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
