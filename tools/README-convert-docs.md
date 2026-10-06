# convert_docs.py：把 Word、PDF、Excel、PowerPoint 轉成帶 metadata 的 Markdown

本工具讀取一個資料夾（含子資料夾），為每份文件產生一份 Markdown 衍生檔，供 Claude 閱讀與查詢。原檔只讀不改；衍生檔可隨時刪除重產，唯一依據永遠是原檔。

## 它做什麼

| 原檔 | 處理方式 |
|---|---|
| .docx、.xlsx、.xls、.pptx | MarkItDown（預設）；.docx 失敗時自動改用 pandoc |
| .doc、.rtf | 以 Word COM 唯讀開啟，另存成暫存 .docx，再交給 MarkItDown；暫存檔轉完即刪 |
| .pdf（有文字層） | 逐頁以 MarkItDown 轉換，每頁前加 `<!-- page: N -->` |
| .pdf（無文字層） | 標記 `ocr: required`，不猜測內容；以 `--ocr-backend` 選擇 OCR 來源（見下節） |
| .md | 保留內文與領域 frontmatter，重建通用來源鍵；不複製來源的驗證狀態 |
| 其他格式 | 不處理，執行結束時列出檔名 |

每份衍生檔開頭是 YAML frontmatter；欄位定義見 `contracts/schema/fields.json` 的 `frontmatter`，下表說明轉檔行為。

| 欄位 | 內容 |
|---|---|
| `source_path` | 原檔相對於輸入資料夾的路徑 |
| `source_sha256` | 原檔指紋，用來判斷原檔有無變動 |
| `source_modified` | 原檔修改時間（UTC） |
| `converter` | 轉換工具與版本 |
| `converted_at` | 轉換時間（UTC） |
| `pages` | PDF 頁數；Word、Excel 無固定頁數，留空 |
| `ocr` | `false`（本文來自文字層）、`required`（整份無文字層，尚未 OCR）、`partial`（仍有頁面無文字）、`true`（至少一頁的文字來自 OCR，不是逐字原文） |
| `ocr_engine`、`ocr_pages` | OCR 引擎與版本；來自 OCR 的頁碼清單 |
| `ocr_source`、`ocr_source_sha256` | 沿用既有 OCR 輸出時，該輸出檔的相對路徑與指紋 |
| `title` | 以檔名預填；contract-intake 核對並驗證後覆寫同一鍵，整份 frontmatter 只有一個 title |
| `warnings` | 轉換可能漏掉的內容（追蹤修訂、頁首頁尾、註解、文字方塊、OCR 風險等） |
| `needs_review` | 原檔更新後，沿用的業務欄位尚待人工複核 |
| `verification_status` | 新轉與重轉均為「未驗證」；狀態定義見 `contracts/schema/fields.json` |
| 業務欄位區 | 由各領域定義與填寫；合約見 `contracts/schema/fields.json`；重轉保留領域欄位，但須重新驗證 |

另外產生：

- `index.md`：每份一行（連結、標題、頁數、轉換日期、是否 OCR）。每次執行後重建，不手動修改。
- `log.md`：每次轉換追加一行，格式 `## [日期 時間] 動作 | 原檔 | sha256 前 12 碼 | 工具`，動作為 new、updated、failed。
- `_history/`：原檔變動後，被取代的舊版 Markdown。

## 增量規則

以 sha256 判斷：原檔沒變就跳過；原檔變了就重轉，舊版先存進 `_history/`，`verification_status` 重設為「未驗證」、`needs_review` 設為 true。複核新版原文完成後才解除旗標；合約主檔不寫入待複核文件。原檔被刪除時，衍生檔不會自動刪除，由 `--lint` 列為「孤兒頁」。

## 用法

```
python convert_docs.py D:\合約\原檔                      輸出到 D:\合約\原檔-md
python convert_docs.py D:\合約\原檔 -o D:\合約\衍生       指定輸出資料夾
python convert_docs.py D:\合約\原檔 -o D:\合約\衍生 --lint 只檢查，不轉換
```

選項：`--engine pandoc`（改以 pandoc 為預設）、`--docx-via-word`（.docx 也先經 Word 另存）、`--force`（忽略 sha256，全部重轉）、OCR 相關選項（見下節）。輸出資料夾不可放在原檔資料夾內。

## 掃描型 PDF 與 OCR

OCR 文字不是逐字原文。frontmatter 以 `ocr: true` 與 `ocr_engine` 標示，`warnings` 附提醒：日期、金額、當事人、期間、通知天數等關鍵欄位引用 OCR 文字時，必須對照該頁影像確認，確認前不得視為已驗證。

