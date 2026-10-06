#!/usr/bin/env python3
"""test_convert_docs.py - convert_docs.py 的單元測試，可在 Linux 執行；Word COM 以假物件取代。

用法：python -m unittest tools/test_convert_docs.py -v
（若已安裝 markitdown 與 reportlab、python-docx，另會執行真實轉換的整合測試；否則該組自動略過。）
"""
import hashlib
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_docs as cd  # noqa: E402

T1 = datetime(2026, 10, 7, 6, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 10, 7, 7, 0, 0, tzinfo=timezone.utc)


class FakeDoc:
    def __init__(self, log, content):
        self.log, self.content = log, content

    def SaveAs2(self, FileName, FileFormat):
        self.log.append(("SaveAs2", Path(FileName).suffix, FileFormat))
        Path(FileName).write_bytes(self.content)

    def Close(self, SaveChanges):
        self.log.append(("Close", SaveChanges))


class FakeDocuments:
    def __init__(self, log):
        self.log = log

    def Open(self, FileName, ReadOnly, AddToRecentFiles, ConfirmConversions):
        self.log.append(("Open", Path(FileName).name, ReadOnly))
        return FakeDoc(self.log, b"PK-fake-docx")


class FakeWord:
    def __init__(self, log):
        self.log = log
        self.Documents = FakeDocuments(log)

    def Quit(self, SaveChanges):
        self.log.append(("Quit", SaveChanges))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.src = self.root / "src"
        self.out = self.root / "src-md"
        self.src.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, data=b"data"):
        p = self.src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def run_convert(self, now=T1, **kw):
        return cd.convert_tree(self.src, self.out, now=now, **kw)

    def fm(self, rel):
        fm, body = cd.read_md(self.out / (rel + ".md"))
        return cd.parse_managed(fm), fm, body


class TestFrontmatter(unittest.TestCase):
    def test_roundtrip_and_blank_business_fields(self):
        managed = {"source_path": "a/b.docx", "source_sha256": "ab" * 32, "source_modified": "x",
                   "converter": "markitdown 0.1.8", "converted_at": "y", "pages": 3, "ocr": "required", "ocr_engine": "", "ocr_pages": [], "ocr_source": "", "ocr_source_sha256": "",
                   "title": "標題: 含冒號與\"引號\"", "warnings": ["w1"], "needs_review": False}
        text = cd.build_frontmatter(managed) + "\n本文\n"
        fm, body = cd.split_frontmatter(text)
        self.assertEqual(cd.parse_managed(fm), managed)
        self.assertEqual(body.strip(), "本文")
        for k in cd.BUSINESS_KEYS:
            self.assertIn(f"{k}:", fm)
        self.assertTrue(text.startswith("---\n"))

    def test_all_required_fields_present(self):
        text = cd.build_frontmatter({})
        for k in ["source_path", "source_sha256", "source_modified", "converter",
                  "converted_at", "pages", "ocr", "title"]:
            self.assertRegex(text, rf"(?m)^{k}:")

    def test_business_tail_preserved_verbatim(self):
        tail = ['doc_type: "服務合約"', "parties:", "  - 甲", "  - 乙"]
        text = cd.build_frontmatter({"title": "t"}, tail)
        fm, _ = cd.split_frontmatter(text)
        self.assertEqual(cd.business_tail(fm), tail)


