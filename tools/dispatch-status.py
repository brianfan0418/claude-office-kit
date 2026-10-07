"""列出指定資料夾中的派工狀態、缺報告、失敗與中斷工作。

用法：python tools/dispatch-status.py [ROOT] [--project PROJECT] [--json]
ROOT 預設為 AI_OFFICE_JOBS，未設定則為目前資料夾的 inbox/codex。
--project 加讀 tasks/*/task.json 的輸出位置，與 ROOT 去重合併。
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
from office_common import emit

spec = importlib.util.spec_from_file_location("office_codex_run", Path(__file__).with_name("codex-run.py"))
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def project_outputs(project):
    """只讀任務設定；交辦已移走或 cwd 不存在仍可查既有紀錄。"""
    project = Path(project).resolve()
    outputs, warnings = set(), []
    for config in sorted((project / "tasks").glob("*/task.json")):
        try:
            data = json.loads(config.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict) or data.get("version") != 1:
                raise ValueError("設定應為 version 1 的 JSON 物件")
            value = data.get("out")
            if value is None or value == "":
                out = project / "inbox/codex" / config.parent.name
            elif isinstance(value, str):
                out = Path(value).expanduser()
                if not out.is_absolute():
                    out = project / out
            else:
                raise ValueError("out 應為路徑字串或 null")
            outputs.add(out.resolve())
        except (OSError, ValueError) as exc:
            warnings.append(f"{config.relative_to(project)} 無法核對輸出位置：{exc}")
    return outputs, warnings


def jobs(root, outputs=()):
    root = Path(root).resolve()
    paths = {p.parent.resolve() for p in root.rglob("job.json") if "scratch" not in p.relative_to(root).parts}
    # 自訂 out 是單一任務資料夾，不遞迴掃描其外部目錄。
    paths.update(Path(out).resolve() for out in outputs if (Path(out) / "job.json").is_file())
    return [run.job_status(path) for path in sorted(paths)]


def brief(root):
    rows = jobs(root)
    counts = {name: sum(r["status"] == name for r in rows) for name in ("starting", "queued", "running", "failed", "interrupted", "missing-report", "unknown")}
    parts = [f"{key} {count}" for key, count in counts.items() if count]
    return "派工狀態：" + "；".join(parts) if parts else ""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path(os.environ.get("AI_OFFICE_JOBS", "inbox/codex")))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--project", type=Path, help="合併專案任務設定所指定的輸出位置")
    args = parser.parse_args(argv)
    outputs, warnings = project_outputs(args.project) if args.project else ((), [])
    rows = jobs(args.root, outputs)
    problems = sum(r["status"] not in ("done", "starting", "queued", "running") for r in rows)
    if args.json:
        emit({"jobs": rows, "problems": problems, "warnings": warnings})
    else:
        for warning in warnings:
            print("總覽警示：" + warning)
        for row in rows:
            print(f"{row['status']}：{row['id']}" + (f"；{row['error']}" if row.get("error") else ""))
        if not rows:
            print("指定資料夾沒有派工紀錄。")
    return 1 if problems or warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
