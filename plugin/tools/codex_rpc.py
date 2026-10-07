"""以官方 Codex App Server stdio 協定查詢帳號限制及模型清單。

用法：由 codex-quota.py 與 codex-autoupdate.py import；不讀取或輸出憑證。
來源：https://learn.chatgpt.com/docs/app-server
"""
import json
import os
import queue
import subprocess
import threading
import time
from office_common import cli


class AppServer:
    def __init__(self, home=None, timeout=40):
        self.home, self.timeout = home, timeout
        self.messages = queue.Queue()
        self.seq = 0

    def __enter__(self):
        env = dict(os.environ)
        if self.home:
            env["CODEX_HOME"] = str(self.home)
        self.process = subprocess.Popen(cli("codex") + ["app-server"], env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, encoding="utf-8", errors="replace")
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            self.request("initialize", {"clientInfo": {"name": "office-kit", "version": "1.0"}})
            self._send({"method": "initialized"})
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _read(self):
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except ValueError:
                continue
        self.messages.put(None)

    def _send(self, value):
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def request(self, method, params=None):
        self.seq += 1
        request = {"id": self.seq, "method": method}
        if params is not None:
            request["params"] = params
        self._send(request)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                msg = self.messages.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                raise TimeoutError(f"{method} 超過 {self.timeout} 秒未回應")
            if msg is None:
                raise RuntimeError("App Server 已結束；請確認 CLI 版本與登入狀態")
            if msg.get("id") != self.seq:
                continue
            if "error" in msg:
                raise RuntimeError(json.dumps(msg["error"]))
            return msg["result"]

    def models(self):
        rows, cursor, seen = [], None, set()
        while True:
            params = {"limit": 100, "includeHidden": False}
            if cursor:
                params["cursor"] = cursor
            result = self.request("model/list", params)
            rows.extend(result["data"])
            cursor = result.get("nextCursor")
            if not cursor:
                return rows
            if cursor in seen:
                raise RuntimeError("模型清單分頁游標重複")
            seen.add(cursor)

    def __exit__(self, *args):
        self.process.kill()
        self.process.wait()
        self.reader.join(timeout=1)
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()
