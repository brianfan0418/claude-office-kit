# 交接

最後更新：2026-10-07（K1）

## 現況與決定

本 repo 是供使用者與 Codex／Claude 逐項選用的通用 AI 工作資源，不預設整套安裝或建立排程。交付環境預設不用 Git；AI 可選用 Git 追蹤自身修改。本開發 repo 維持 commit 與 push。

- 合約資源已拆至獨立的 `claude-contract-kit`；請沿用取得該工具包的位置。本輪去識別檢查要求僅保留本 repo 的識別網址，故其他 repo 的作者網址改為資源名稱與檔案位置。
- `README.md`、`GUIDE-FOR-CLAUDE.md` 使用建議語氣，列 Claude Code／Cowork 的使用與未驗證範圍；Codex 與 Claude 均可協助選用、執行及驗收。
- 公司核准的企業版 Claude／Codex 派工不視為對外行為；寄信、提交表單及公開發布仍依使用者工作規則處理。
- 原始資源在 `skills/`、`hooks/`、`tools/`、`knowledge/`；`plugin/` 是 `tools/build_plugin.py` 產生的副本，直接修改會被重建覆寫。外掛名為 `office-work-kit`，本版為 0.2.0。

## K1 資源與參考依據

各項官方網址與操作說明集中於 `tools/README-ai-management.md`。以下本機實作均只參考行為，再改寫為去識別、標準函式庫與 Windows 路徑版本，不保留其帳號、服務或排程。

| 項目 | 本機參考 | 公開版本與決定 |
|---|---|---|
| 模型知識 | codex-cli.md 的模型／額度／派工節、CLI 0.160.1 models_cache.json | knowledge/codex-models.md，日期及可見模型快照；CLI 預設強度與 API 分開說明 |
| 額度 | codex-quota.py、claude-quota.py | 同名工具：Codex 用官方 App Server；Claude 改用官方入口與限制說明，不呼叫非公開 OAuth 端點 |
| CLI 更新 | codex-autoupdate.py | 同名工具：npm 新版升級、短回覆實測、回退核對；清單變動更新知識與 INDEX、UTF-8 收件匣通知；不改預設模型 |
| 官方文件 | official-docs-fetch.py | 同名工具：四組官方索引、一頁一檔及 manifest；Claude Code 失效轉址可由官方 llms-full.txt 分頁備援 |
| 派工與總覽 | codex-run.py、codex-queue.py、dispatch-status.py | 同名精簡工具：背景 worker、wait/status、結果與摘要；不用 systemd，Windows Job Object 限制選用 |
| 文件落差 | doc-audit.py | 同名工具：mtime、登記表內容與本機連結；Git 由 --git 啟用；時間只作待核對線索 |
| 登記表 | registry.py | 同名工具：工具 docstring 與單行 frontmatter 產生 REGISTRY／INDEX；外掛表只列實際封裝工具 |
| Hooks | block-dangerous.py 的 FG_WAIT、session-brief.py | block_dangerous.py 去除文字／heredoc 再攔前景等待；session_start.py 有事項才附狀態與落差摘要，同 session 抑制重複 |

新工具的共用依賴為 `office_common.py`、`codex_rpc.py`、`win_memory.py`；選擇部分工具時見採用指南。工具本身不建立 Windows 排程，指南提供選用操作步驟。

## 已完成驗證

- Linux：hooks 18 tests、tools 88 tests 通過，無略過；tools 的一次性環境含 markitdown[docx,pdf]、python-docx、reportlab，包含真實 DOCX／PDF 轉換。Windows Word／Outlook COM 仍使用假物件。
- 新增測試含前景等待該擋／不該擋、開場摘要、背景派工／等待／重複輸出拒絕、UTF-8、查詢逾時、更新／回退／通知、下載失敗保留、文件落差與索引。
- 真實 Codex App Server 模型與額度查詢通過；模型 refresh-only dry-run 通過。模型知識以同一更新程式從必要快取欄位產生；不匯出 identity 等額外欄位。
- 四組官方來源共 554 頁全部取得，含 1 頁官方完整文字版備援；結果以派工交付物的驗證摘要保存，下載原檔在暫存目錄，不進公開 repo。
- 外掛 40 個檔案副本核對及官方 `claude plugin validate plugin` 通過；完整命令輸出保存於本次派工交付物。Markdown 本機連結、登記表與去識別掃描於提交前核對。

## 未驗證與接續動作

第一個可執行動作：在目標 Windows 用虛構交辦驗證已選工具的 submit → wait → result／summary，再重開所選 AI 介面確認 hook 的實際觸發。

1. Windows npm／Node 入口、分離 worker、Job Object、PowerShell 及工作排程器尚未在實機驗證；升級安裝與回退採替身測試，本輪不升級維護者正在使用的 CLI。
2. Cowork 的主機 CLI／企業登入、Python hook matcher、工作目錄、Outlook COM、OCR／GPU 整合未驗證。官方結構驗證通過不表示上述整合已生效。
3. Claude 企業的即時剩餘訂閱額度公開 API 未查得；企業 Analytics API 是延遲用量／成本資料，不能當作即時餘額。本工具只提供官方可用入口，不要求管理員憑證。
4. `mtime` 可能因複製或封裝變動而提示落差，建議人工核對內容；Git 缺少不影響其他檢查。無 hook 提示亦不表示所有檢查通過，直接執行工具可核對結果。
