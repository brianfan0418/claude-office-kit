# 工具登記表

由 `registry.py tools` 自動產生；修改來源後重跑，請勿手改。

| 工具 | 用途 | 用法 |
|---|---|---|
| [build_plugin.py](build_plugin.py) | 從 repo 的資源原始檔重建外掛副本，不安裝至使用者設定。 | python tools/build_plugin.py [--out plugin] [--check] |
| [claude-quota.py](claude-quota.py) | 提供 Claude 官方用量查詢入口；不把企業歷史用量當作即時剩餘額度。 | python tools/claude-quota.py [--json] |
| [codex-autoupdate.py](codex-autoupdate.py) | 選用的 Codex npm 更新、實測與回退；模型變更更新知識並寫收件匣通知。 | python tools/codex-autoupdate.py --knowledge FILE [--inbox DIR] [--dry-run] [--refresh-only] [--cache FILE] [--codex-home DIR] [--npm-prefix DIR] |
| [codex-queue.py](codex-queue.py) | 選用的資源等待派工：可用記憶體達門檻後送出並等待結果。 | python dispatch.py 任務名稱；資源門檻寫在 task.json 的 min_free／max_wait。 |
| [codex-quota.py](codex-quota.py) | 查詢目前 Codex 登入帳號的官方使用限制；無資料時明示未知。 | python tools/codex-quota.py [--codex-home DIR] [--json] [--timeout 40] |
| [codex-run.py](codex-run.py) | 背景派工給 Codex，保存交辦、事件、回覆、摘要；預設不需 Git。 | python dispatch.py 任務名稱；本檔為派工引擎，對外使用任務資料夾入口。 |
| [codex_rpc.py](codex_rpc.py) | 以官方 Codex App Server stdio 協定查詢帳號限制及模型清單。 | 由 codex-quota.py 與 codex-autoupdate.py import；不讀取或輸出憑證。 |
| [convert_docs.py](convert_docs.py) | convert_docs.py - 把 Word、PDF、Excel、PowerPoint、Markdown 轉成帶 metadata 的 Markdown。 | python convert_docs.py 原檔資料夾 [-o 輸出資料夾]   轉換（增量） |
| [dispatch-status.py](dispatch-status.py) | 列出指定資料夾中的派工狀態、缺報告、失敗與中斷工作。 | python tools/dispatch-status.py [ROOT] [--json] |
| [dispatch.py](dispatch.py) | 以中文任務名稱派工，從任務資料夾讀交辦與設定，保存結果及摘要。 | python dispatch.py 合約欄位整理 [--status\|--wait]；python dispatch.py --list |
| [doc-audit.py](doc-audit.py) | 以修改時間、登記表及本機連結檢查文件落差；Git 檢查可選用。 | python tools/doc-audit.py [ROOT] [--json] [--git] [--grace-seconds 2] |
| [office_common.py](office_common.py) | 工作管理工具共用的 UTF-8、行程、CLI 與互斥鎖功能。 | 由同目錄的工作管理工具 import；不需直接執行。 |
| [official-docs-fetch.py](official-docs-fetch.py) | 將 Anthropic、OpenAI 官方使用建議整批下載，一頁一檔並保留來源清單。 | python tools/official-docs-fetch.py --out DIR [--only claude-code,claude-platform,openai-codex,openai-api] [--workers 4] |
| [outlook-watch.py](outlook-watch.py) | 以 Outlook 傳統版 COM 唯讀監看收件匣，新信寫成 JSONL。 | outlook-watch.py [--check] [--output-dir inbox] [--max-body-chars 2000] [--save-attachments] [--first-run-days 1]（--check 只檢查能否連上 Outlook 傳統版） |
| [registry.py](registry.py) | 從 Python 檔頭或知識 frontmatter 產生工具登記表與知識索引。 | python tools/registry.py tools\|knowledge DIR [--check] |
| [win_memory.py](win_memory.py) | 以 Windows Job Object 限制本 worker 與子行程的合計 committed memory。 | python dispatch.py 任務名稱；task.json 的 memory_max 選用，worker 內部 import。 |
