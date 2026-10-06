#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""以 Outlook 傳統版 COM 唯讀監看收件匣，新信寫成 JSONL。

用途：由 Windows 工作排程器每 5 分鐘執行一次；每次只處理上次之後的新信。
唯讀：不寄信、不移動、不刪除、不標已讀、不修改任何信件屬性。
輸出：<輸出資料夾>\\YYYY-MM-DD.jsonl（依收信日分檔，一行一封）。
     <輸出資料夾>\\_watch-state.json 保存水位；<輸出資料夾>\\attachments\\ 僅在 --save-attachments 時建立。

用法：outlook-watch.py [--check] [--output-dir inbox] [--max-body-chars 2000] [--save-attachments] [--first-run-days 1]（--check 只檢查能否連上 Outlook 傳統版）
需求：Windows、Outlook 傳統版（New Outlook 不提供 COM）、pip install pywin32。
結束碼：0 正常；2 無法連上 Outlook 傳統版；3 其他錯誤。
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

OL_FOLDER_INBOX = 6
OL_MAIL = 43  # OlObjectClass.olMail；會議邀請、回條等其他類型略過
STATE_NAME = "_watch-state.json"
DEFAULT_DIR = Path(__file__).resolve().parent / "inbox"
CONNECT_HELP = (
    "無法連上 Outlook 傳統版（COM）。請確認：\n"
    "  1. 已安裝並登入 Outlook 傳統版；右上角若有「新 Outlook」切換開關，須切回傳統版。\n"
    "  2. 以登入 Windows 的同一個使用者執行，且與 Outlook 同樣的權限層級（不要一邊以系統管理員、一邊一般使用者）。\n"
    "  3. 已執行 pip install pywin32。"
)


class OutlookUnavailable(RuntimeError):
    pass


def text(value):
    return "" if value is None else str(value).encode("utf-8", errors="replace").decode("utf-8")


def to_naive(value):
    """COM 回傳的時間可能帶時區；一律轉成本機無時區 datetime。"""
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=None)
    return None


def clean_body(body, limit):
    """正規化換行與連續空行，截取前 limit 字；回傳 (文字, 是否被截斷)。"""
    body = text(body).replace("\r\n", "\n").replace("\r", "\n")
    body = re.sub(r"[ \t]+\n", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body[:limit], len(body) > limit


def safe_filename(name, fallback):
    candidate = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text(name)).strip(". ")
    return candidate or fallback


# ---------- 狀態（水位） ----------

def load_state(path):
    if not path.exists():
        return {"version": 1, "watermark": None, "ids_at_watermark": []}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("version") != 1:
            raise ValueError("版本不支援")
        state.setdefault("ids_at_watermark", [])
        return state
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"無法讀取狀態檔 {path}：{exc}") from exc


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as h:
        json.dump(state, h, ensure_ascii=False, indent=2)
        h.write("\n")
        name = h.name
    os.replace(name, path)


def cutoff(state, now, first_run_days):
    """回傳 (起算時間, 起算時間當下已處理的 entry_id 集合)。"""
    if state.get("watermark"):
        return dt.datetime.fromisoformat(state["watermark"]), set(state["ids_at_watermark"])
    return now - dt.timedelta(days=first_run_days), set()


def advance(state, entry_id, received):
    stamp = received.isoformat(timespec="seconds")
    if state.get("watermark") is None or stamp > state["watermark"]:
        state["watermark"], state["ids_at_watermark"] = stamp, [entry_id]
    elif stamp == state["watermark"] and entry_id not in state["ids_at_watermark"]:
        state["ids_at_watermark"].append(entry_id)


# ---------- 輸出 ----------

def jsonl_path(output_dir, received):
    return output_dir / f"{received:%Y-%m-%d}.jsonl"


def already_written(path, entry_id):
    """寫入後、更新水位前若程式中斷，下次以此避免重複寫入。"""
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8", errors="replace") as h:
        for line in h:
            try:
                if json.loads(line).get("entry_id") == entry_id:
                    return True
            except json.JSONDecodeError:
                continue
    return False


def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as h:
        h.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def sender_address(mail):
    address = text(getattr(mail, "SenderEmailAddress", ""))
    if "@" in address:
        return address
    try:  # Exchange 內部寄件者的地址是 X500 格式，改取 SMTP
        return text(mail.Sender.PropertyAccessor.GetProperty(
            "http://schemas.microsoft.com/mapi/proptag/0x39FE001E")) or address
    except Exception:
        return address


def save_attachments(mail, output_dir, entry_id):
    digest = hashlib.sha256(entry_id.encode("utf-8", errors="replace")).hexdigest()[:24]
    folder = output_dir / "attachments" / digest
    saved = []
    for i in range(1, int(mail.Attachments.Count) + 1):
        att = mail.Attachments.Item(i)
        name = text(att.FileName) or f"attachment-{i}"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{i:03d}_{safe_filename(name, f'attachment-{i}')}"
        try:
            att.SaveAsFile(str(dest))  # 只把附件複製到磁碟，不改動信件
        except Exception:
            dest = folder / f"{i:03d}{Path(safe_filename(name, '')).suffix[:10]}"  # 路徑過長時改短名
            try:
                att.SaveAsFile(str(dest))
            except Exception as exc:
                saved.append({"filename": name, "saved_path": None, "error": text(exc)})
                continue
        saved.append({"filename": name, "saved_path": str(dest.relative_to(output_dir))})
    return saved


