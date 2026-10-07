---
name: doc-library
description: 管理大量合約、法務與公司文件（Word、PDF、Excel，含掃描檔）時載入：收錄（ingest）、查詢（query）與健檢（lint）。涵蓋原始文件與衍生 Markdown 的分層、YAML frontmatter、OCR 文字的驗證規則，以及回答必須引用原文頁碼並回原文核對的做法。使用者要整理、搜尋、比對一批文件，或問「這份合約怎麼寫」「哪些合約快到期」時使用。
---

# 大量文件管理（doc-library）

使用者是合約與法務的最終把關者。本 skill 的目標是讓每一個結論都能追溯到原文的某一頁或某一條，而不是讓 AI（Codex、Claude 皆可）記住文件內容。

## 不可違反的規則

1. 原始文件是唯一依據。不修改、不覆蓋、不搬移、不刪除原檔。
2. 衍生內容（Markdown、摘要、索引、主題頁）都可能有轉換錯誤，只用來尋找與導覽。任何要告訴使用者的結論，先回原文核對、引用原文頁碼或條號。
3. 原文沒寫的事，回答「文件中未找到」。不用常識、慣例或記憶補空白，不推測當事人的意圖。
4. 兩份文件互相矛盾時，並列兩處原文與出處，不自行調和或擇一。
5. OCR 文字不是逐字原文。日期、金額、當事人、期間、通知天數這類關鍵欄位引用 OCR 文字時，先對照該頁影像確認；未對照前，驗證狀態不得標為「已驗證」。
6. 沒有把握的地方明說沒把握，並說明缺什麼才能確認。

## 三層結構

建議的資料夾配置（路徑可自訂，三者分開存放）：

```
文件庫/
  原檔/      第一層：原始文件，唯讀。使用者自己維護，AI（Codex、Claude 皆可）不寫入
  衍生/      第二層：convert_docs.py 產生的 Markdown 加 metadata，可整個刪除重產
    index.md   每份文件一行，由工具產生
    log.md     每次轉換一行，由工具追加
    _history/  原檔變動前的舊版 Markdown
  主題/      第三層：主題頁與人工整理的導覽（選用，規則見「主題頁」）
```

| 層 | 內容 | 誰寫 | 可信度 |
|---|---|---|---|
| 一 | 原始 .doc/.docx/.pdf/.xlsx 等 | 外部來源 | 唯一依據 |
| 二 | 衍生 Markdown 與 frontmatter | 工具產生，業務欄位由 AI（Codex、Claude 皆可）依原文填寫 | 轉換可能有誤，須回原文核對 |
| 三 | `index.md`、`主題/` | 工具與 AI（Codex、Claude 皆可）| 只作導覽 |

衍生層放在原檔資料夾之外：工具拒絕把輸出放進原檔資料夾，避免污染原始文件。

## YAML frontmatter

frontmatter 是 Markdown 檔最前面、以兩行 `---` 包起來的一段「欄位名: 值」，像文件的資料卡。AI（Codex、Claude 皆可）與腳本可以不讀全文就知道這份文件是哪個原檔、何時轉的、有沒有 OCR，也能用一個指令列出「所有到期日在三個月內的合約」。

使用它的原因：

- 可追溯：`source_path` 與 `source_sha256` 指回原檔，原檔改了就查得出來。
- 可檢查：欄位固定，缺欄或過期可由腳本機械檢查，不靠印象。
- 可篩選：業務欄位集中在同一個位置。

