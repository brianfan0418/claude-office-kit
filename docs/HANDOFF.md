# 交接

最後更新：2026-10-07（K1d）

## 現況

K1、K1b、K1c 的工作管理資源已補齊；K1d 已評估並修正驗收 F1–F7。本 repo 供使用者與 Codex／Claude 逐項選用；交付環境預設不用 Git，不替對方安裝、信任 hooks 或設定排程。本開發 repo 依交辦提交推送。

- 原始資源在 skills、hooks、tools、knowledge、templates；plugin 是 build_plugin.py 產生的 0.3.2 副本，共 56 個檔案，維護原始檔後重建。
- K1 提供模型／額度、CLI 更新、官方文件下載、派工記錄／狀態、文件落差與登記表；K1b 提供 AI 維護的必讀清單、寫法 gate 與中文任務資料夾。
- K1c 背景派工／等待用 description「任務名（模型・強度）」；新增官方用量的 70% 收尾提醒，以及官方 prompt-audit 的採用建議。
- 新增工具與 hooks 僅用 Python 標準函式庫；既有轉檔及 Outlook 的選用依賴仍依各自說明。私人文件、帳號、下載原檔與測試環境不納入公開 repo。

## 現行決定與依據

操作與來源集中於 [開場說明](../hooks/README-session-start.md)、[工具說明](../tools/README-ai-management.md)、[採用指南](../GUIDE-FOR-CLAUDE.md)，後續請更新原說明，其他入口保持連結。

| 項目 | 參考依據 | 公開實作 |
|---|---|---|
| 必讀清單 | round_start.py 的 MUST_READ、理由、定案原文與工作線；兩端官方 SessionStart | docs/session-start.json，path／reason／full、section、path；缺檔明示、超量列路徑，不截條文；由專案 AI 維護 |
| 工具摘要／索引 | 既有 registry.py 與 REGISTRY.md | 開場每支一行用途；寫新腳本前查表，已有直接用；沿用產生器 |
| 寫法 gate | 本機 skill-gate.py；兩端官方 PreToolUse／PostToolUse | 規則、skill、派工查 handoff-docs；專案文件加 project-docs；成功讀取才記錄，壓縮後重讀 |
| 任務設定／等待 | codex-run.py／queue 與 npm scripts；Codex 官方 unified exec handler | tasks/中文名稱/brief.md＋task.json；短指令供執行；獨立 worker、queued 狀態；Codex 單次 --status，Claude 可背景 --wait |
| 背景標籤 | 本機 skill-gate.py 的 BG_WAIT／LABEL；官方 Bash／PowerShell 欄位；使用者的 App Bash 實測 | gate 強制全形「任務名（模型・強度）」；格式不符先擋，模型／強度由 AI 核對設定；Codex 對等畫面未確認 |
| 收尾提醒 | 本機 session-brief.py 的 wrapup_nudge；官方 statusLine／UserPromptSubmit | context_status.py 接官方百分比，wrapup_nudge.py 每輪讀取；>=70% 且尚缺任一寫法 skill，同對話提醒一次；無值／壓縮舊值不推算 |
| 狀態列採用 | 官方 statusLine 的 JSON 與 Windows Git Bash／PowerShell 規則 | install_hooks.py 選 --with-context-status；備存並轉交原指令、保留其他設定；更換 Python 不再次包裝；外掛不代設 statusLine |
| 規則檔審查 | 官方 memory 與 commands 的 prompt-audit | 指南列 v2.1.283 門檻、別名、範圍、單一路徑、內建 skill 限制及使用者同意後才改檔；Cowork／Codex 專用對等功能未確認 |

本機來源只參考行為；沒有公開私人專案、條文、帳號、服務或路徑。K1 的各項來源見工具說明與檔頭；模型知識有資料日期及更新程式，不更改預設模型或切換帳號。

## K1d 驗收修正

F1–F7 均成立；每項先以新測試重現原問題，再修正，同步原始資源與外掛。

