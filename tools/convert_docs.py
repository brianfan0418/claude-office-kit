#!/usr/bin/env python3
"""convert_docs.py - 把資料夾中的 Word、PDF、Excel、PowerPoint 轉成帶 metadata 的 Markdown。

用法：python convert_docs.py 原檔資料夾 [-o 輸出資料夾]   轉換（增量）
  python convert_docs.py 原檔資料夾 [-o 輸出資料夾] --lint  檢查衍生檔與原檔是否一致（不轉換）

原則
  - 原檔只讀不改：以唯讀方式開啟，轉換前後各算一次 sha256，不一致即視為失敗。
  - 不自己寫解析器：.docx/.xlsx/.pptx/.pdf 交給 Microsoft MarkItDown，pandoc 為 .docx 備援；
    .doc/.rtf 以 Word COM（pywin32）另存成暫存 .docx 後再轉；掃描型 PDF 標記 ocr: required，
    以 --ocr-backend 選擇 docling 本機 OCR，或沿用既有 OCR 工具的輸出（existing-text）。
  - 增量：以來源檔 sha256 判斷；沒變就跳過；變了就重轉並把舊 Markdown 存進 _history/。
  - 每份 Markdown 開頭是 YAML frontmatter；「業務欄位」區由各領域 skill 填寫，重轉時原樣保留。

輸出
  <輸出資料夾>/<原檔相對路徑>.md   例：合約/甲.docx -> 合約/甲.docx.md
  <輸出資料夾>/index.md            每次執行後由全部 .md 的 frontmatter 重新產生
  <輸出資料夾>/log.md              每次轉換追加一行
  <輸出資料夾>/_history/           被取代的舊版 Markdown
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

# 以 Word COM 先轉成 .docx 的格式
WORD_EXTS = {".doc", ".rtf"}
# 直接交給 MarkItDown 的格式
MARKITDOWN_EXTS = {".docx", ".xlsx", ".xls", ".pptx", ".pdf"}
SUPPORTED_EXTS = WORD_EXTS | MARKITDOWN_EXTS

# 由本工具產生與更新的欄位（單行、JSON 風格的值）。順序即寫出順序。
MANAGED_KEYS = [
    "source_path", "source_sha256", "source_modified", "converter",
    "converted_at", "pages", "ocr", "ocr_engine", "ocr_pages", "ocr_source", "ocr_source_sha256",
    "title", "warnings", "needs_review",
]
# 業務欄位預設值，由各領域 skill 填寫；本工具只在首次轉換時寫入空白。
BUSINESS_KEYS = ["doc_type", "parties", "effective_date", "expiry_date", "status", "tags"]
BUSINESS_MARKER = "# --- 業務欄位：由各領域 skill 填寫，重新轉換時原樣保留 ---"

# 單頁抽出的文字少於此字數，視為該頁沒有文字層
MIN_TEXT_CHARS_PER_PAGE = 20

# frontmatter 的 ocr 欄位：false＝本文來自文字層；required／partial＝需要 OCR 但尚未完成；
# true＝至少一頁的文字來自 OCR（不是逐字原文，引用關鍵欄位須對照頁面影像）
OCR_NOT_NEEDED, OCR_REQUIRED, OCR_PARTIAL, OCR_DONE = False, "required", "partial", True
OCR_BACKENDS = ["none", "docling", "existing-text"]


@dataclass
class OcrConfig:
    backend: str = "none"            # none｜docling｜existing-text
    ocr_dir: Path | None = None      # existing-text：使用者既有 OCR 工具的輸出資料夾
    engine_name: str = ""            # existing-text：既有 OCR 工具名稱，記入 ocr_engine
    device: str = "auto"             # docling：auto｜cuda｜cpu
    lang: list[str] | None = None    # docling：OCR 語言（依 docling 官方說明為 BCP-47 標籤）


class ConversionError(Exception):
    pass


# ---------------------------------------------------------------- 工具函式

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def iso_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat()


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def pkg_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "未安裝"


# ---------------------------------------------------------------- frontmatter

def dump_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None or v == "":
        return ""
    if isinstance(v, int):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


def build_frontmatter(managed: dict, business_tail: list[str] | None = None) -> str:
    lines = ["---"]
    for k in MANAGED_KEYS:
        v = dump_value(managed.get(k))
        lines.append(f"{k}: {v}" if v != "" else f"{k}:")
    lines.append(BUSINESS_MARKER)
    if business_tail is None:
        business_tail = [f"{k}:" for k in BUSINESS_KEYS]
    lines.extend(business_tail)
    lines.append("---")
    return "\n".join(lines) + "\n"


def split_frontmatter(text: str):
    """回傳 (frontmatter 各行, 本文)；沒有 frontmatter 時回傳 ([], text)。"""
    if not text.startswith("---\n"):
        return [], text
    end = text.find("\n---\n", 4)
    if end == -1:
        return [], text
    return text[4:end].split("\n"), text[end + 5:]


def parse_managed(fm_lines: list[str]) -> dict:
    """只解析本工具寫出的單行欄位；其餘（業務欄位）不解析。"""
    out: dict = {}
    for line in fm_lines:
        if line.startswith(BUSINESS_MARKER):
            break
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m or m.group(1) not in MANAGED_KEYS:
            continue
        raw = m.group(2).strip()
        if raw == "":
            out[m.group(1)] = ""
            continue
        try:
            out[m.group(1)] = json.loads(raw)
        except ValueError:
            out[m.group(1)] = raw
    return out


def business_tail(fm_lines: list[str]) -> list[str] | None:
    for i, line in enumerate(fm_lines):
        if line.startswith(BUSINESS_MARKER):
            return fm_lines[i + 1:]
    return None


def read_md(path: Path):
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    return fm, body


# ---------------------------------------------------------------- Word COM

class WordSession:
    """以 Word COM 把 .doc/.rtf 轉成暫存 .docx。原檔以 ReadOnly=True 開啟，不儲存。

    word_factory 可注入假物件供測試；預設才匯入 pywin32（僅 Windows）。
    """

    def __init__(self, word_factory=None):
        self._factory = word_factory
        self._app = None

    def _start(self):
        if self._app is not None:
            return self._app
        if self._factory is None:
            try:
                import win32com.client  # type: ignore
            except ImportError as e:
                raise ConversionError("需要 pywin32 與 Windows 上的 Microsoft Word 才能轉換此格式") from e
            self._factory = lambda: win32com.client.DispatchEx("Word.Application")
        app = self._factory()
        app.Visible = False
        app.DisplayAlerts = 0          # wdAlertsNone
        app.AutomationSecurity = 3     # msoAutomationSecurityForceDisable：停用巨集
        self._app = app
        return app

    def to_docx(self, src: Path, dst: Path) -> None:
        app = self._start()
        doc = app.Documents.Open(
            FileName=str(src), ReadOnly=True, AddToRecentFiles=False, ConfirmConversions=False,
        )
        try:
            doc.SaveAs2(FileName=str(dst), FileFormat=12)  # wdFormatXMLDocument (.docx)
        finally:
            doc.Close(SaveChanges=0)  # wdDoNotSaveChanges

    def close(self):
        if self._app is not None:
            try:
                self._app.Quit(SaveChanges=0)
            finally:
                self._app = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ---------------------------------------------------------------- 各格式轉換

def run_markitdown(path: Path) -> str:
    try:
        from markitdown import MarkItDown
    except ImportError as e:
        raise ConversionError("未安裝 markitdown（pip install \"markitdown[docx,pdf,xlsx,xls,pptx]\"）") from e
    return MarkItDown().convert(str(path)).markdown


def run_markitdown_bytes(data: bytes, ext: str) -> str:
    from markitdown import MarkItDown, StreamInfo
    return MarkItDown().convert_stream(io.BytesIO(data), stream_info=StreamInfo(extension=ext)).markdown


def run_pandoc(path: Path) -> str:
    exe = shutil.which("pandoc")
    if not exe:
        raise ConversionError("找不到 pandoc")
    r = subprocess.run(
        [exe, "-f", "docx", "-t", "gfm", "--wrap=none", str(path)],
        capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0:
        raise ConversionError(f"pandoc 失敗：{r.stderr.strip()[:300]}")
    return r.stdout


def pandoc_version() -> str:
    exe = shutil.which("pandoc")
    if not exe:
        return "未安裝"
    r = subprocess.run([exe, "--version"], capture_output=True, text=True)
    return r.stdout.splitlines()[0].replace("pandoc", "").strip() if r.stdout else "未知"


def docx_warnings(path: Path) -> list[str]:
    """檢查 .docx 內 Markdown 轉換可能漏掉的內容，供使用者回原檔核對。"""
    warns = []
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            doc = z.read("word/document.xml").decode("utf-8", "ignore") if "word/document.xml" in names else ""
            hf_text = any(
                re.search(r"<w:t[ >]", z.read(n).decode("utf-8", "ignore"))
                for n in names if re.match(r"word/(header|footer)\d*\.xml$", n)
            )
    except (zipfile.BadZipFile, OSError):
        return warns
    if "<w:ins " in doc or "<w:del " in doc:
        warns.append("含追蹤修訂：以 markitdown 0.1.8 實測，轉換結果含已插入的文字、不含已刪除的文字，請回原檔核對修訂")
    if "word/comments.xml" in names:
        warns.append("含註解（comments），轉換結果不含註解，請回原檔核對")
    if hf_text:
        warns.append("頁首或頁尾有文字，轉換結果不含（以 markitdown 0.1.8 實測），請回原檔核對")
    if "<w:txbxContent" in doc:
        warns.append("含文字方塊，可能未被轉出，請回原檔核對")
    return warns


def pdf_page_texts(path: Path) -> list[str]:
    """以 pdfplumber（MarkItDown 的 PDF 依賴）逐頁取純文字，用來判斷有無文字層。"""
    try:
        import pdfplumber  # type: ignore
    except ImportError as e:
        raise ConversionError("未安裝 pdfplumber（隨 markitdown[pdf] 安裝）") from e
    texts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            texts.append((page.extract_text() or "").strip())
    return texts


def pdf_single_page_bytes(path: Path, index: int) -> bytes:
    import pypdfium2 as pdfium  # type: ignore  # pdfplumber 的依賴
    src = pdfium.PdfDocument(str(path))
    try:
        dst = pdfium.PdfDocument.new()
        dst.import_pages(src, [index])
        buf = io.BytesIO()
        dst.save(buf)
        return buf.getvalue()
    finally:
        src.close()


def run_docling_pages(path: Path, n_pages: int, cfg: OcrConfig) -> list[str]:
    """以 docling 取得逐頁 Markdown。未實測：依 docling 官方 GPU 文件與範例撰寫。"""
    try:
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions  # type: ignore
        from docling.datamodel.base_models import InputFormat  # type: ignore
        from docling.datamodel.pipeline_options import PdfPipelineOptions  # type: ignore
        from docling.document_converter import DocumentConverter, PdfFormatOption  # type: ignore
    except ImportError as e:
        raise ConversionError("未安裝 docling（pip install docling）") from e
    opts = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=getattr(AcceleratorDevice, cfg.device.upper())))
    opts.do_ocr = True
    if cfg.lang:
        opts.ocr_options.lang = cfg.lang
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    doc = conv.convert(str(path)).document
    return [doc.export_to_markdown(page_no=i + 1) for i in range(n_pages)]


def find_existing_ocr(cfg: OcrConfig, rel: str) -> Path | None:
    """在既有 OCR 輸出資料夾找對應檔：同相對路徑的 PDF，或同名 .txt／.pdf.txt。"""
    if cfg.backend != "existing-text" or cfg.ocr_dir is None:
        return None
    base = cfg.ocr_dir / rel
    for cand in (base, base.with_suffix(".txt"), Path(str(base) + ".txt")):
        if cand.is_file():
            return cand
    return None


def existing_ocr_pages(cand: Path, n_pages: int) -> list[str]:
    """讀取既有 OCR 輸出，回傳與原 PDF 等長的逐頁文字；頁數對不上就拒絕，避免頁碼錯位。"""
    if cand.suffix.lower() == ".pdf":
        texts = pdf_page_texts(cand)
        if len(texts) != n_pages:
            raise ConversionError(f"既有 OCR 的 PDF 頁數（{len(texts)}）與原檔（{n_pages}）不符：{cand.name}")
        return [run_markitdown_bytes(pdf_single_page_bytes(cand, i), ".pdf").strip() for i in range(n_pages)]
    chunks = cand.read_text(encoding="utf-8").split("\f")
    if chunks and not chunks[-1].strip():
        chunks.pop()  # 換頁字元結尾造成的空尾段
    if len(chunks) != n_pages:
        raise ConversionError(
            f"既有 OCR 文字檔以換頁字元分出 {len(chunks)} 頁，與原檔 {n_pages} 頁不符：{cand.name}")
    return [c.strip() for c in chunks]


@dataclass
class Converted:
    body: str
    converter: str
    pages: int | None = None
    ocr: object = OCR_NOT_NEEDED
    warnings: list[str] = field(default_factory=list)
    ocr_engine: str = ""
    ocr_pages: list[int] = field(default_factory=list)
    ocr_source: str = ""
    ocr_source_sha256: str = ""


def convert_pdf(path: Path, rel: str, cfg: OcrConfig) -> Converted:
    texts = pdf_page_texts(path)
    n = len(texts)
    empty = [i for i, t in enumerate(texts) if len(t) < MIN_TEXT_CHARS_PER_PAGE]
    warns: list[str] = []
    ocr: object = OCR_NOT_NEEDED
    if empty:
        ocr = OCR_REQUIRED if len(empty) == n else OCR_PARTIAL
    conv_name = f"markitdown {pkg_version('markitdown')}"
    ocr_pages: dict[int, str] = {}
    engine = src_rel = src_sha = ""
    if empty and cfg.backend == "docling":
        try:
            md_pages = run_docling_pages(path, n, cfg)
            ocr_pages = {i: md_pages[i] for i in empty}
            engine = f"docling {pkg_version('docling')} ({cfg.device})"
            conv_name += f" + docling {pkg_version('docling')}"
        except Exception as e:  # noqa: BLE001 - 任何 OCR 失敗都保留 required 並記錄
            warns.append(f"OCR 失敗，仍待處理：{e}")
    elif empty and cfg.backend == "existing-text":
        cand = find_existing_ocr(cfg, rel)
        if cand is None:
            warns.append("既有 OCR 輸出資料夾內找不到對應檔，仍待處理")
        else:
            pages = existing_ocr_pages(cand, n)  # 頁數不符會丟 ConversionError，整份轉換失敗
            ocr_pages = {i: pages[i] for i in empty}
            engine = cfg.engine_name or "未指明（既有 OCR 輸出）"
            src_rel = cand.relative_to(cfg.ocr_dir).as_posix()
            src_sha = sha256_of(cand)
    if ocr_pages:
        ocr = OCR_DONE
        warns.append("第 %s 頁文字來自 OCR，不是逐字原文；金額、日期、當事人、期間、通知天數等關鍵欄位須對照該頁影像確認"
                     % ",".join(str(i + 1) for i in sorted(ocr_pages)))
        still = [i for i in empty if i not in ocr_pages]
        if still:
            ocr = OCR_PARTIAL
    parts = []
    for i in range(n):
        parts.append(f"<!-- page: {i + 1} -->")
        if i in ocr_pages:
            parts.append(ocr_pages[i].strip())
        elif i in empty:
            parts.append("> 本頁沒有文字層，未轉出內容（需要 OCR），請回原檔閱讀。")
        else:
            parts.append(run_markitdown_bytes(pdf_single_page_bytes(path, i), ".pdf").strip())
    if ocr == OCR_PARTIAL:
        warns.append("第 %s 頁沒有文字層且尚未 OCR" % ",".join(str(i + 1) for i in empty if i not in ocr_pages))
    if ocr == OCR_REQUIRED:
        warns.append("整份沒有文字層（掃描檔），需要 OCR")
    if n and ocr == OCR_NOT_NEEDED:
        warns.append("若此 PDF 由掃描檔經 OCR 軟體加上文字層，文字可能有辨識錯誤，金額、日期、條號須回原文核對")
    return Converted("\n\n".join(parts) + "\n", conv_name, n, ocr, warns, engine,
                     sorted(i + 1 for i in ocr_pages), src_rel, src_sha)


def convert_office(path: Path, engine: str, word: WordSession | None, docx_via_word: bool) -> Converted:
    """處理 .doc/.rtf/.docx/.xlsx/.xls/.pptx。"""
    ext = path.suffix.lower()
    tmpdir = None
    work = path
    prefix = ""
    warns: list[str] = []
    try:
        if ext in WORD_EXTS or (ext == ".docx" and docx_via_word):
            if word is None:
                raise ConversionError("此格式需要 Word COM")
            tmpdir = Path(tempfile.mkdtemp(prefix="convdocs_"))
            work = tmpdir / (path.stem + ".docx")
            word.to_docx(path, work)
            if not work.exists():
                raise ConversionError("Word 未產生 .docx")
            prefix = "word-com → "
            ext = ".docx"
        if ext == ".docx":
            warns += docx_warnings(work)
        order = [engine, "pandoc" if engine == "markitdown" else "markitdown"]
        errors = []
        for eng in order:
            if eng == "pandoc" and ext != ".docx":
                continue
            try:
                if eng == "markitdown":
                    body, name = run_markitdown(work), f"markitdown {pkg_version('markitdown')}"
                else:
                    body, name = run_pandoc(work), f"pandoc {pandoc_version()}"
                if errors:
                    warns.append(f"預設工具失敗，改用 {eng}：{errors[0]}")
                return Converted(body.rstrip() + "\n", prefix + name, None, OCR_NOT_NEEDED, warns)
            except ConversionError as e:
                errors.append(str(e))
            except Exception as e:  # noqa: BLE001
                errors.append(f"{eng}: {e}")
        raise ConversionError("；".join(errors))
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def guess_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        m = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if m:
            return m.group(1).strip()
    return fallback


# ---------------------------------------------------------------- 主流程

def scan_sources(src_dir: Path, out_dir: Path):
    supported, skipped = [], []
    for p in sorted(src_dir.rglob("*")):
        if not p.is_file() or p.name.startswith(("~$", ".")):
            continue
        try:
            p.relative_to(out_dir)
            continue
        except ValueError:
            pass
        (supported if p.suffix.lower() in SUPPORTED_EXTS else skipped).append(p)
    return supported, skipped


def append_log(out_dir: Path, now: datetime, action: str, rel: str, sha: str, converter: str, note: str = ""):
    log = out_dir / "log.md"
    if not log.exists():
        log.write_text("# 轉換紀錄\n\n", encoding="utf-8")
    line = f"## [{now.strftime('%Y-%m-%d %H:%M')}] {action} | {rel} | {sha[:12]} | {converter}"
    if note:
        line += f" | {note}"
    with open(log, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def convert_one(src: Path, rel: str, out_dir: Path, *, engine, ocr: OcrConfig, word, docx_via_word,
                force, now) -> str:
    """回傳 new / updated / unchanged / failed。"""
    sha_before = sha256_of(src)
    out_path = out_dir / (rel + ".md")
    old_fm: list[str] = []
    old_text = None
    if out_path.exists():
        old_text = out_path.read_text(encoding="utf-8")
        old_fm, _ = split_frontmatter(old_text)
        old_m = parse_managed(old_fm)
        is_pdf = src.suffix.lower() == ".pdf"
        cand = find_existing_ocr(ocr, rel) if is_pdf else None
        cand_sha = sha256_of(cand) if cand else ""
        ocr_pending = (old_m.get("ocr") in (OCR_REQUIRED, OCR_PARTIAL)
                       and (ocr.backend == "docling" or (ocr.backend == "existing-text" and cand is not None)))
        ocr_input_changed = ocr.backend == "existing-text" and (old_m.get("ocr_source_sha256") or "") != cand_sha
        if old_m.get("source_sha256") == sha_before and not force and not ocr_pending and not ocr_input_changed:
            return "unchanged"
    try:
        if src.suffix.lower() == ".pdf":
            res = convert_pdf(src, rel, ocr)
        else:
            res = convert_office(src, engine, word, docx_via_word)
        if sha256_of(src) != sha_before:
            raise ConversionError("轉換期間原檔內容改變（sha256 前後不一致），結果作廢")
    except Exception as e:  # noqa: BLE001
        append_log(out_dir, now, "failed", rel, sha_before, "-", str(e).replace("\n", " ")[:300])
        print(f"  失敗：{rel}：{e}", file=sys.stderr)
        return "failed"

    action = "new"
    tail = business_tail(old_fm)
    needs_review = False
    if old_text is not None:
        action = "updated"
        hist = out_dir / "_history" / (rel + ".md").replace("\\", "/")
        old_sha = parse_managed(old_fm).get("source_sha256", "") or "unknown"
        hist_file = hist.parent / f"{hist.name}.{now.strftime('%Y%m%dT%H%M%S')}.{str(old_sha)[:8]}.md"
        hist_file.parent.mkdir(parents=True, exist_ok=True)
        hist_file.write_text(old_text, encoding="utf-8")
        # 原檔已變，沿用的業務欄位可能過時，標記待人工複核
        needs_review = bool(tail and any(re.match(r"^[A-Za-z0-9_]+:\s*\S", ln) for ln in tail))

    managed = {
        "source_path": rel,
        "source_sha256": sha_before,
        "source_modified": iso_utc(src.stat().st_mtime),
        "converter": res.converter,
        "converted_at": now.isoformat(),
        "pages": res.pages,
        "ocr": res.ocr,
        "ocr_engine": res.ocr_engine,
        "ocr_pages": res.ocr_pages,
        "ocr_source": res.ocr_source,
        "ocr_source_sha256": res.ocr_source_sha256,
        "title": guess_title(res.body, Path(rel).stem),
        "warnings": res.warnings,
        "needs_review": needs_review,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_frontmatter(managed, tail) + "\n" + res.body, encoding="utf-8")
    append_log(out_dir, now, action, rel, sha_before, res.converter,
               f"ocr={dump_value(res.ocr)} {res.ocr_engine}".strip() if res.ocr != OCR_NOT_NEEDED else "")
    return action


def collect_md(out_dir: Path):
    for p in sorted(out_dir.rglob("*.md")):
        rel = p.relative_to(out_dir)
        if rel.parts[0] == "_history" or rel.as_posix() in ("index.md", "log.md"):
            continue
        yield p, rel.as_posix()


def write_index(out_dir: Path) -> int:
    rows = []
    for p, rel in collect_md(out_dir):
        fm, _ = read_md(p)
        m = parse_managed(fm)
        title = (m.get("title") or Path(rel).stem).replace("|", "/")
        converted = str(m.get("converted_at", ""))[:10]
        pages = m.get("pages", "")
        rows.append(f"- [{title}]({rel.replace(' ', '%20')}) | 頁數 {pages if pages != '' else '未知'} | "
                    f"轉換 {converted} | OCR {dump_value(m.get('ocr', '')) or '未知'}{(' ' + m['ocr_engine']) if m.get('ocr_engine') else ''} | 原檔 {m.get('source_path', '')}")
    (out_dir / "index.md").write_text(
        "# 文件索引\n\n本檔由 convert_docs.py 依各 Markdown 的 frontmatter 重新產生，請勿手動修改。\n\n"
        + "\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return len(rows)


def convert_tree(src_dir: Path, out_dir: Path, *, engine="markitdown", ocr: OcrConfig | None = None,
                 docx_via_word=False, force=False, word_factory=None, now=None) -> dict:
    src_dir, out_dir = src_dir.resolve(), out_dir.resolve()
    if not src_dir.is_dir():
        raise ConversionError(f"找不到原檔資料夾：{src_dir}")
    if out_dir == src_dir or src_dir in out_dir.parents:
        raise ConversionError("輸出資料夾不可位於原檔資料夾內，避免污染原始文件")
    out_dir.mkdir(parents=True, exist_ok=True)
    now = now or now_utc()
    ocr = ocr or OcrConfig()
    if ocr.backend == "existing-text" and (ocr.ocr_dir is None or not ocr.ocr_dir.is_dir()):
        raise ConversionError("--ocr-backend existing-text 需要以 --ocr-dir 指定既有 OCR 輸出資料夾")
    files, skipped = scan_sources(src_dir, out_dir)
    stats = {"new": 0, "updated": 0, "unchanged": 0, "failed": 0, "unsupported": len(skipped)}
    with WordSession(word_factory) as word:
        for p in files:
            rel = p.relative_to(src_dir).as_posix()
            res = convert_one(p, rel, out_dir, engine=engine, ocr=ocr, word=word,
                              docx_via_word=docx_via_word, force=force, now=now)
            stats[res] += 1
    stats["indexed"] = write_index(out_dir)
    stats["unsupported_files"] = [p.relative_to(src_dir).as_posix() for p in skipped]
    return stats


# ---------------------------------------------------------------- lint（機械檢查）

def lint_tree(src_dir: Path, out_dir: Path) -> list[str]:
    """回傳問題清單（空表示通過）。矛盾與語意檢查不在此處，由 skill 的流程處理。"""
    src_dir, out_dir = src_dir.resolve(), out_dir.resolve()
    issues: list[str] = []
    files, _ = scan_sources(src_dir, out_dir)
    src_rel = {p.relative_to(src_dir).as_posix(): p for p in files}
    seen = set()
    for p, rel in collect_md(out_dir):
        fm, body = read_md(p)
        m = parse_managed(fm)
        missing = [k for k in MANAGED_KEYS if k not in m]
        if missing:
            issues.append(f"[metadata 缺欄] {rel}：{', '.join(missing)}")
        if business_tail(fm) is None:
            issues.append(f"[metadata 缺欄] {rel}：缺少業務欄位區")
        sp = m.get("source_path")
        if not sp:
            continue
        seen.add(sp)
        if sp not in src_rel:
            issues.append(f"[孤兒頁] {rel}：原檔 {sp} 已不存在")
            continue
        if sha256_of(src_rel[sp]) != m.get("source_sha256"):
            issues.append(f"[過期] {rel}：原檔 {sp} 已變更，衍生檔未更新")
        if m.get("ocr") in (OCR_REQUIRED, OCR_PARTIAL):
            issues.append(f"[OCR 未完成] {rel}：ocr={m.get('ocr')}")
        if m.get("needs_review") is True:
            issues.append(f"[待複核] {rel}：原檔更新後業務欄位尚未複核")
        pages = m.get("pages")
        if isinstance(pages, int):
            n_markers = len(re.findall(r"^<!-- page: \d+ -->$", body, flags=re.M))
            if n_markers != pages:
                issues.append(f"[頁碼標記] {rel}：frontmatter pages={pages}，實際標記 {n_markers}")
        blanks = [ln.split(":")[0] for ln in (business_tail(fm) or [])
                  if re.match(r"^[A-Za-z0-9_]+:\s*$", ln)]
        if blanks:
            issues.append(f"[提示] {rel}：業務欄位未填：{', '.join(blanks)}")
    for rel, _ in src_rel.items():
        if rel not in seen:
            issues.append(f"[未轉換] 原檔 {rel} 沒有對應的衍生檔")
    idx = out_dir / "index.md"
    if idx.exists():
        listed = set(re.findall(r"\]\(([^)]+)\)", idx.read_text(encoding="utf-8")))
        actual = {rel.replace(" ", "%20") for _, rel in collect_md(out_dir)}
        for x in sorted(actual - listed):
            issues.append(f"[索引] {x} 不在 index.md（請重新執行轉換以重建）")
        for x in sorted(listed - actual):
            issues.append(f"[索引] index.md 列出的 {x} 不存在")
    elif seen:
        issues.append("[索引] 缺少 index.md")
    return issues


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="把 Word/PDF/Excel/PowerPoint 轉成帶 metadata 的 Markdown（原檔唯讀）")
    ap.add_argument("source", type=Path, help="原檔資料夾")
    ap.add_argument("-o", "--out", type=Path, help="輸出資料夾（預設：原檔資料夾旁的「<名稱>-md」）")
    ap.add_argument("--engine", choices=["markitdown", "pandoc"], default="markitdown",
                    help="預設轉換工具；失敗時自動改用另一個（pandoc 僅 .docx）")
    ap.add_argument("--docx-via-word", action="store_true", help=".docx 也先經 Word COM 另存再轉")
    ap.add_argument("--ocr-backend", choices=OCR_BACKENDS, default="none",
                    help="無文字層的 PDF 頁面如何取得文字：none＝只標記 ocr: required（預設）；"
                         "docling＝本機 OCR；existing-text＝沿用使用者既有 OCR 工具的輸出（需 --ocr-dir）")
    ap.add_argument("--ocr-dir", type=Path, help="existing-text：既有 OCR 輸出資料夾，結構與原檔資料夾相同")
    ap.add_argument("--ocr-engine-name", default="", help="existing-text：既有 OCR 工具名稱，記入 frontmatter ocr_engine")
    ap.add_argument("--ocr-device", choices=["auto", "cuda", "cpu"], default="auto", help="docling 使用的裝置")
    ap.add_argument("--ocr-lang", nargs="+", help="docling 的 OCR 語言標籤（未實測中文標籤）")
    ap.add_argument("--force", action="store_true", help="忽略 sha256，全部重轉")
    ap.add_argument("--lint", action="store_true", help="只檢查衍生檔與原檔是否一致，不轉換")
    a = ap.parse_args(argv)
    src = a.source.resolve()
    out = (a.out or src.parent / (src.name + "-md")).resolve()
    try:
        if a.lint:
            issues = lint_tree(src, out)
            print("\n".join(issues) if issues else "通過：未發現問題")
            return 1 if any(not i.startswith("[提示]") for i in issues) else 0
        ocr = OcrConfig(a.ocr_backend, a.ocr_dir.resolve() if a.ocr_dir else None,
                        a.ocr_engine_name, a.ocr_device, a.ocr_lang)
        stats = convert_tree(src, out, engine=a.engine, ocr=ocr,
                             docx_via_word=a.docx_via_word, force=a.force)
    except ConversionError as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return 2
    print(f"輸出：{out}")
    print("新增 {new}、更新 {updated}、未變 {unchanged}、失敗 {failed}、不支援 {unsupported}；索引 {indexed} 份".format(**stats))
    for f in stats["unsupported_files"]:
        print(f"  未處理（不支援的格式）：{f}")
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
