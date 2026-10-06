import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("outlook_watch", Path(__file__).resolve().parent / "outlook-watch.py")
ow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ow)


class Attachment:
    def __init__(self, name, fail=False):
        self.FileName, self.fail = name, fail

    def SaveAsFile(self, path):
        if self.fail:
            raise OSError("path too long")
        Path(path).write_bytes(b"x")


class Attachments:
    def __init__(self, items):
        self.items = items
        self.Count = len(items)

    def Item(self, i):
        return self.items[i - 1]


class Mail:
    Class = 43

    def __init__(self, entry_id, received, subject="主旨", body="內文", atts=(), cls=43):
        self.EntryID, self.ReceivedTime, self.Subject, self.Body = entry_id, received, subject, body
        self.SenderName, self.SenderEmailAddress, self.To = "寄件者", "a@example.com", "我"
        self.Attachments = Attachments(list(atts))
        self.Class = cls
        self.UnRead = True
        self.Touched = False


NOW = dt.datetime(2026, 10, 7, 12, 0)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "inbox"
        self.state_path = self.out / ow.STATE_NAME
        self.logs = []

    def tearDown(self):
        self.tmp.cleanup()

    def run_process(self, mails, **kw):
        state = ow.load_state(self.state_path)
        return ow.process(mails, self.out, state, self.state_path, NOW, kw.pop("max_chars", 2000),
                          log=self.logs.append, **kw)

    def lines(self, name):
        return [json.loads(l) for l in (self.out / name).read_text(encoding="utf-8").splitlines()]


