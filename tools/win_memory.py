"""以 Windows Job Object 限制本 worker 與子行程的合計 committed memory。

用法：python dispatch.py 任務名稱；task.json 的 memory_max 選用，worker 內部 import。
來源：https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
"""
import ctypes
import os

_handles = []  # 行程結束前保持 Job handle，子行程繼承同一 Job。


def apply_limit(size):
    if os.name != "nt":
        raise RuntimeError("--memory-max 的 Job Object 限制僅適用 Windows；其他平台請省略此選項")
    from ctypes import wintypes
    ptr = ctypes.c_size_t

    class Basic(ctypes.Structure):
        _fields_ = [("ProcessTime", ctypes.c_longlong), ("JobTime", ctypes.c_longlong),
                    ("Flags", wintypes.DWORD), ("MinWorkingSet", ptr), ("MaxWorkingSet", ptr),
                    ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ptr),
                    ("Priority", wintypes.DWORD), ("Scheduling", wintypes.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

    class Extended(ctypes.Structure):
        _fields_ = [("Basic", Basic), ("IO", IO), ("ProcessMemoryLimit", ptr), ("JobMemoryLimit", ptr),
                    ("PeakProcessMemory", ptr), ("PeakJobMemory", ptr)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    info = Extended()
    info.Basic.Flags = 0x200  # JOB_OBJECT_LIMIT_JOB_MEMORY
    info.JobMemoryLimit = size
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.get_last_error()
        kernel.CloseHandle(handle)
        raise ctypes.WinError(error)
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        error = ctypes.get_last_error()
        kernel.CloseHandle(handle)
        raise ctypes.WinError(error)
    _handles.append(handle)
