"""工作管理工具共用的 UTF-8、行程、CLI 與互斥鎖功能。

用法：由同目錄的工作管理工具 import；不需直接執行。
"""
import contextlib
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def write_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def emit(data):
    # ASCII JSON 可在 PowerShell 5.1 的預設主控台安全解碼。
    print(json.dumps(data))


def state_dir():
    return Path(os.environ.get("AI_OFFICE_STATE", str(Path.home() / ".ai-office-state"))).expanduser()


def cli(name):
    """npm 的 Windows .cmd 入口改由 node 執行，避免 shell 轉義使用者參數。"""
    path = shutil.which(name)
    if not path:
        raise FileNotFoundError(f"找不到 {name}，請先確認安裝與 PATH")
    if os.name == "nt" and Path(path).suffix.lower() in (".cmd", ".bat"):
        node = shutil.which("node")
        entry = Path(path).parent / ("node_modules/@openai/codex/bin/codex.js" if name == "codex"
                                    else "node_modules/npm/bin/npm-cli.js")
        if not node or not entry.is_file():
            raise RuntimeError(f"無法定位 {name} 的 node 入口；請使用官方 npm 安裝或原生 .exe")
        return [node, str(entry)]
    return [path]


def alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # 無權查詢時保守視為仍在跑
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        stat = Path(f"/proc/{pid}/stat")
        return not stat.exists() or stat.read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextlib.contextmanager
def runtime_lock():
    """更新與送出共用鎖；不自動拆除不明來源的鎖，避免重複升級。"""
    path = state_dir() / "runtime.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError:
        raise RuntimeError(f"工具正在送出或更新，請稍後重試；若上次中斷，先核對 {path} 的 owner.json")
    try:
        write_json(path / "owner.json", {"pid": os.getpid(), "time": time.time()})
        yield
    finally:
        (path / "owner.json").unlink(missing_ok=True)
        path.rmdir()


def active_jobs():
    rows = []
    for path in (state_dir() / "active").glob("*.json"):
        job = read_json(path)
        if job and (alive(job.get("pid")) or alive(job.get("child_pid"))):
            rows.append(job)
        elif job is None:
            rows.append({"error": f"無法讀取工作紀錄 {path}"})
    return rows


def memory_bytes(text):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([KMG]?)", text.upper())
    if not match:
        raise ValueError("記憶體大小請用 512M、2G 或位元組")
    size = int(float(match[1]) * 1024 ** {"": 0, "K": 1, "M": 2, "G": 3}[match[2]])
    if not 0 < size < 2**63:
        raise ValueError("記憶體上限須大於 0 且低於 2^63")
    return size


def available_memory():
    if os.name == "nt":
        from ctypes import wintypes
        class Memory(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (n, ctypes.c_ulonglong) for n in ("total", "available", "page", "avail_page", "virtual", "avail_virtual", "extended")]
        info = Memory()
        info.length = ctypes.sizeof(info)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):
            raise OSError("無法查詢可用記憶體")
        return info.available
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise OSError("此平台沒有可用記憶體查詢介面")
