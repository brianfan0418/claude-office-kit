# 交接

最後更新：2026-10-07 06:32（台灣時間）

## 一句話狀態

2026-10-07 驗收必修 1～10 項已修正；四組測試共 96 個通過，無略過項目，端到端可產生一筆合約主檔；本輪僅建立一個本機 commit，不 push。

## 已完成與證據

- 欄位與驗證狀態：`contracts/schema/fields.json` 定義主檔及 frontmatter；轉檔、doc-library 與 contract-intake 共用鍵名、citations 與同一個 title。
- 主檔閘門：`contracts/build_register.py` 排除各層 `_history/`，拒收 `needs_review: true`；引用須有頁碼或條號，逐字比對，有頁碼時限於對應頁標記區段。
- 原檔重轉：`tools/convert_docs.py` 保留領域欄位，但重設驗證狀態與複核旗標；Markdown 來源可保留領域 frontmatter 並重建通用鍵。`contracts/test_build_register.py`、`tools/test_convert_docs.py` 涵蓋歷史檔、重轉、單一 title、條號引用與空清單型別。
- Windows 安裝：`INSTALL-FOR-CLAUDE.md` 的 19 段 PowerShell 均重新設定 ws、cl、kit；步驟 7.6 安裝文件庫與合約 skills、套件並替換腳本路徑佔位。最終測試從示範專案開新對話。legal 功能名稱已核對官方 README。
- CUAD 與手冊：`contracts/README.md` 附論文與查閱日期；schema、README、playbook 類別名稱已核對附錄。手冊移除未附來源數字，標示一般慣例須法務確認，法條附官方查詢來源與核對要求。
- 文件外送同意：`templates/CLAUDE.md` 與 `skills/codex-dispatch/SKILL.md` 要求外送前取得同意，合約與個資逐批確認。
- 工具索引與 Outlook：根目錄 README 補文件庫、工具及四組測試；`tools/README-outlook-watch.md` 明列非英文語系日期篩選未實測及首次新信比對程序。

## 驗證

```text
python3 -m unittest discover -s hooks                 10 tests，OK
python3 -m unittest discover -s contracts             20 tests，OK
python3 -m unittest discover -s contracts/dashboard   15 tests，OK
python3 -m unittest discover -s tools                 51 tests，OK
```

- 測試於 Linux 執行。真實 DOCX／PDF 整合測試已執行；Word、Outlook COM 使用假物件測試。完整指令輸出保存於本次派工輸出目錄的 `test-results.txt`。
- 端到端：自製含 frontmatter 的 Markdown 經轉檔 CLI 產生通用鍵，未驗證時主檔拒收；以固定測試值核對原文、覆寫原 title 並設定驗證狀態後，主檔 CLI 搭配 `--source-root` 寫入一筆，原檔 SHA-256 不變。此為程式測試，未宣稱完成真實合約的人工或獨立模型審閱。完整鍵值與 CSV 保存於派工輸出目錄的 `e2e-output.txt`，不在 scratch 中。
- PowerShell 路徑設定、skill 腳本佔位、手冊無數字要點及法條來源已用程式檢查；去識別掃描零命中；`git diff --check` 通過。

## 下一步與限制

1. 在目標 Windows 電腦依安裝文件檢查環境與使用者同意，執行安裝及示範專案的新對話驗證。Windows、Word COM 與真實 Outlook 尚未在本次執行環境實測。
2. 合約審閱前由法務填寫公司立場並核對現行法條；外送合約或個資前按範本逐批取得同意。
3. 本次未留下必修未完成項目；公開發布與 push 由使用者後續決定。