### 第一次使用前：盤點既有 OCR 環境

使用者可能已有 OCR 軟體與 GPU。第一次處理掃描檔之前，先盤點並向使用者報告，再選路；已有可用的就沿用，不重複安裝。盤點項目：

- GPU：`nvidia-smi`（顯示型號、驅動與 CUDA 版本；指令不存在或報錯代表沒有 NVIDIA 驅動）。
- 已安裝的 OCR 程式：開始功能表或「設定 > 應用程式」搜尋 ABBYY FineReader、Adobe Acrobat、其他 OCR 軟體。
- Python 套件：`py -m pip list`，查看 docling、paddleocr、easyocr、surya、pytesseract、rapidocr、ocrmypdf 等。
- 既有 OCR 輸出：詢問使用者掃描檔經 OCR 後存在哪裡（含文字層的 PDF、.txt、.docx），這些可直接沿用。

### 選項

| `--ocr-backend` | 行為 |
|---|---|
| `none`（預設） | 只標記 `ocr: required`，不產生文字 |
| `existing-text` | 沿用使用者既有工具的輸出。以 `--ocr-dir` 指定輸出資料夾（結構與原檔資料夾相同）；找檔順序為同相對路徑的 PDF（含文字層）、同名 `.txt`、`<原檔名>.pdf.txt`。文字檔以換頁字元（Form Feed，`\f`）分頁；頁數與原檔不符時整份轉換失敗，避免頁碼錯位。`--ocr-engine-name "工具名稱"` 記入 `ocr_engine` |
| `docling` | 以本機 docling 做 OCR；`--ocr-device auto｜cuda｜cpu` 選裝置；`--ocr-lang` 指定語言標籤 |

```
python convert_docs.py D:\合約\原檔 -o D:\合約\衍生 --ocr-backend existing-text --ocr-dir D:\合約\OCR輸出 --ocr-engine-name "ABBYY FineReader"
python convert_docs.py D:\合約\原檔 -o D:\合約\衍生 --ocr-backend docling --ocr-device cuda
```

掃描檔已有 OCR 輸出或改用其他後端後再次執行，原本 `ocr: required` 的檔案會重新轉換；OCR 輸出檔變動時亦同。

### docling 的 GPU 支援（依官方文件，2026-10-07 查，未實測）

- 官方 GPU 文件以 `AcceleratorOptions(device=AcceleratorDevice.CUDA)`（或 `AUTO`）選擇裝置；本工具的 `--ocr-device` 即據此傳入。
- docling 的 OCR 引擎依賴第三方套件，GPU 是否可用取決於各引擎。官方文件僅說明 RapidOCR 可經 Torch 或 ONNX Runtime 後端使用 GPU；ONNX Runtime 後端需安裝 `pip install "docling[onnxruntime]"`，並確認 `onnxruntime` 載入得到 `CUDAExecutionProvider`。
- 本工具呼叫 docling 時使用 docling 預設的 OCR 引擎設定，沒有指定 RapidOCR 的 ONNX Runtime 後端，因此預設設定下 OCR 是否真的用到 GPU 未驗證。要使用該設定須自行調整程式。
- 中文辨識品質、`--ocr-lang` 的中文標籤寫法、Windows 上的 CUDA 安裝，均未實測。

`--lint` 檢查：原檔已變但衍生檔未更新、原檔不存在的孤兒頁、原檔沒有衍生檔、frontmatter 缺欄、OCR 未完成、待複核、頁碼標記數與 `pages` 不符、`index.md` 與實際檔案不一致。有問題時結束代碼為 1。內容矛盾這類需要判讀的檢查不在此處，見 `skills/doc-library/SKILL.md`。

## Windows 安裝

1. 安裝 Python 3.10 以上版本（python.org 下載；安裝畫面勾選「Add python.exe to PATH」）。
2. 開啟 PowerShell，執行：

   ```
   py -m pip install "markitdown[docx,pdf,xlsx,xls,pptx]" pywin32
   ```

   `pywin32` 只在需要轉換 .doc、.rtf 時使用，並需要本機已安裝 Microsoft Word。
3. 確認安裝：`py -c "import markitdown, pdfplumber, pypdfium2; print('ok')"`。
4. 選配：
   - pandoc（.docx 備援）：自 pandoc.org/installing.html 下載 Windows 安裝程式。
   - docling（掃描型 PDF 的 OCR）：`py -m pip install docling`。體積大，首次執行可能需要下載模型。

