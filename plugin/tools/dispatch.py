"""以中文任務名稱派工，從任務資料夾讀交辦與設定，保存結果及摘要。

用法：python dispatch.py 合約欄位整理 [--status|--wait]；python dispatch.py --list
採用：python tools/dispatch.py --install PROJECT（只部署入口及相依工具，不設排程）。
"""
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from office_common import emit, memory_bytes, write_json

HERE = Path(__file__).resolve().parent
RUNTIME = ("dispatch.py", "codex-run.py", "dispatch-status.py", "office_common.py",
           "win_memory.py", "registry.py")
FIELDS = {"version", "cwd", "out", "model", "effort", "sandbox", "search", "codex_home",
          "memory_max", "min_free", "max_wait", "timeout"}


def task_name(name):
    if (not name or name in (".", "..") or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or name.endswith((" ", ".")) or len(name) > 100
            or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name, re.I)):
        raise ValueError("任務名稱請用一個 Windows 可用的資料夾名稱，可使用中文")
    return name


def resolve(root, value):
    path = Path(value).expanduser()
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def load_task(root, name):
    task = root / "tasks" / task_name(name)
    config = json.loads((task / "task.json").read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict) or type(config.get("version")) is not int or config.get("version") != 1:
        raise ValueError("task.json 的 version 應為 1")
    unknown = set(config) - FIELDS
    if unknown:
        raise ValueError("task.json 未知欄位：" + "、".join(sorted(unknown)))
    for key in ("cwd", "out", "model", "effort", "sandbox", "codex_home", "memory_max", "min_free"):
        if key in config and config[key] is not None and (not isinstance(config[key], str) or not config[key].strip()):
            raise ValueError(key + " 應為非空字串或 null")
    if config.get("sandbox", "workspace-write") not in ("read-only", "workspace-write"):
        raise ValueError("sandbox 僅支援 read-only 或 workspace-write")
    if config.get("effort") not in (None, "low", "medium", "high", "xhigh", "max", "ultra"):
        raise ValueError("effort 不支援；請核對模型清單")
    if type(config.get("search", False)) is not bool:
        raise ValueError("search 應為 true 或 false")
    for key in ("timeout", "max_wait"):
        if key in config and (type(config[key]) not in (int, float) or not math.isfinite(config[key]) or config[key] <= 0):
            raise ValueError(key + " 應為正數分鐘")
    for key in ("memory_max", "min_free"):
        if config.get(key):
            memory_bytes(config[key])
    if config.get("memory_max") and os.name != "nt":
        raise ValueError("memory_max 僅支援 Windows；其他平台請設 null")
    cwd = resolve(root, config.get("cwd") or ".")
    out = resolve(root, config.get("out") or str(Path("inbox/codex") / name))
    brief = task / "brief.md"
    if not cwd.is_dir() or not brief.is_file() or not brief.read_text(encoding="utf-8-sig").strip():
        raise ValueError("工作資料夾或非空 brief.md 不存在")
    return task, config, cwd, out, brief


def install(root):
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    dest = root / ".ai-office/tools"
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    launcher = ('"""專案派工入口；任務與設定放 tasks/<任務名稱>/。"""\n'
                'from pathlib import Path\nimport runpy\nimport sys\n\n'
                'root = Path(__file__).resolve().parent\n'
                'sys.path.insert(0, str(root / ".ai-office/tools"))\n'
                'from dispatch import main\n'
                'raise SystemExit(main(root=root))\n')
    targets = [(dest / name, (HERE / name).read_bytes()) for name in RUNTIME]
    targets.append((root / "dispatch.py", launcher.encode("utf-8")))
    for path, content in targets:
        if path.exists() and path.read_bytes() != content:
            shutil.copy2(path, path.with_name(path.name + ".bak-" + stamp))
        path.write_bytes(content)
    # 任務範本另存於 tasks/_template，不覆寫已有交辦。
    template = HERE.parent / "templates/tasks/合約欄位整理"
    if template.is_dir():
        sample = root / "tasks/_template"
        sample.mkdir(parents=True, exist_ok=True)
        for name in ("brief.md", "task.json"):
            target = sample / name
            if not target.exists():
                shutil.copy2(template / name, target)
    subprocess.run([sys.executable, str(dest / "registry.py"), "tools", str(dest)], check=True)
    emit({"ok": True, "project": str(root), "command": "python dispatch.py 合約欄位整理",
          "next": "請由 AI 建立 tasks/合約欄位整理/brief.md 與 task.json，再用背景執行功能啟動"})
    return 0


def run_task(root, name, status=False, wait=False):
    task, config, cwd, out, brief = load_task(root, name)
    engine = HERE / "codex-run.py"
    if status or wait:
        command = [sys.executable, str(engine), "wait" if wait else "status", str(out)]
        if wait and config.get("timeout"):
            command += ["--timeout", str(config["timeout"])]
        return subprocess.call(command)
    if out.exists():
        raise ValueError("已有派工紀錄；請先用同任務名稱加 --status 核對，新的交辦請用新名稱")
    command = [sys.executable, str(engine), "submit", "--brief", str(brief), "--cwd", str(cwd),
               "--out", str(out), "--sandbox", config.get("sandbox") or "workspace-write"]
    for key in ("model", "effort", "memory_max"):
        if config.get(key):
            command += ["--" + key.replace("_", "-"), config[key]]
    if config.get("codex_home"):
        command += ["--codex-home", str(resolve(root, config["codex_home"]))]
    if config.get("search"):
        command.append("--search")
    if config.get("min_free"):
        command += ["--min-free", config["min_free"], "--max-wait", str(config.get("max_wait", 60))]
    result = subprocess.run(command, capture_output=True, encoding="utf-8")
    if result.returncode:
        sys.stdout.write(result.stdout or result.stderr)
        return result.returncode
    info = json.loads(result.stdout)
    if not info.get("ok"):
        emit(info)
        return 2
    write_json(out / "task-settings.json", config)
    emit(dict(info, task=name, message="已確認啟動；完成請查 --status 及 result.md、summary.json"))
    return 0


def main(argv=None, root=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?")
    parser.add_argument("--install", type=Path, metavar="PROJECT")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--status", action="store_true")
    actions.add_argument("--wait", action="store_true")
    actions.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    root = Path(root or Path.cwd()).resolve()
    try:
        if args.install:
            return install(args.install)
        if args.list:
            return subprocess.call([sys.executable, str(HERE / "dispatch-status.py"), str(root / "inbox/codex"), "--json"])
        if not args.name:
            parser.error("請提供任務名稱")
        return run_task(root, args.name, args.status, args.wait)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