轉檔通用鍵為 `converter`、`ocr`、`ocr_engine`、`ocr_pages`、`source_path`、`source_sha256`、`source_modified`、`converted_at`、`pages`、`title`；工具另記錄轉檔警告與複核旗標。業務欄位由各領域定義；合約見 [合約欄位定義](https://github.com/brianfan0418/claude-contract-kit/blob/main/schema/fields.json)。轉檔行為與限制見 `<工具包資料夾>/tools/README-convert-docs.md`。

- 只填原文明文寫出的內容。原文沒寫、看不出來就依領域規則留空或標示未載明，不推算。
- 引用一律存於 `citations`，格式與必填條件依領域定義；合約依上述 schema 與 contract-intake 流程處理。
- `title` 轉檔時以檔名預填；contract-intake 核對原文並完成驗證後，覆寫同一鍵，整份 frontmatter 只保留一個 `title`。其餘轉檔來源資訊不手動修改。
- 重轉時保留業務欄位，`verification_status` 重設為「未驗證」、`needs_review` 設為 `true`。新版原文驗證完成後才改回 `false`，否則合約主檔不收錄。

## 驗證狀態

驗證狀態依 [合約欄位定義](https://github.com/brianfan0418/claude-contract-kit/blob/main/schema/fields.json) 的 `verification_status` 列舉，不另訂狀態或格式。OCR 文字尚未對照影像屬「未驗證」；只有依領域驗證流程確認原檔與欄位相符後，才可標「已驗證」，確認不符則標「驗證不符」。

使用者要據以簽約、發函、報價的內容，須為「已驗證」。無法開啟原檔或對照影像時，維持「未驗證」並說明缺少的依據。

## 第一次使用前：盤點 OCR 環境

使用者可能已有 OCR 軟體與 GPU，也可能已有 OCR 過的輸出。大量掃描檔的庫，先盤點並向使用者報告，再選路；已有可用的就沿用，不重複安裝。

1. 查 GPU：`nvidia-smi`。指令不存在或報錯，代表沒有 NVIDIA 驅動，不代表沒有顯示卡。
2. 查已安裝程式：ABBYY FineReader、Adobe Acrobat 或其他 OCR 軟體（開始功能表、「設定 > 應用程式」，或詢問使用者）。
3. 查 Python 套件：`py -m pip list`，看 docling、paddleocr、easyocr、surya、pytesseract、rapidocr、ocrmypdf 等。
4. 詢問既有 OCR 輸出：掃描檔經 OCR 後存在哪裡（含文字層的 PDF、.txt、.docx）。
5. 向使用者報告盤點結果與建議的路，由使用者決定。選項：
   - 沿用既有輸出：`--ocr-backend existing-text --ocr-dir <資料夾> --ocr-engine-name "<工具名稱>"`。
   - 用既有工具補做 OCR（例如在 FineReader 或 Acrobat 內批次處理），輸出放到 OCR 輸出資料夾，再用上一項收錄。
   - 以 docling 本機 OCR：`--ocr-backend docling --ocr-device cuda`。GPU 支援依官方文件，專案內未實測，細節與限制見 `<工具包資料夾>/tools/README-convert-docs.md`。
6. 不為了「能 OCR」就安裝新軟體；先確認既有路徑不可用。

## 操作一：收錄（ingest）

1. 確認原檔資料夾與衍生資料夾路徑；第一次使用先做上一節盤點。
2. 執行 `python "<工具包資料夾>/tools/convert_docs.py" <原檔資料夾> -o <衍生資料夾>`（參數見 `<工具包資料夾>/tools/README-convert-docs.md`）。增量：原檔沒變的會跳過。
3. 讀工具的結束摘要與 `log.md` 新增的行。逐一處理：
   - 失敗：向使用者回報檔名與原因，不略過不提。
   - 不支援的格式：列給使用者。
   - `ocr: required` 或 `partial`：回報張數，依上一節選路。
   - `warnings` 有內容：該份文件引用時一律回原檔核對對應內容（追蹤修訂、頁首頁尾、註解、文字方塊、OCR）。
4. 抽查：每批至少開啟一份原檔，與衍生 Markdown 對照（標題、一個數字、一個日期、頁碼標記），確認轉換沒有系統性錯誤。抽查結果向使用者報告，沒抽查就不說已確認。
5. 填業務欄位（規則見「YAML frontmatter」）。
6. 執行 `--lint`（見操作三），把結果報告給使用者。

收錄完成不代表內容已被理解或驗證，只代表衍生檔已產生。

## 操作二：查詢（query）

1. 從 `index.md` 與 frontmatter 縮小範圍（用 grep 或逐檔讀取 frontmatter）。不憑記憶或上次對話的結論作答。
2. 讀衍生 Markdown 找到相關段落，記下檔名與頁碼（PDF 的 `<!-- page: N -->`）或條號與標題（Word 沒有固定頁碼）。
3. 回原檔核對：開啟原檔該頁或該條，確認文字相同。OCR 來源的頁面對照影像。無法核對時，在回答中標示「未回原檔核對」。
4. 回答格式：

   - 結論一至兩句。
   - 每個事實附出處：`〈檔名〉p.N`（PDF）或 `〈檔名〉第 X 條`（Word），並附原文逐字引文（引用區塊）。
   - 驗證狀態（見「驗證狀態」）。
   - 找不到時寫「文件中未找到 X」，並說明查了哪些文件。
   - 摘要與解讀和原文引文分開寫，讓使用者看得出哪些是原文、哪些是 AI（Codex、Claude 皆可）的歸納。
5. 查詢範圍涉及多份文件時，列出納入的文件清單，使用者才知道有沒有漏。
6. 法律意見與風險判斷由使用者與法務決定；AI（Codex、Claude 皆可）提供原文位置、差異與待釐清的問題。

## 操作三：健檢（lint）

先跑機械檢查：`python "<工具包資料夾>/tools/convert_docs.py" <原檔資料夾> -o <衍生資料夾> --lint`。它檢查：

- 原檔已變但衍生檔未更新（`過期`）
- 原檔不存在的衍生檔（`孤兒頁`）、原檔沒有衍生檔（`未轉換`）
- frontmatter 缺欄
- OCR 未完成、`needs_review` 待複核
- `pages` 與頁碼標記數不符、`index.md` 與實際檔案不一致

處理：過期與未轉換者重新執行收錄；孤兒頁由使用者決定保留或移除（AI（Codex、Claude 皆可）不刪除原檔，衍生檔移除前也先詢問）。

再做機械檢查做不到的檢查（AI（Codex、Claude 皆可）讀文件判斷，結果向使用者報告為「疑似」，附雙方原文出處）：

- 互相矛盾：同一對象、不同文件的日期、金額、期間、通知天數不一致。
- 業務欄位與原文不符：抽查已填欄位，對照 `citations` 記的出處。
- 主題頁孤兒或失效：沒有任何連結指向的主題頁；連結的衍生檔已不存在。
- 主題頁的敘述與原文不符。

## 主題頁

主題頁（`主題/`）是選用的導覽，例如「各廠商保密合約一覽」。與 LLM Wiki 構想不同，這裡不讓 AI（Codex、Claude 皆可）的摘要成為知識本身，評估見 `references/llm-wiki-evaluation.md`。規則：

- 內容只放：文件清單、指向原文頁碼的連結、原文逐字引文。不放 AI（Codex、Claude 皆可）的歸納結論當作事實。
- 每個陳述附出處（檔名與頁碼或條號）；沒有出處的句子不寫。
- frontmatter 記 `generated_from`（所依據的衍生檔清單與其 `source_sha256`）與 `generated_at`；來源檔變動後，主題頁視為過期，健檢時列出。
- 頁首註明「導覽用，結論須回原文」。
- 查詢的答案不自動存成主題頁；使用者要求保存時，依上述規則寫入。

## 工具使用的限制

- 轉換工具不能保證完整（頁首頁尾、註解、文字方塊、圖片內文字、Word 自動編號可能缺漏或不同），限制清單見 `<工具包資料夾>/tools/README-convert-docs.md`。
- PDF 頁碼為檔案的第幾頁，不一定等於頁面上印的頁碼；引用時兩者不同要註明。
- Word 的頁數隨版面變動，引用 Word 以條號與標題為準。