| 項目 | 本輪修正與驗證 |
|---|---|
| F1 更新結果不明 | 保留 pending，下一輪一般更新先停止；測試未知回退、已核對回退、升級成功及版本已最新仍有 pending |
| F2 自訂派工輸出漏列 | 總覽與開場共用 --project，合併 tasks 設定與預設位置；測試中文自訂 out、絕對位置、去重、預設與錯誤警示 |
| F3 Windows 本機連結漏查 | 先辨識磁碟／反斜線 UNC，再解析網址；Windows 查存在，其他平台明示無法核對；測試原問題與原生分支替身 |
| F4 Python 路徑有空白 | 引用執行檔；Claude 依 Windows shell 使用 Bash／PowerShell，Codex 明確啟動 PowerShell；保留退出碼、升級舊指令；測試實際 POSIX 子行程與 Windows 設定替身 |
| F5 文件更新規則衝突 | 使用者 K1d 指定制度內／版本控制文件在原路徑照制度覆寫，其餘另存；兩端範本及兩份寫法 skills 同步，文件契約測試核對邊界 |
| F6 Codex 專案入口缺漏 | project-docs 附共用 AGENTS.md，CLAUDE.md 用 @AGENTS.md 匯入；新專案流程複製兩份，原生範圍附官方來源；範本模擬測試與 Linux Codex 原生診斷確認 |
| F7 官方來源失效 | 改為有效的 Advanced Configuration 與 Non-interactive mode 頁，來源仍支援 CODEX_HOME／exec 敘述；離線契約測試及實際 GET 200 核對，外掛同步 |

## 已完成驗證

- Linux：hooks 57 tests、tools 105 tests，共 162 通過，無略過；一次性測試環境含既有轉檔的 markitdown[docx,pdf]、python-docx、reportlab，含真實 DOCX／PDF 轉換。
- 標籤測試：8 個應擋例、4 個正確派工／等待例，另含狀態、help、list、heredoc、引號範例及 Codex 沒有背景欄位的情況。
- 收尾測試：70% 邊界、缺一／兩份 skill、兩份已讀、同 session 一次、不同 session、缺值／null／NaN、壓縮失效、JSON 輸出、原狀態列轉交、備份／dry-run／重複安裝及更換 Python。
- Codex 的官方 debug prompt-input 已在隔離的無 Git 專案確認舊 CLAUDE 範本未載入、新 AGENTS 範本已載入；它只診斷模型可見輸入，不派推理任務。官方依據見 [developer commands](https://learn.chatgpt.com/docs/developer-commands#codex-debug-prompt-input)。
- Windows shell 選擇以替身驗證；狀態列轉交與 session hook 以實際 Python 子行程、官方格式假輸入驗證，未把替身測試當成 Windows 實測。
- 外掛 56 檔副本核對、官方 claude plugin validate plugin、兩份工具登記表／知識索引及 git diff --check 均通過。
- 去識別掃描只命中本 repo 網址的 4 行；文件落差檢查 0 項，本機文件連結亦納入核對。
- K1b 必讀清單、短派工及 K1 工具回歸均包含於本輪測試；沒有升級維護者 CLI、改主機 hook 設定或替對方設排程。

## 未驗證與第一個接續動作

第一個動作：在目標 Windows 的虛構專案填一份中文任務，確認模型／強度後，以「任務名（模型・強度）」的 description 背景送出／等待；核對面板、--status、result.md 與 summary.json。選用收尾提醒時，先驗證官方 statusLine 來源，再核對 70% 與壓縮後不沿用舊值。

1. Windows 含空白的 Python 路徑、磁碟／UNC 存在檢查、真實 Bash／PowerShell 面板、狀態列與每輪提醒、原指令轉交、npm／Node、分離行程、Job Object、排程器，尚未在實機驗證。
2. Claude 原生 @AGENTS.md 匯入及 Cowork 入口載入本輪未實機驗證；來源與檔案契約已核對。App Bash 的 description 顯示方式是使用者已實測，本 repo 未重做；Cowork／Claude Code App 的 statusLine 用量來源未確認。本套 hook 的真實 context 注入、Codex 信任及 Cowork Python／matcher／工作目錄未端到端實測。
3. Codex UserPromptSubmit 官方機制已確認，對等用量取得／自動收尾及背景 description 畫面未確認；Cowork prompt-audit 與 Codex 專用對等功能未確認。兩端均可人工交辦規則檔審查與交接。
4. gate 不能解析任意程式的全部副作用；未採用、未信任、逾時或缺用量來源，不可當作檢查已生效。必讀注入也不保證 AI 遵守全部原文。
5. mtime 只作落差線索；Claude 企業即時剩餘額度公開 API 未查得。既有 Windows Outlook COM、OCR／GPU 與 Cowork 主機 CLI 登入仍未實測。
