"""背景派工給 Codex，保存交辦、事件、回覆、摘要；預設不需 Git。

用法：python dispatch.py 任務名稱；本檔為派工引擎，對外使用任務資料夾入口。
來源：Codex 官方 non-interactive 文件與 codex exec --help（0.160.1）；Windows subprocess 文件。
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from office_common import alive, available_memory, cli, emit, memory_bytes, read_json, runtime_lock, state_dir, write_json, write_text


def job_status(out):
    out = Path(out)
    job = read_json(out / "job.json")
    summary = read_json(out / "summary.json")
    if summary is not None:
        status = "done" if summary.get("ok") else "failed"
        if summary.get("ok") and (not (out / "result.md").is_file() or not (out / "result.md").stat().st_size):
            status = "missing-report"
        return dict(summary, id=str(out), status=status)
    if not job:
        return {"ok": False, "id": str(out), "status": "unknown", "error": "找不到有效 job.json"}
    running = alive(job.get("pid")) or alive(job.get("child_pid"))
    return dict(job, id=str(out), status=job.get("status", "starting") if running else "interrupted",
                ok=False if not running else None)


def submit(args):
    brief = args.brief.expanduser().resolve().read_text(encoding="utf-8-sig")
    cwd, out = args.cwd.expanduser().resolve(), args.out.expanduser().resolve()
    if not brief.strip():
        raise ValueError("交辦檔是空的")
    if not cwd.is_dir():
        raise ValueError("工作資料夾不存在")
    if args.memory_max and os.name != "nt":
        raise ValueError("--memory-max 僅適用 Windows；其他平台請省略")
    # 先確認 CLI 存在，避免建立永遠不會執行的工作。
    cli("codex")
    with runtime_lock():
        out.parent.mkdir(parents=True, exist_ok=True)
        out.mkdir()  # 排他建立：既有紀錄一律保留
        params = {"cwd": str(cwd), "model": args.model, "effort": args.effort, "search": args.search,
                  "sandbox": args.sandbox, "codex_home": str(args.codex_home.expanduser().resolve()) if args.codex_home else None,
                  "memory_max": args.memory_max, "min_free": getattr(args, "min_free", None),
                  "max_wait": getattr(args, "max_wait", 60)}
        job = {"id": str(out), "job_id": uuid.uuid4().hex, "status": "starting", "submitted_at": time.time(),
               "pid": os.getpid(), "params": params}
        write_text(out / "brief.md", brief)
        (out / "scratch").mkdir()
        write_json(out / "job.json", job)
        active = state_dir() / "active" / (job["job_id"] + ".json")
        write_json(active, job)
        env = dict(os.environ, PYTHONUTF8="1")
        flags = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        try:
            with (out / "worker.log").open("wb") as log:
                worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_worker", str(out)],
                                          stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env, **flags)
            # worker 自己更新 job/active；父行程不在啟動後覆寫以免競爭。
        except OSError as exc:
            write_json(out / "summary.json", {"ok": False, "exit_code": None, "error": str(exc)})
            active.unlink(missing_ok=True)
            raise
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        current = job_status(out)
        if current["status"] in ("queued", "running", "done", "failed", "missing-report"):
            emit({"ok": current["status"] in ("queued", "running", "done"), "id": str(out), "pid": worker.pid, "status": current["status"]})
            return 0 if current["status"] in ("queued", "running", "done") else 1
        if not alive(worker.pid):
            break
        time.sleep(0.1)
    emit({"ok": False, "id": str(out), "status": "starting", "error": "未確認啟動；請用 status 查詢，確認前請勿重送"})
    return 2


def worker(out):
    out = Path(out)
    job = read_json(out / "job.json")
    params = job["params"]
    active = state_dir() / "active" / (job["job_id"] + ".json")
    start = time.time()
    summary = {"ok": False, "exit_code": None, "thread_id": None, "model": params["model"],
               "effort": params["effort"], "usage": {}, "codex_home": params["codex_home"],
               "memory_max": params["memory_max"], "started_at": start}
    job.update(pid=os.getpid(), status="starting")
    write_json(out / "job.json", job)
    write_json(active, job)
    try:
        if params.get("min_free"):
            threshold = memory_bytes(params["min_free"])
            deadline = time.monotonic() + params.get("max_wait", 60) * 60
            job.update(status="queued")
            write_json(out / "job.json", job)
            write_json(active, job)
            while available_memory() < threshold:
                if time.monotonic() >= deadline:
                    raise RuntimeError("資源等待逾時；尚未啟動 Codex，請核對後以新任務名稱交辦")
                time.sleep(min(5, max(0, deadline - time.monotonic())))
        if params["memory_max"]:
            from win_memory import apply_limit
            apply_limit(memory_bytes(params["memory_max"]))
        cmd = cli("codex") + (["--search"] if params["search"] else []) + [
            "exec", "--skip-git-repo-check", "--json", "-C", params["cwd"], "-s", params["sandbox"],
            "-c", 'approval_policy="never"', "-o", str(out / "result.md")]
        if params["sandbox"] == "workspace-write":
            cmd += ["--add-dir", str(out)]
        if params["model"]:
            cmd += ["-m", params["model"]]
        if params["effort"]:
            cmd += ["-c", "model_reasoning_effort=" + params["effort"]]
        cmd += ["-"]
        env = dict(os.environ)
        if params["codex_home"]:
            env["CODEX_HOME"] = params["codex_home"]
        prompt = (out / "brief.md").read_text(encoding="utf-8") + f"\n\n輸出目錄：{out}\n中間檔請放 {out / 'scratch'}；交付物請放輸出目錄其他位置。"
        # 檔案 stdin 避免長交辦在 pipe 寫入時阻塞，並保留完整實際交辦。
        write_text(out / "prompt.txt", prompt)
        with (out / "prompt.txt").open("rb") as inp, (out / "events.jsonl").open("wb") as events, (out / "stderr.log").open("wb") as errors:
            child = subprocess.Popen(cmd, stdin=inp, stdout=events, stderr=errors, env=env, cwd=params["cwd"])
            job.update(status="running", child_pid=child.pid, started_at=start)
            write_json(out / "job.json", job)
            write_json(active, job)
            summary["exit_code"] = child.wait()
        event_error = None
        with (out / "events.jsonl").open(encoding="utf-8", errors="replace") as events:
            for line in events:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "thread.started":
                    summary["thread_id"] = event.get("thread_id")
                if event.get("type") == "turn.completed":
                    for key, value in (event.get("usage") or {}).items():
                        if isinstance(value, (float, int)):
                            summary["usage"][key] = summary["usage"].get(key, 0) + value
                if event.get("type") in ("turn.failed", "error"):
                    event_error = event.get("error") or event.get("message") or event["type"]
        report = out / "result.md"
        summary["ok"] = summary["exit_code"] == 0 and report.is_file() and bool(report.read_text(encoding="utf-8").strip()) and event_error is None
        if not summary["ok"]:
            summary["error"] = event_error or "CLI 失敗或缺少回覆；請查看 stderr.log 與 events.jsonl"
    except Exception as exc:
        summary["error"] = str(exc)
    finally:
        summary.update(finished_at=time.time(), elapsed_seconds=round(time.time() - start, 2))
        write_json(out / "summary.json", summary)
        active.unlink(missing_ok=True)
    return 0 if summary["ok"] else 1


def inspect(args):
    deadline = time.monotonic() + args.timeout * 60 if args.timeout is not None else None
    while True:
        status = job_status(args.id.expanduser().resolve())
        if args.command == "status" or status["status"] not in ("starting", "queued", "running"):
            emit(status)
            return 0 if status["status"] in ("starting", "queued", "running", "done") else 1
        if deadline is not None and time.monotonic() >= deadline:
            emit(dict(status, timed_out=True))
            return 2
        time.sleep(1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sub = commands.add_parser("submit")
    sub.add_argument("--brief", type=Path, required=True)
    sub.add_argument("--out", type=Path, required=True)
    sub.add_argument("--cwd", type=Path, default=Path.cwd())
    sub.add_argument("--model")
    sub.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max", "ultra"])
    sub.add_argument("--search", action="store_true")
    sub.add_argument("--sandbox", choices=["read-only", "workspace-write"], default="workspace-write")
    sub.add_argument("--codex-home", type=Path)
    sub.add_argument("--memory-max", type=lambda s: s if memory_bytes(s) else s)
    sub.add_argument("--min-free", type=lambda s: s if memory_bytes(s) else s)
    sub.add_argument("--max-wait", type=float, default=60)
    for name in ("wait", "status", "_worker"):
        p = commands.add_parser(name)
        p.add_argument("id", type=Path)
        p.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "submit":
            return submit(args)
        if args.command == "_worker":
            return worker(args.id)
        return inspect(args)
    except (OSError, ValueError, RuntimeError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