class TestIncremental(Base):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(cd, "run_markitdown", side_effect=lambda p: f"# 標題\n\n內容 {p.name}\n")
        self.md = patcher.start()
        self.addCleanup(patcher.stop)

    def test_new_then_unchanged_then_updated(self):
        f = self.write("sub/甲.docx", b"v1")
        s = self.run_convert()
        self.assertEqual((s["new"], s["unchanged"], s["updated"]), (1, 0, 0))
        m, _, body = self.fm("sub/甲.docx")
        self.assertEqual(m["source_sha256"], hashlib.sha256(b"v1").hexdigest())
        self.assertEqual(m["source_path"], "sub/甲.docx")
        self.assertEqual(m["title"], "標題")
        self.assertIs(m["ocr"], False)

        calls = self.md.call_count
        s = self.run_convert(now=T2)
        self.assertEqual((s["new"], s["unchanged"], s["updated"]), (0, 1, 0))
        self.assertEqual(self.md.call_count, calls)  # 沒變就不再轉換

        f.write_bytes(b"v2")
        s = self.run_convert(now=T2)
        self.assertEqual(s["updated"], 1)
        m, _, _ = self.fm("sub/甲.docx")
        self.assertEqual(m["source_sha256"], hashlib.sha256(b"v2").hexdigest())
        hist = list((self.out / "_history").rglob("*.md"))
        self.assertEqual(len(hist), 1)
        self.assertIn(hashlib.sha256(b"v1").hexdigest()[:8], hist[0].name)
        self.assertIn(hashlib.sha256(b"v1").hexdigest(), hist[0].read_text(encoding="utf-8"))

    def test_force_reconverts(self):
        self.write("a.docx", b"x")
        self.run_convert()
        s = self.run_convert(force=True)
        self.assertEqual(s["updated"], 1)

    def test_business_fields_kept_and_flagged_after_update(self):
        f = self.write("a.docx", b"v1")
        self.run_convert()
        p = self.out / "a.docx.md"
        p.write_text(p.read_text(encoding="utf-8").replace("doc_type:\n", 'doc_type: "NDA"\n'), encoding="utf-8")
        f.write_bytes(b"v2")
        self.run_convert(now=T2)
        m, fm, _ = self.fm("a.docx")
        self.assertIn('doc_type: "NDA"', fm)
        self.assertIs(m["needs_review"], True)

    def test_source_never_modified(self):
        f = self.write("a.docx", b"keep")
        mtime = f.stat().st_mtime_ns
        self.run_convert()
        self.assertEqual(f.read_bytes(), b"keep")
        self.assertEqual(f.stat().st_mtime_ns, mtime)

    def test_source_changed_during_conversion_is_failure(self):
        f = self.write("a.docx", b"v1")

        def mutate(p):
            f.write_bytes(b"changed")
            return "x"
        self.md.side_effect = mutate
        s = self.run_convert()
        self.assertEqual(s["failed"], 1)
        self.assertFalse((self.out / "a.docx.md").exists())

    def test_failure_logged_and_does_not_stop_others(self):
        self.write("bad.docx", b"1")
        self.write("good.docx", b"2")
        self.md.side_effect = lambda p: (_ for _ in ()).throw(cd.ConversionError("壞檔")) if p.name == "bad.docx" else "# ok\n"
        with mock.patch.object(cd, "run_pandoc", side_effect=cd.ConversionError("無 pandoc")):
            s = self.run_convert()
        self.assertEqual((s["failed"], s["new"]), (1, 1))
        self.assertIn("failed | bad.docx", (self.out / "log.md").read_text(encoding="utf-8"))

    def test_fallback_to_pandoc(self):
        self.write("a.docx", b"1")
        self.md.side_effect = cd.ConversionError("markitdown 壞了")
        with mock.patch.object(cd, "run_pandoc", return_value="# 備援\n"):
            s = self.run_convert()
        self.assertEqual(s["new"], 1)
        m, _, _ = self.fm("a.docx")
        self.assertTrue(m["converter"].startswith("pandoc"))
        self.assertTrue(any("改用 pandoc" in w for w in m["warnings"]))

    def test_lock_files_hidden_and_unsupported_skipped(self):
        self.write("~$a.docx")
        self.write(".hidden.docx")
        self.write("notes.txt")
        self.write("a.docx")
        s = self.run_convert()
        self.assertEqual(s["new"], 1)
        self.assertEqual(s["unsupported_files"], ["notes.txt"])

    def test_output_inside_source_rejected(self):
        with self.assertRaises(cd.ConversionError):
            cd.convert_tree(self.src, self.src / "out")


