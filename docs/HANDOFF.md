# 交接

最後更新：2026-10-07（K1b）

## 現況

本 repo 提供使用者與 Codex／Claude 逐項選用的 AI 工作資源，交付環境預設不用 Git，也不替對方安裝或設排程。本開發 repo 維持 commit 與 push。K1 的模型、額度、更新、官方文件下載、派工、文件落差與登記表已加入；K1b 補齊必讀清單、寫法 gate 及中文短派工。

- 原始資源在 skills、hooks、tools、knowledge、templates；plugin 是 build_plugin.py 產生的 0.3.0 外掛副本，維護原始檔後重建。
- Codex 與 Claude 均可選用、派工與驗收；企業版之間派工不視為對外行為，寄信、表單、付款及發布仍依使用者授權處理。
- 工具只用標準函式庫；既有轉檔與 Outlook 的選用依賴仍依各自說明。私人文件、帳號資料及下載原檔不納入公開 repo。

## K1b 決定與依據

各項官方來源、平台差異與採用方式集中於 [開場說明](../hooks/README-session-start.md) 及 [工作管理工具說明](../tools/README-ai-management.md)。

| 項目 | 本機參考／官方依據 | 公開決定 |
|---|---|---|
| 必讀清單 | round_start.py 的 MUST_READ＋理由、定案逐條列出、HANDOFF 指定章節原文、工作線 | docs/session-start.json；path、reason、full／section／path；由專案 AI 維護；hook 只讀取與檢查 |
| 原生開場 | Claude SessionStart／additionalContext／@path；Codex hooks 與 AGENTS.md 官方文件 | 同一 Python hook、startup／resume／clear／compact；原生指示檔放固定規則，清單處理章節與檢查 |
| 長度／缺檔 | round_start.py 缺檔結束碼；官方 SessionStart 的事件行為 | context 預設 24000 字元；超量改列路徑、不截條文；缺檔明示；手動 --text --check 非零，hook 回傳有效 context |
| 登記表 | 既有 registry.py／REGISTRY.md | 開場每支工具一行用途；寫新腳本前先查，已有的直接使用；不另建產生器 |
| 寫法 gate | skill-gate.py 的用途分類；兩端官方 PreToolUse／PostToolUse | 規則／skill／派工查 handoff-docs，專案文件加 project-docs；成功載入後放行，壓縮後重讀；不解析不穩定 transcript |
| 短派工 | 既有 codex-run.py／queue；npm scripts 將名稱與設定分離的官方慣例 | tasks/中文名稱/brief.md＋task.json；根目錄 python dispatch.py 中文名稱；帳號、模型、強度及權限留設定檔 |
| 前景等待 | 既有 FG_WAIT；Codex 官方 unified exec handler 的 hook 輸入 | 短指令派出獨立 worker 後回傳；資源等待在 worker、狀態 queued；Codex 用 --status，Claude 可背景 --wait |
| 外掛同步 | 既有 build_plugin.py 與官方外掛格式 | 附三個 hooks、共用狀態、兩端設定、必讀與任務範本；52 個檔案 |

本機來源只參考行為，沒有複製專案名稱、條文、帳號、服務或私人路徑。K1 基礎工具的各項來源仍見工具說明與程式檔頭；模型清單以更新程式維護，不更改預設模型或切換帳號。

## 已完成驗證

- Linux：hooks 37 tests、tools 95 tests，共 132 通過，無略過；一次性測試環境含既有轉檔的 markitdown[docx,pdf]、python-docx、reportlab，含真實 DOCX／PDF 轉換。
- 新增測試含清單全文／章節／路徑、無清單提示同 session 一次、缺檔／章節／格式、超量、不截斷定案、四個開場來源重載、總長含工具摘要、成功 skill 載入及壓縮失效。
- 派工測試含中文任務資料夾、根目錄短入口、設定驗證／傳遞、worker 回覆與摘要、既有結果保留、queued 狀態及資源逾時未啟動 CLI；CLI 執行以替身測試。
- 外掛 52 檔副本核對與官方 claude plugin validate plugin 通過。登記表、知識索引、Markdown 本機連結與去識別於提交前核對；去識別只保留本 repo 的網址。
- K1 已核對真實 App Server 模型／額度與官方文件下載；本輪沿用其實作及回歸測試，不升級維護者 CLI 或替對方設定排程。

## 未驗證與第一個接續動作

第一個動作：在目標 Windows 用虛構專案部署入口，填一份中文任務；送出後查 --status、result.md 及 summary.json，再於所選介面重開、恢復與壓縮，核對必讀原文及 gate。

1. Windows npm／Node 入口、分離行程、Job Object、PowerShell 與工作排程器未在實機驗證。
2. Claude／Codex 的本程式 hook 真實介面注入、Codex 信任流程與 Cowork 的 Python／工具 matcher／工作目錄尚未端到端實測；官方機制已查證，JSON 假輸入與安裝器以暫存資料夾驗證。
3. gate 涵蓋官方所列工具與常見 shell 寫檔，無法解析任意程式全部副作用；hook 未採用、未信任或逾時不能當作生效。SessionStart 注入不等於保證 AI 遵守所有原文。
4. mtime 只作待核對線索；Claude 企業的即時剩餘額度公開 API 未查得，保持未知。既有 Windows Outlook COM、OCR／GPU 與 Cowork 主機 CLI 登入亦未實測。