def build_record(mail, entry_id, received, max_chars, output_dir=None, with_attachments=False):
    body, truncated = clean_body(getattr(mail, "Body", ""), max_chars)
    names = []
    for i in range(1, int(mail.Attachments.Count) + 1):
        names.append(text(mail.Attachments.Item(i).FileName))
    record = {
        "entry_id": entry_id,
        "received_time": received.isoformat(timespec="seconds"),
        "sender_name": text(getattr(mail, "SenderName", "")),
        "sender_email": sender_address(mail),
        "to": text(getattr(mail, "To", "")),
        "subject": text(getattr(mail, "Subject", "")),
        "body_preview": body,
        "body_truncated": truncated,
        "attachment_filenames": names,
    }
    if with_attachments and names:
        record["attachments"] = save_attachments(mail, output_dir, entry_id)
    return record


def process(items, output_dir, state, state_path, now, max_chars, with_attachments=False,
            first_run_days=1, log=None):
    """逐封處理 items（可迭代的信件物件），回傳新寫入的封數。

    每寫完一封就更新水位；單封失敗只記錄並略過，不中斷整批。
    """
    log = log or (lambda message: print(message, file=sys.stderr))
    start, known = cutoff(state, now, first_run_days)
    candidates = []
    for mail in items:
        try:
            if int(getattr(mail, "Class", 0)) != OL_MAIL:
                continue
            received = to_naive(getattr(mail, "ReceivedTime", None))
            entry_id = text(getattr(mail, "EntryID", ""))
            if received is None or not entry_id:
                continue
            if received < start or (received == start and entry_id in known):
                continue
            candidates.append((received, entry_id, mail))
        except Exception as exc:
            log(f"警告：略過一封無法讀取的項目：{exc}")
    candidates.sort(key=lambda c: (c[0], c[1]))
    written = 0
    for received, entry_id, mail in candidates:
        try:
            path = jsonl_path(output_dir, received)
            if not already_written(path, entry_id):
                append_jsonl(path, build_record(mail, entry_id, received, max_chars, output_dir, with_attachments))
                written += 1
            advance(state, entry_id, received)
            save_state(state_path, state)
        except Exception as exc:
            log(f"警告：處理信件失敗，下次重試：{exc}")
            break  # 水位不可跨過失敗的信件，否則該信永遠不會被補寫
    return written


# ---------- Outlook 連線 ----------

def connect_outlook(dispatch=None):
    """回傳 (application, namespace)。不是傳統版或無法連線時拋 OutlookUnavailable。"""
    if dispatch is None:
        try:
            import win32com.client  # 只在 Windows 才需要
            from win32com.client import dynamic
        except ImportError as exc:
            raise OutlookUnavailable("找不到 pywin32（win32com）。" + CONNECT_HELP) from exc
        win32com.client.gencache.GetClassForCLSID = lambda clsid: None  # 避開 gen_py 快取問題
        dispatch = lambda: dynamic.Dispatch("Outlook.Application")
    try:
        app = dispatch()
        namespace = app.GetNamespace("MAPI")
        namespace.GetDefaultFolder(OL_FOLDER_INBOX)  # 實際取一次，確認 COM 可用
    except Exception as exc:
        raise OutlookUnavailable(f"{exc}\n{CONNECT_HELP}") from exc
    return app, namespace


def inbox_items(namespace, start):
    items = namespace.GetDefaultFolder(OL_FOLDER_INBOX).Items
    try:
        items.Sort("[ReceivedTime]", False)
        items = items.Restrict("[ReceivedTime] >= '" + start.strftime("%m/%d/%Y %I:%M %p") + "'")
    except Exception:
        pass  # 不支援時改由 process() 逐封比對時間
    for i in range(1, int(items.Count) + 1):
        yield items.Item(i)


def main(argv=None):
    p = argparse.ArgumentParser(description="唯讀監看 Outlook 傳統版收件匣")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.add_argument("--max-body-chars", type=int, default=2000)
    p.add_argument("--save-attachments", action="store_true")
    p.add_argument("--first-run-days", type=int, default=1, help="第一次執行時回溯的天數")
    p.add_argument("--check", action="store_true", help="只檢查能否連上 Outlook 傳統版")
    a = p.parse_args(argv)
    try:
        app, namespace = connect_outlook()
    except OutlookUnavailable as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 2
    if a.check:
        print(f"已連上 Outlook（版本 {text(getattr(app, 'Version', '未知'))}），收件匣可讀取。")
        return 0
    out = Path(a.output_dir)
    state_path = out / STATE_NAME
    try:
        state = load_state(state_path)
        now = dt.datetime.now()
        start, _ = cutoff(state, now, a.first_run_days)
        n = process(inbox_items(namespace, start), out, state, state_path, now,
                    a.max_body_chars, a.save_attachments, a.first_run_days)
    except Exception as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 3
    print(f"{dt.datetime.now():%Y-%m-%d %H:%M} 新增 {n} 封")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    sys.exit(main())
