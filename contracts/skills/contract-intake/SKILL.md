---
name: contract-intake
description: 讀一份合約（PDF、Word、掃描檔），抽出合約主檔欄位與章節目錄，每個欄位附原文出處，經獨立驗證與使用者確認後才寫入主檔。使用者要登錄、整理、建檔、盤點合約時使用。
---

# 合約登錄（contract-intake）

目標：把一份合約變成可驗證的主檔資料。結論正確性優先於速度；任何一個欄位都不憑印象、不推測、不補常識。

## 不可違反的規則

1. 只從合約原文抽取。原文沒有的欄位寫「未載明」（日期、數字、字串欄位留空，列舉欄位選「未載明」），不由其他欄位或慣例推算。需要推算的值（例如通知截止日）不寫入主檔，由面板計算。
2. 每個有值的欄位附出處：檔案（`source_path`）、頁碼、條號、逐字引句（從原文複製，不改寫、不省略號、不翻譯）。引句須足以支持該欄位的值，且完整出現在同一頁。
3. 原始合約檔唯讀，不改名、不移動、不覆寫。Markdown 與主檔都是可重新產生的衍生資料。
4. 驗證由另一個不帶前情的對話執行；抽取者不得自行驗證自己的結果。驗證不符的項目不得寫入主檔。
5. 寫入主檔前須取得使用者確認。

## 步驟

1. **轉成 Markdown**：先用 `doc-library` skill 把原檔轉成 Markdown。輸出每頁開頭有 `<!-- page: N -->` 標記；後續所有頁碼以這些標記為準。掃描檔（`ocr_used` 為 true）的文字可能有辨識錯誤，關鍵欄位（日期、金額、對象名稱、期間）須對照該頁影像再引用，並在 `notes` 註明。轉換失敗、缺頁或頁標記不連續時停止，向使用者回報，不繼續抽取。
2. **建立章節目錄**：依原文標題列出條號與標題，格式 `第N條 標題`，以 ` | ` 串接，寫入 `toc`。原文沒有條號者以其標題原文為準，不自編條號。每個章節附一筆 citation（`field` 為 `toc`），引句取標題原文。
3. **抽取欄位**：依 `contracts/schema/fields.json` 逐欄處理。`from_text` 為 true 的欄位須附 citation；`from_text` 為 false 的欄位（承辦部門、承辦人、合約類型、對象類別、狀態、合約編號、備註等）不由原文判斷，向使用者詢問或留空。列舉欄位只能填 `fields.json` 中該列舉的 label。日期一律 `YYYY-MM-DD`；原文為民國年者，轉換後在 citation 的 quote 保留民國年原文。
4. **整理關鍵條款摘要**：`key_clauses` 以 `第N條：摘要` 書寫，摘要只複述原文所載事實，每項附 citation。手冊涵蓋的條款類型（期間與續約、終止、付款、責任上限、賠償、保密、智慧財產、個資、準據法與管轄、不可抗力、轉讓）逐一檢查：有則摘要，全文找不到則在 `notes` 寫「全文未見○○條款」並註明搜尋用語。
5. **寫入 Markdown frontmatter**：在轉換後的 Markdown 檔首加入 YAML frontmatter，格式見 `contracts/build_register.py` 的說明；內文原樣保留不修改。frontmatter 含：
   - `fields.json` 的所有欄位（欄位名稱一致）。
   - `source_path`、`source_sha256`、`converted_by`、`converted_at`、`ocr_used`：沿用 doc-library 輸出者，不自行編造；缺少時回報使用者。
   - `verification_status: "未驗證"`。
   - `citations`：每行一筆單行 JSON，`{"field":"end_date","file":"<source_path>","page":3,"clause":"第5條","quote":"逐字引句"}`。同一欄位有多個依據時寫多筆。
6. **機械檢查**：執行 `python contracts/build_register.py --md-dir <md 資料夾> --out <暫存 csv> --allow-unverified`，確認沒有「quote 不在原文中」「有值但沒有 citations」等錯誤；有錯誤先修正再繼續。
7. **獨立驗證**：開一個不帶前情的新對話（或不帶前情的 subagent），只給它轉換後的 Markdown 路徑與下方「驗證交辦」，不給抽取過程的推理。驗證者只更新 `verification_status`、`verified_at`、`verifier_note`，不改欄位值與 citations。結果為「驗證不符」的欄位，回到步驟 3 修正後重驗；無法修正者改填「未載明」並在 `notes` 說明。
8. **使用者確認**：給使用者一張逐欄表：欄位、值、頁碼、條號、引句、驗證結果；`未載明` 欄位單獨列出。使用者確認後才執行：`python contracts/build_register.py --md-dir <md 資料夾> --out <主檔 register.csv>`（只寫入 `verification_status` 為「已驗證」者）。
9. 回報寫入筆數與被擋下的清單；不要手動編輯 `register.csv`。

## 驗證交辦（交給不帶前情的對話）

> 你是合約抽取結果的驗證者。檔案：`<md 路徑>`。逐一檢查 frontmatter 的 `citations`：(1) `quote` 是否逐字出現在內文第 `page` 頁（`<!-- page: N -->` 標記之後、下一個標記之前）；(2) 該欄位的值是否被這段引句直接支持，沒有多出引句沒有的內容；(3) 有值但沒有 citation 的欄位；(4) 原文有載明但被填為「未載明」的欄位（自行在全文搜尋）；(5) `ocr_used` 為 true 時，關鍵欄位對照該頁影像。不要修改任何欄位值或內文。輸出每筆 citation 的「相符／不符／無法判斷」與理由，最後把 `verification_status` 設為「已驗證」（全部相符）或「驗證不符」，並填 `verified_at` 與 `verifier_note`。AI 的驗證不取代人工覆核。

## 輸出給使用者的語氣

只報告原文所載與驗證結果；不寫「應該」「通常」「大概」。無法確定處寫「無法確認」並說明缺什麼。
