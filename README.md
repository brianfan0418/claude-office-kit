# claude-office-kit

供您與您的 AI 逐項選用的 AI 工作資源目錄，包含規則範本、skills、hooks、文件轉檔、背景派工、模型知識、額度查詢、文件維護與 Outlook 監看。Codex 與 Claude 均可協助選用及使用，取得本 repo 不代表同意安裝全部資源。

建議由您的 AI 讀取 [GUIDE-FOR-CLAUDE.md](GUIDE-FOR-CLAUDE.md)，了解工作內容、Codex App／CLI、Claude Code 或桌面版 Cowork、既有工具與設定，再提出採用建議，由您逐項選擇。既有規則與流程建議先比對，避免重複安裝。

## 資源與適用情境

| 資源 | 用途 | 適用情境 |
|---|---|---|
| [CLAUDE 範本](templates/CLAUDE.md)、[AGENTS 範本](templates/AGENTS.md) | 證據、授權、落檔、必讀維護及先查登記表 | Claude／Codex 依各自原生指示檔採用 |
| [handoff-docs](skills/handoff-docs/SKILL.md) | 撰寫可檢查的規則、交辦與交接文件 | 多次對話接手同一項工作 |
| [project-docs](skills/project-docs/SKILL.md) | 專案文件結構與範本 | 需要追蹤進度、決策與下一步 |
| [evidence-discipline](skills/evidence-discipline/SKILL.md) | 原文引用、查證與核對表 | 正式文件、事實與數字須可追溯 |
| [maker-checker](skills/maker-checker/SKILL.md) | 由另一個不帶前情的對話驗收 | 抽取欄位、審閱與批次修改需要獨立核對 |
| [codex-dispatch](skills/codex-dispatch/SKILL.md) | 在 Windows 派工作業給 Codex | 大量讀檔、批次處理或第二意見，且已有企業訂閱與 CLI |
| [doc-library](skills/doc-library/SKILL.md) | 文件收錄、查詢、OCR 核對與健檢 | 經常查詢 Word、PDF、Excel、PowerPoint |
| [session_start.py](hooks/session_start.py)、[必讀清單](templates/session-start.json) | 依 AI 維護清單載入全文／章節／路徑，檢查缺檔與長度；附工具及工作摘要 | 開場、恢復與壓縮後重新進入狀況，兩端共用 |
| [skill_gate.py](hooks/skill_gate.py)、[說明](hooks/README-session-start.md) | 寫規則、專案文件與派工前檢查寫法 skill 已載入 | 已採用 PreToolUse／PostToolUse hooks 的 Claude／Codex |
| [block_dangerous.py](hooks/block_dangerous.py) | 攔截部分破壞性指令、自身設定修改與前景等待 | AI 有執行指令或改檔權限；仍須搭配平台權限控制，hook 介面依平台驗證 |
| [install_hooks.py](hooks/install_hooks.py)、[Claude 設定](hooks/settings.example.json)、[Codex 設定](hooks/codex-hooks.example.json) | 備份合併開場、防護與寫法 gate；Codex 另需原生信任審閱 | 已決定採用所選平台 hooks；不替對方安裝 |
| [convert_docs.py](tools/convert_docs.py)、[說明](tools/README-convert-docs.md) | 原檔唯讀，產生 Markdown、索引與來源資訊 | 需要全文查詢、引用或合約登錄；先盤點既有 OCR 工具 |
| [outlook-watch.py](tools/outlook-watch.py)、[說明](tools/README-outlook-watch.md) | 在 Windows 以 Outlook COM 監看新信與附件 | 已使用傳統版 Outlook，需供 AI 讀取新信提示 |
| [plugin/](plugin/) | 依官方結構封裝 skills、hooks 與所需工具 | 在 Cowork 使用選定資源；安裝前依指南裁減未採用項目 |
| [build_plugin.py](tools/build_plugin.py) | 從原始檔重建外掛副本 | 維護或封裝外掛，避免副本與原始檔不同步 |
| [Codex 模型知識](knowledge/codex-models.md) | 模型清單、用途、推理強度及帳號／額度觀念 | 需要選模型或維護派工設定 |
| [codex-quota.py](tools/codex-quota.py)、[claude-quota.py](tools/claude-quota.py) | Codex 官方限制查詢；Claude 官方入口與企業 API 限制 | 需要判斷各自帳號用量，查不到時保持未知 |
| [codex-autoupdate.py](tools/codex-autoupdate.py) | npm 升級、實測、回退、模型清單更新及收件匣通知 | 希望維持 CLI 與知識資料，可選用工作排程器 |
| [official-docs-fetch.py](tools/official-docs-fetch.py) | 整批下載 Anthropic／OpenAI 官方建議，一頁一檔 | 希望 AI 讀取本機參考文件，可重跑更新 |
| [dispatch.py](tools/dispatch.py)、[任務範本](templates/tasks/合約欄位整理/task.json) | `python dispatch.py 合約欄位整理`；交辦及設定存任務資料夾，底層沿用 codex-run 引擎 | 背景面板以中文任務名稱辨識，一般非 Git 工作區 |
| [dispatch-status.py](tools/dispatch-status.py) | 派工狀態及缺報告／失敗／中斷總覽 | 跨對話接手與盤點待處理工作 |
| [doc-audit.py](tools/doc-audit.py) | 修改時間、索引及本機連結的落差線索；Git 選用 | 預設不用 Git，仍需核對文件與實況 |
| [registry.py](tools/registry.py)、[工具登記表](tools/REGISTRY.md)、[知識索引](knowledge/INDEX.md) | 從工具檔頭與知識 frontmatter 自動產生索引 | 寫新工具或查既有資源前先查登記表 |

每項資源的「Claude Code 用法」與「Claude 桌面版 Cowork 用法」均列於[指南](GUIDE-FOR-CLAUDE.md)。Python、Codex、OCR 與 Outlook 只在所選資源需要時檢查，如需新增執行環境，建議先說明用途供您選擇。

新增工作管理工具的輸入、官方依據、Windows 指令及工作排程器設定說明集中於[工具說明](tools/README-ai-management.md)。新增程式僅用 Python 標準函式庫，不建立任何排程；是否採用及何時執行，可由您與您的 AI 決定。

開場清單、Claude 的 `@path`、Codex 的 AGENTS.md／SessionStart、寫法 skill gate 與介面限制見 [開場說明](hooks/README-session-start.md)。清單由專案 AI 自行維護，hook 照原文載入；沒有清單仍保留 HANDOFF 行為，每 session 提示建立清單一次。

## 合約資源

合約主檔、登錄／比對／初審 skills、台灣法審閱手冊與面板已拆至獨立 repo：`claude-contract-kit`（請沿用您取得合約工具包的位置）。需要文件轉檔時，可搭配本 repo 的 doc-library；兩個 repo 可以分別使用。

## 驗證

如需驗證，可由您的 AI 在本 repo 根目錄執行：

```text
python3 -m unittest discover -s hooks
python3 -m unittest discover -s tools
python3 tools/build_plugin.py --check
claude plugin validate plugin
```

Windows 可將 `python3` 換成已確認可用的 `python` 或 `py -3`。測試涵蓋範圍與未實測環境見 [docs/HANDOFF.md](docs/HANDOFF.md)。外掛產生器的 `--check` 只比對副本，不修改檔案。

## 授權

MIT，見 [LICENSE](LICENSE)。