class TestIndexLog(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(cd, "run_markitdown", return_value="# 合約標題\n\n內文\n")
        p.start()
        self.addCleanup(p.stop)

    def test_index_and_log(self):
        self.write("a b.docx", b"1")
        self.write("c.xlsx", b"2")
        self.run_convert()
        idx = (self.out / "index.md").read_text(encoding="utf-8")
        self.assertIn("[合約標題](a%20b.docx.md)", idx)
        self.assertIn("2026-10-07", idx)
        self.assertEqual(len([ln for ln in idx.splitlines() if ln.startswith("- [")]), 2)
        log = (self.out / "log.md").read_text(encoding="utf-8")
        entries = [ln for ln in log.splitlines() if ln.startswith("## [")]
        self.assertEqual(len(entries), 2)
        self.assertRegex(entries[0], r"^## \[2026-10-07 06:00\] new \| .+ \| [0-9a-f]{12} \| markitdown")
        self.run_convert(now=T2)  # 未變：不追加
        log2 = (self.out / "log.md").read_text(encoding="utf-8")
        self.assertEqual(len([ln for ln in log2.splitlines() if ln.startswith("## [")]), 2)
        self.write("a b.docx", b"1-changed")
        self.run_convert(now=T2)
        log3 = (self.out / "log.md").read_text(encoding="utf-8")
        self.assertIn("] updated | a b.docx |", log3)


class TestPdf(Base):
    def test_page_markers_and_text_layer_detection(self):
        pdf = self.write("a.pdf", b"%PDF")
        texts = ["第一頁 " * 10, "", "第三頁 " * 10]
        with mock.patch.object(cd, "pdf_page_texts", return_value=texts), \
                mock.patch.object(cd, "pdf_single_page_bytes", side_effect=lambda p, i: bytes([i])), \
                mock.patch.object(cd, "run_markitdown_bytes", side_effect=lambda b, e: f"頁{b[0] + 1}內容"):
            self.run_convert()
        m, _, body = self.fm("a.pdf")
        self.assertEqual(m["pages"], 3)
        self.assertEqual(m["ocr"], "partial")
        self.assertEqual([ln for ln in body.splitlines() if ln.startswith("<!-- page:")],
                         ["<!-- page: 1 -->", "<!-- page: 2 -->", "<!-- page: 3 -->"])
        self.assertIn("沒有文字層", body)
        self.assertTrue(any("第 2 頁沒有文字層" in w for w in m["warnings"]))
        self.assertEqual(cd.lint_tree(self.src, self.out).count("[OCR 未完成] a.pdf.md：ocr=partial"), 1)
        del pdf

    def test_scanned_pdf_marked_required(self):
        self.write("s.pdf", b"%PDF")
        with mock.patch.object(cd, "pdf_page_texts", return_value=["", ""]):
            self.run_convert()
        m, _, body = self.fm("s.pdf")
        self.assertEqual(m["ocr"], "required")
        self.assertEqual(body.count("<!-- page:"), 2)

    def test_docling_ocr_fills_empty_pages(self):
        self.write("s.pdf", b"%PDF")
        with mock.patch.object(cd, "pdf_page_texts", return_value=["", ""]), \
                mock.patch.object(cd, "run_docling_pages", return_value=["OCR一", "OCR二"]):
            self.run_convert(ocr=cd.OcrConfig("docling"))
        m, _, body = self.fm("s.pdf")
        self.assertIs(m["ocr"], True)
        self.assertTrue(m["ocr_engine"].startswith("docling"))
        self.assertEqual(m["ocr_pages"], [1, 2])
        self.assertIn("OCR二", body)
        self.assertTrue(any("來自 OCR" in w and "對照該頁影像" in w for w in m["warnings"]))

    def test_docling_failure_keeps_required(self):
        self.write("s.pdf", b"%PDF")
        with mock.patch.object(cd, "pdf_page_texts", return_value=[""]), \
                mock.patch.object(cd, "run_docling_pages", side_effect=cd.ConversionError("未安裝 docling")):
            self.run_convert(ocr=cd.OcrConfig("docling"))
        m, _, _ = self.fm("s.pdf")
        self.assertEqual(m["ocr"], "required")
        self.assertTrue(any("OCR 失敗" in w for w in m["warnings"]))


class TestWordCom(Base):
    def test_doc_goes_through_fake_word_readonly(self):
        self.write("舊.doc", b"OLE")
        log = []
        seen = {}

        def fake_markitdown(p):
            seen["name"] = p.name
            seen["bytes"] = p.read_bytes()
            return "# 由 Word 轉出\n"
        with mock.patch.object(cd, "run_markitdown", side_effect=fake_markitdown):
            s = self.run_convert(word_factory=lambda: FakeWord(log))
        self.assertEqual(s["new"], 1)
        self.assertEqual(seen, {"name": "舊.docx", "bytes": b"PK-fake-docx"})
        self.assertIn(("Open", "舊.doc", True), log)           # ReadOnly=True
        self.assertIn(("SaveAs2", ".docx", 12), log)
        self.assertIn(("Close", 0), log)                       # 不儲存原檔
        self.assertIn(("Quit", 0), log)
        m, _, _ = self.fm("舊.doc")
        self.assertTrue(m["converter"].startswith("word-com → markitdown"))
        self.assertEqual(sum(1 for x in log if x[0] == "Open"), 1)

    def test_doc_without_word_fails_cleanly(self):
        self.write("舊.doc", b"OLE")
        with mock.patch.dict(sys.modules, {"win32com": None, "win32com.client": None}):
            s = self.run_convert()
        self.assertEqual(s["failed"], 1)
        self.assertIn("pywin32", (self.out / "log.md").read_text(encoding="utf-8"))

    def test_docx_via_word_option(self):
        self.write("a.docx", b"PK")
        log = []
        with mock.patch.object(cd, "run_markitdown", return_value="# t\n"):
            self.run_convert(word_factory=lambda: FakeWord(log), docx_via_word=True)
        self.assertTrue(any(x[0] == "Open" for x in log))

    def test_word_not_started_when_no_doc_files(self):
        self.write("a.docx", b"PK")
        log = []
        with mock.patch.object(cd, "run_markitdown", return_value="# t\n"):
            self.run_convert(word_factory=lambda: FakeWord(log))
        self.assertEqual(log, [])


class TestLint(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(cd, "run_markitdown", return_value="# t\n")
        p.start()
        self.addCleanup(p.stop)

    def test_clean_state_has_only_hints(self):
        self.write("a.docx", b"1")
        self.run_convert()
        self.assertTrue(all(i.startswith("[提示]") for i in cd.lint_tree(self.src, self.out)))

    def test_detects_changed_missing_orphan_and_missing_keys(self):
        a = self.write("a.docx", b"1")
        self.write("b.docx", b"2")
        self.run_convert()
        a.write_bytes(b"1-new")                       # 原檔已變
        self.write("c.docx", b"3")                    # 未轉換
        (self.src / "b.docx").unlink()                # 原檔消失 -> 孤兒
        p = self.out / "a.docx.md"
        p.write_text(p.read_text(encoding="utf-8").replace("title:", "xtitle:", 1), encoding="utf-8")
        issues = "\n".join(cd.lint_tree(self.src, self.out))
        self.assertIn("[過期] a.docx.md", issues)
        self.assertIn("[孤兒頁] b.docx.md", issues)
        self.assertIn("[未轉換] 原檔 c.docx", issues)
        self.assertIn("[metadata 缺欄] a.docx.md：title", issues)

    def test_detects_page_marker_mismatch_and_index_drift(self):
        self.write("a.docx", b"1")
        self.run_convert()
        p = self.out / "a.docx.md"
        p.write_text(p.read_text(encoding="utf-8").replace("pages:\n", "pages: 2\n"), encoding="utf-8")
        (self.out / "index.md").write_text("# 文件索引\n", encoding="utf-8")
        issues = "\n".join(cd.lint_tree(self.src, self.out))
        self.assertIn("[頁碼標記] a.docx.md", issues)
        self.assertIn("[索引] a.docx.md 不在 index.md", issues)


class TestExistingOcr(Base):
    def setUp(self):
        super().setUp()
        self.ocr = self.root / "ocr"
        self.ocr.mkdir()
        self.write("s.pdf", b"%PDF")

    def cfg(self, name="ABBYY FineReader"):
        return cd.OcrConfig("existing-text", self.ocr, name)

    def run_pdf(self, **kw):
        with mock.patch.object(cd, "pdf_page_texts", return_value=["", ""]):
            return self.run_convert(ocr=self.cfg(), **kw)

    def test_sidecar_txt_with_formfeed_pages(self):
        (self.ocr / "s.txt").write_text("甲方 OCR\f乙方 OCR\f", encoding="utf-8")
        s = self.run_pdf()
        self.assertEqual(s["new"], 1)
        m, _, body = self.fm("s.pdf")
        self.assertIs(m["ocr"], True)
        self.assertEqual(m["ocr_engine"], "ABBYY FineReader")
        self.assertEqual(m["ocr_pages"], [1, 2])
        self.assertEqual(m["ocr_source"], "s.txt")
        self.assertRegex(body, r"<!-- page: 2 -->\s+乙方 OCR")
        self.assertTrue(any("對照該頁影像" in w for w in m["warnings"]))

    def test_page_count_mismatch_fails_instead_of_misaligning(self):
        (self.ocr / "s.pdf.txt").write_text("只有一頁沒有換頁字元", encoding="utf-8")
        s = self.run_pdf()
        self.assertEqual(s["failed"], 1)
        self.assertFalse((self.out / "s.pdf.md").exists())

    def test_missing_ocr_output_stays_required(self):
        s = self.run_pdf()
        self.assertEqual(s["new"], 1)
        m, _, _ = self.fm("s.pdf")
        self.assertEqual(m["ocr"], "required")
        self.assertTrue(any("找不到對應檔" in w for w in m["warnings"]))

    def test_text_layer_pdf_from_existing_tool(self):
        (self.ocr / "s.pdf").write_bytes(b"%PDF-ocr")
        orig = cd.pdf_page_texts
        with mock.patch.object(cd, "pdf_page_texts", side_effect=lambda p: ["", ""] if p.parent == self.src else ["t" * 30, "u" * 30]), \
                mock.patch.object(cd, "pdf_single_page_bytes", side_effect=lambda p, i: bytes([i])), \
                mock.patch.object(cd, "run_markitdown_bytes", side_effect=lambda b, e: f"OCR頁{b[0] + 1}"):
            self.run_convert(ocr=self.cfg())
        m, _, body = self.fm("s.pdf")
        self.assertIs(m["ocr"], True)
        self.assertIn("OCR頁2", body)
        del orig

    def test_reconvert_when_ocr_output_appears_or_changes(self):
        s = self.run_pdf()
        self.assertEqual(s["new"], 1)
        s = self.run_pdf(now=T2)
        self.assertEqual(s["unchanged"], 1)       # 沒有 OCR 輸出可用，不重複轉換
        (self.ocr / "s.txt").write_text("a\fb", encoding="utf-8")
        s = self.run_pdf(now=T2)
        self.assertEqual(s["updated"], 1)
        s = self.run_pdf(now=T2)
        self.assertEqual(s["unchanged"], 1)
        (self.ocr / "s.txt").write_text("a2\fb", encoding="utf-8")
        s = self.run_pdf(now=T2)
        self.assertEqual(s["updated"], 1)

    def test_requires_ocr_dir(self):
        with self.assertRaises(cd.ConversionError):
            cd.convert_tree(self.src, self.out, ocr=cd.OcrConfig("existing-text"))

    def test_docling_device_passed_through(self):
        with mock.patch.object(cd, "pdf_page_texts", return_value=[""]), \
                mock.patch.object(cd, "run_docling_pages", return_value=["x"]) as r:
            self.run_convert(ocr=cd.OcrConfig("docling", device="cuda"))
        self.assertEqual(r.call_args[0][2].device, "cuda")
        m, _, _ = self.fm("s.pdf")
        self.assertIn("(cuda)", m["ocr_engine"])


class TestDocxWarnings(Base):
    def test_tracked_changes_comments_header(self):
        import zipfile
        p = self.src / "t.docx"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("word/document.xml", "<w:document><w:ins w:id='1'><w:r/></w:ins></w:document>")
            z.writestr("word/comments.xml", "<w:comments/>")
            z.writestr("word/header1.xml", "<w:hdr><w:p><w:r><w:t>機密</w:t></w:r></w:p></w:hdr>")
            z.writestr("word/footer1.xml", "<w:ftr><w:p/></w:ftr>")
        w = "\n".join(cd.docx_warnings(p))
        self.assertIn("追蹤修訂", w)
        self.assertIn("註解", w)
        self.assertIn("頁首或頁尾", w)
        self.assertEqual(cd.docx_warnings(self.src / "missing.docx"), [])


def _real_deps():
    try:
        import markitdown  # noqa: F401
        import pdfplumber  # noqa: F401
        import pypdfium2  # noqa: F401
        import docx  # noqa: F401
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_real_deps(), "未安裝 markitdown / python-docx / reportlab，略過整合測試")
class TestRealConversion(Base):
    def test_real_docx_and_pdf(self):
        import docx
        from reportlab.pdfgen import canvas
        d = docx.Document()
        d.add_heading("測試合約", 1)
        d.add_paragraph("第一條 付款期限為三十日。")
        d.save(str(self.src / "a.docx"))
        c = canvas.Canvas(str(self.src / "b.pdf"))
        c.drawString(72, 750, "Page one: payment within 30 days of invoice.")
        c.showPage()
        c.drawString(72, 750, "Page two: termination with 60 days notice.")
        c.showPage()
        c.save()
        s = self.run_convert()
        self.assertEqual((s["new"], s["failed"]), (2, 0))
        m, _, body = self.fm("a.docx")
        self.assertEqual(m["title"], "測試合約")
        self.assertIn("第一條 付款期限為三十日。", body)
        m, _, body = self.fm("b.pdf")
        self.assertEqual(m["pages"], 2)
        self.assertIs(m["ocr"], False)
        self.assertRegex(body, r"<!-- page: 1 -->\s+Page one: payment")
        self.assertRegex(body, r"<!-- page: 2 -->\s+Page two: termination")
        self.assertEqual([i for i in cd.lint_tree(self.src, self.out) if not i.startswith("[提示]")], [])


if __name__ == "__main__":
    unittest.main()
