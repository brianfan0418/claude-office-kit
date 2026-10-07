# 交接

最後更新：2026-10-07 B14（台灣時間）

## 現況

本 repo 為逐項選用的通用工作資源目錄；合約工具位於 [claude-contract-kit](https://github.com/brianfan0418/claude-contract-kit)。B14 的採用建議文件由 Codex commit 並 push。

## 完成項目與決定

- `README.md` 列出每項資源用途與情境；`GUIDE-FOR-CLAUDE.md` 先了解使用者工作、平台與既有設定，再逐項採用，各項均列 Claude Code 與桌面版 Cowork 用法。
- `templates/CLAUDE.md`、`skills/codex-dispatch/SKILL.md` 移除文件傳送的額外同意要求；公司核准的企業版 Claude／Codex 派工不視為對外。寄信、提交表單與公開發布仍先取得同意。
- doc-library、轉檔說明與本交接已改用獨立合約 repo 的 GitHub 連結。
- `plugin/` 依官方格式包含六個 skills、兩個 hooks 及所需工具；`tools/build_plugin.py` 從原始資源重建，`--check` 核對副本。第三方外掛名稱使用 `office-work-kit`，因官方驗證器禁止 `claude-` 前綴；repo 名稱維持不變。
- 外掛安裝前在封裝副本裁減未採用的資源，不預設全部安裝。外掛結構與封裝依據集中於採用指南，維護原始資源後重建副本。

## 已完成驗證

2026-10-07 B11：依 [gist 官方頁面](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 頁首核對 LLM Wiki 構想文建立日期為 2026-04-04，更新評估原檔並以 build_plugin.py 重建副本。兩份日期來源一致。hooks 10 tests、tools 51 tests 全過且無略過；tools 在一次性虛擬環境安裝 markitdown[docx,pdf]、python-docx、reportlab 後包含真實 DOCX／PDF 轉換。外掛 24 個副本核對及 plugin validate 通過；驗收指定去識別規則排除 .git 後零命中。未修改辦公工具程式；本機 commit 由使用者 push。


```text
python3 -m unittest discover -s hooks         10 tests，OK
python3 -m unittest discover -s tools         51 tests，OK，無略過
python3 tools/build_plugin.py --check         OK，24 個檔案
claude plugin validate plugin                Validation passed
```

測試在 Linux 執行；tools 套件在一次性虛擬環境安裝 markitdown[docx,pdf]、python-docx 與 reportlab 後執行，包含真實 DOCX／PDF 轉換。Word 與 Outlook COM 使用假物件。本輪完整指令及輸出保存於派工交付物 `test-results.txt`，不納入公開 repo。

公開工作樹去識別掃描零命中，Markdown 本機連結與 `git diff --check` 通過；未留下失效的拆分前合約路徑。

## 未驗證與接續動作

1. 在目標 Windows 或 Cowork，以虛構檔案依指南逐項驗證選定資源。官方已確認 Cowork 支援 skills 與 hooks，但本套 Python hooks 的 matcher、工作目錄、Python 指令及實際觸發未驗證。
2. Cowork 讀取主機 Codex CLI／企業登入、Outlook COM、OCR 工具與 GPU 的整合未查證；指南不能當成主機程式已可使用的證據。
3. Windows 真實 Word／Outlook、工作排程器與桌面版外掛上傳尚未實測；需要時由使用者選定環境與資源後測試。

## B14：採用指南語氣

GUIDE-FOR-CLAUDE.md 及 README 改為供您與您的 AI 參考的建議語氣，盤點、資源選擇、封裝及驗證步驟維持具體。既有同意範圍與對外動作限制保留；不預設整套安裝。Git 維持選用，Codex 與 Claude 均可協助。

文件變更驗證：hooks 10 tests 通過；tools 51 tests 通過，其中 1 項依既有 Windows COM 條件跳過；外掛 --check 24 檔一致。Windows Cowork、Word COM 與 Outlook 實機限制仍依既有驗證節。

## B15：版本紀錄預設

2026-10-07 使用者決定：交付環境預設不用 Git，文件版本與處理紀錄由系統負責；AI 若需追蹤自身修改可選用。templates、GUIDE、project-docs 與外掛副本同步取消 git init／commit 的預設要求；既有開發 repo 的維護規則仍沿用。驗證：hooks 10 tests、tools 51 tests（1 個 Windows COM 條件跳過）通過；外掛 --check 24 檔一致。