## 選用工具與依據

預設採 MarkItDown，pandoc 為 .docx 備援。

| 項目 | MarkItDown | pandoc |
|---|---|---|
| 授權 | MIT（GitHub 授權欄位，2026-10-07 查） | GPL-2.0（GitHub 授權欄位，2026-10-07 查） |
| 安裝 | `pip` 套件，同一套件涵蓋 docx、xlsx、pptx、pdf | 獨立執行檔，須另外安裝 |
| 讀 PDF | 可 | 不可（官方手冊的輸入格式清單無 PDF） |
| 定位 | 官方說明為供文字分析工具讀取，「可能不是人類閱讀所需高保真轉換的最佳選擇」 | 通用文件轉換器 |

選 MarkItDown 為預設的理由：單一套件涵蓋本工具需要的全部格式，安裝步驟最少，適合非工程人員在 Windows 上安裝；pandoc 無法讀 PDF，無法單獨涵蓋。pandoc 保留為 .docx 備援，因為它另有 `--track-changes=all` 可顯示追蹤修訂（以 pandoc 3.1.3 實測會輸出刪除與插入的標記）。

來源：

- MarkItDown：https://github.com/microsoft/markitdown
- pandoc 手冊：https://pandoc.org/MANUAL.html
- docling：https://github.com/docling-project/docling（MIT；官方說明具備掃描 PDF 與影像的 OCR）

掃描型 PDF 不用 MarkItDown 的 OCR 外掛（`markitdown-ocr`）：依其官方說明，該外掛透過 LLM 視覺模型辨識，頁面影像會送往外部模型服務，法務文件不宜預設如此；大型語言模型辨識也可能產出原文沒有的文字（推論，未實測）。docling 的 OCR 引擎在本機執行（官方範例列有 Tesseract、EasyOCR、RapidOCR、macOS OCR 等選項）。

## 已實測與未實測

已在 Linux 實測（Python 3.12、markitdown 0.1.8、pandoc 3.1.3）：

- 自製 .docx 與文字型 PDF 的轉換、frontmatter、頁碼標記、增量、`_history/`、`index.md`、`log.md`、`--lint`。
- 追蹤修訂：MarkItDown 輸出含已插入的文字、不含已刪除的文字。
- 頁首文字：MarkItDown 輸出不含。
- 沒有文字層的 PDF 被標記為 `ocr: required`。
- Word COM 以假物件測試呼叫順序（`ReadOnly=True`、`SaveAs2` 為 .docx、`Close(SaveChanges=0)`、`Quit`）。

未在 Windows 實測，亦未用真實 Word 實測：

- Word COM 轉換 .doc、.rtf（`DispatchEx("Word.Application")`、`Documents.Open`、`SaveAs2(FileFormat=12)`、`AutomationSecurity=3` 停用巨集）。密碼保護、損毀、受保護檢視的檔案如何回應未知。
- docling 的 OCR 與 GPU：呼叫方式依官方文件與範例撰寫，中文辨識品質、逐頁匯出（`export_to_markdown(page_no=...)`）、GPU 實際使用均未實測。
- `existing-text` 只以假資料與自製 PDF 測試；ABBYY FineReader、Adobe Acrobat 等實際輸出的換頁字元與編碼未實測。
- .xls、.pptx、.xlsx 的實轉。
- 超大檔案與大量檔案的效能。

## 已知限制

- PDF 頁碼是檔案的第幾頁（第 1 頁起算），不一定等於頁面上印的頁碼。
- Word 沒有固定頁碼（頁數隨印表機與版面變動），本工具不為 Word 標頁；引用 Word 文件時用條號與標題，並回原檔核對。
- Word 自動編號（條號、項次）在轉出的 Markdown 中可能與原檔畫面不同（推論，未實測）；條號以原檔為準。
- 逐頁轉換的 PDF，跨頁的表格會被切成兩段。
- 文字型 PDF 若本身是掃描檔經 OCR 軟體加上文字層，文字可能有辨識錯誤，工具無法偵測，frontmatter `warnings` 對所有文字型 PDF 都附此提醒。
- 轉換結果不含：Word 頁首頁尾、註解、文字方塊、圖片內的文字、Excel 公式本身（以儲存值為準）。這些內容以 `warnings` 提示時才有偵測，沒有提示不代表沒有，重要文件請回原檔核對。
- 工具只做格式轉換，不判斷內容，也不填寫業務欄位。