class ProcessTest(Base):
    def test_record_format(self):
        m = Mail("E1", dt.datetime(2026, 10, 7, 9, 30), "合約續約", "第一行\r\n\r\n\r\n\r\n第二行", [Attachment("合約.pdf")])
        self.assertEqual(self.run_process([m]), 1)
        rec = self.lines("2026-10-07.jsonl")[0]
        self.assertEqual(rec["entry_id"], "E1")
        self.assertEqual(rec["subject"], "合約續約")
        self.assertEqual(rec["sender_email"], "a@example.com")
        self.assertEqual(rec["received_time"], "2026-10-07T09:30:00")
        self.assertEqual(rec["body_preview"], "第一行\n\n第二行")
        self.assertEqual(rec["attachment_filenames"], ["合約.pdf"])
        self.assertFalse(rec["body_truncated"])

    def test_body_truncated(self):
        self.run_process([Mail("E1", dt.datetime(2026, 10, 7, 9, 0), body="あ" * 50)], max_chars=10)
        rec = self.lines("2026-10-07.jsonl")[0]
        self.assertEqual(len(rec["body_preview"]), 10)
        self.assertTrue(rec["body_truncated"])

    def test_dedup_across_runs(self):
        mails = [Mail("E1", dt.datetime(2026, 10, 7, 9, 0)), Mail("E2", dt.datetime(2026, 10, 7, 9, 0))]
        self.assertEqual(self.run_process(mails), 2)
        self.assertEqual(self.run_process(mails), 0)
        self.assertEqual(len(self.lines("2026-10-07.jsonl")), 2)
        mails.append(Mail("E3", dt.datetime(2026, 10, 7, 10, 0)))
        self.assertEqual(self.run_process(mails), 1)

    def test_same_timestamp_new_mail_after_watermark(self):
        self.run_process([Mail("E1", dt.datetime(2026, 10, 7, 9, 0))])
        self.assertEqual(self.run_process([Mail("E1", dt.datetime(2026, 10, 7, 9, 0)),
                                           Mail("E2", dt.datetime(2026, 10, 7, 9, 0))]), 1)

    def test_first_run_ignores_old_mail(self):
        self.assertEqual(self.run_process([Mail("OLD", dt.datetime(2026, 9, 1, 9, 0))]), 0)

    def test_non_mail_items_skipped(self):
        self.assertEqual(self.run_process([Mail("E1", dt.datetime(2026, 10, 7, 9, 0), cls=53)]), 0)

    def test_files_split_by_day_and_sorted(self):
        self.run_process([Mail("B", dt.datetime(2026, 10, 7, 10, 0)), Mail("A", dt.datetime(2026, 10, 6, 15, 0))],
                         first_run_days=3)
        self.assertEqual(self.lines("2026-10-06.jsonl")[0]["entry_id"], "A")
        self.assertEqual(self.lines("2026-10-07.jsonl")[0]["entry_id"], "B")
        self.assertEqual(ow.load_state(self.state_path)["watermark"], "2026-10-07T10:00:00")

    def test_crash_between_write_and_state_does_not_duplicate(self):
        m = Mail("E1", dt.datetime(2026, 10, 7, 9, 0))
        ow.append_jsonl(ow.jsonl_path(self.out, m.ReceivedTime), ow.build_record(m, "E1", m.ReceivedTime, 100))
        self.assertEqual(self.run_process([m]), 0)
        self.assertEqual(len(self.lines("2026-10-07.jsonl")), 1)
        self.assertEqual(ow.load_state(self.state_path)["watermark"], "2026-10-07T09:00:00")

    def test_failure_stops_watermark_before_failed_mail(self):
        class Broken(Mail):
            @property
            def Body(self):
                raise RuntimeError("COM error")

            @Body.setter
            def Body(self, v):
                pass

        mails = [Mail("A", dt.datetime(2026, 10, 7, 8, 0)), Broken("B", dt.datetime(2026, 10, 7, 9, 0)),
                 Mail("C", dt.datetime(2026, 10, 7, 10, 0))]
        mails[1].Body = "x"
        self.assertEqual(self.run_process(mails), 1)
        self.assertEqual(ow.load_state(self.state_path)["watermark"], "2026-10-07T08:00:00")
        self.assertTrue(self.logs)

    def test_read_only_no_mutation(self):
        m = Mail("E1", dt.datetime(2026, 10, 7, 9, 0))
        self.run_process([m])
        self.assertTrue(m.UnRead)
        self.assertFalse(any(hasattr(m, n) for n in ("Delete", "Move", "Send", "Reply")))

    def test_save_attachments(self):
        m = Mail("E1", dt.datetime(2026, 10, 7, 9, 0), atts=[Attachment("a/b.pdf"), Attachment("long.pdf", fail=True)])
        self.run_process([m], with_attachments=True)
        rec = self.lines("2026-10-07.jsonl")[0]
        self.assertTrue((self.out / rec["attachments"][0]["saved_path"]).exists())
        self.assertIn("a_b.pdf", rec["attachments"][0]["saved_path"])
        self.assertIsNone(rec["attachments"][1]["saved_path"])


class ConnectTest(unittest.TestCase):
    def test_classic_outlook_ok(self):
        class NS:
            def GetDefaultFolder(self, n):
                return n

        class App:
            def GetNamespace(self, name):
                return NS()

        app, ns = ow.connect_outlook(lambda: App())
        self.assertIsInstance(ns, NS)

    def test_new_outlook_or_missing_raises_clear_error(self):
        def boom():
            raise OSError("Invalid class string")

        with self.assertRaises(ow.OutlookUnavailable) as ctx:
            ow.connect_outlook(boom)
        self.assertIn("傳統版", str(ctx.exception))

    def test_main_exit_code_when_unavailable(self):
        orig = ow.connect_outlook
        ow.connect_outlook = lambda *a, **k: (_ for _ in ()).throw(ow.OutlookUnavailable("x"))
        try:
            self.assertEqual(ow.main(["--check"]), 2)
        finally:
            ow.connect_outlook = orig


class StateTest(Base):
    def test_corrupt_state_raises(self):
        self.out.mkdir(parents=True)
        self.state_path.write_text("{壞", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            ow.load_state(self.state_path)


if __name__ == "__main__":
    unittest.main()
