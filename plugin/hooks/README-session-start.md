# 開場必讀清單、派工標籤與收尾提醒

建議由專案內的 Codex 或 Claude 自行維護必讀文件，將每輪都需要遵守的規則與已定案規格加入，將過時、撤回或已併入其他文件的項目移出。hook 只照清單讀取與檢查，不替 AI 選擇文件或摘要條文。官方查閱日期：2026-10-07。

## 清單位置與格式

建議將 [範本](../templates/session-start.json) 複製到專案的 `docs/session-start.json`，依現有文件調整，不把示例路徑當成已建立。採 JSON 是本工具包的設計選擇：人與 AI 都能直接編輯，[Python 標準 json](https://docs.python.org/3/library/json.html) 可解析並保留項目順序，不需 YAML 套件。官方 hook 沒有規定必讀清單的檔名或格式。

~~~json
{
  "version": 1,
  "max_chars": 24000,
  "items": [
    {"path": "docs/HANDOFF.md", "reason": "接續目前工作", "mode": "full"},
    {"path": "docs/規格.md", "reason": "逐條遵守定案", "mode": "section", "section": "已定案條文"},
    {"path": "docs/ROADMAP.md", "reason": "討論優先順序前閱讀", "mode": "path"}
  ]
}
~~~

| 欄位／模式 | 本工具包的行為 |
|---|---|
| `path`、`reason` | 專案內相對路徑與為什麼要讀；可用中文、空白及 Windows 分隔符，建議以 `/` 書寫；不允許跳出專案或絕對路徑 |
| `full` | 全文載入，含逐條定案內容，不由 AI 挑重點 |
| `section` | `section` 填標題文字，不含 `##`；精確比對唯一 ATX 標題，含標題及下層章節原文，到下一個同層／上層標題停止；缺章節／重名會標出 |
| `path` | 列路徑與理由，提醒 AI 使用前讀原檔；仍檢查檔案存在 |
| `max_chars` | 整段 context 字元上限，預設 24000，可設 2048–64000；字元不等於 token |

一份清單至多 100 項、256 KB；單檔超過 2 MB 改列提醒。程式先替路徑與缺檔提示保留空間，全文或章節放不下就改列該路徑，不截斷條文。連路徑與理由都放不下時，列清單入口與問題數，建議縮短理由或調整上限後重讀。

沒有清單時仍讀 HANDOFF 前 60 行與其餘待辦，並提示可以建立清單；相同 session 與專案只提示一次。必讀原文、工具登記表在 startup／resume／clear／compact 都重新載入；有事項的派工／文件落差摘要維持同 session 重複抑制。

工具摘要從專案 `tools/REGISTRY.md`、`scripts/REGISTRY.md`、派工部署的 `.ai-office/tools/REGISTRY.md` 及工具包登記表讀取，每支一行「檔名 — 用途」。超過總長上限時提示查閱入口；完整參數請查原表。專案 AI 寫新腳本前建議先查表，已有的直接使用。

缺檔在 context 標示 `[缺檔]` 及理由，其他項目仍載入。手動核對：

~~~powershell
python "<工具包>/hooks/session_start.py" --cwd "<專案>" --text --check
~~~

`--check` 有缺檔、格式或章節問題時結束碼為 1；一般 hook 回傳 0 與有效 JSON，讓問題進入 context。[Claude SessionStart](https://code.claude.com/docs/en/hooks#sessionstart) 是增加 context 的事件，exit 2 不阻止開場且其 stderr 不會給 Claude。因此請不要將「已注入」解讀為保證 AI 每條遵守；兩端範本另要求處理缺檔與未載入原文後再依該文件工作。

## Claude 與 Codex 對應機制

| 項目 | Claude Code | Codex |
|---|---|---|
| 固定規則 | `CLAUDE.md`，可用 `@path` 匯入全文 | `AGENTS.md`，依官方發現順序載入；不假設支援 `@path` |
| 開場／壓縮 | SessionStart matcher `startup|resume|clear|compact`、`additionalContext` | 同一 matcher 及 context；官方已支援壓縮後、下一次模型請求前注入 |
| 設定 | `.claude/settings.json` | `.codex/hooks.json`；亦支援 inline TOML，本工具包只合併 JSON |
| 寫法 gate | PreToolUse 的 Write／Edit／shell／Agent；PostToolUse 的 Skill／Read／shell | PreToolUse 的 Bash／apply_patch／spawn_agent；PostToolUse 的成功 shell 讀取 |
| 背景派工顯示 | Bash／PowerShell 有 description、run_in_background；App 的 Bash 面板顯示 description 為本次使用者實測 | 對等背景畫面及 description 參數未確認；不因 Bash 別名就假設相同 |
| 每輪收尾 | UserPromptSubmit；官方 statusLine 提供 context 百分比 | UserPromptSubmit 已確認；取得 context 百分比的對應機制未確認 |

依據：[Claude hooks](https://code.claude.com/docs/en/hooks)、[Claude 記憶與匯入](https://code.claude.com/docs/en/memory#import-additional-files)、[Codex hooks](https://learn.chatgpt.com/docs/hooks)、[Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。固定、短且每次需全文的規則，建議沿用原生指示檔；需指定章節、缺檔診斷、長度控制及跨平台同一清單時，建議採本程式。這是依官方機制做出的設計判斷，兩個 AI 採同一份清單。

可先 dry-run 核對；採用後再去掉 `--dry-run`。本 repo 不替對方安裝：

~~~powershell
python "<工具包>/hooks/install_hooks.py" --platform claude --dry-run
python "<工具包>/hooks/install_hooks.py" --platform codex --dry-run
~~~

安裝器備份並合併開場、防護及寫法 gate，複製共用 `hook_state.py`。只選寫法 gate 時，仍請保留 hook_state.py 及 block_dangerous.py，因 gate 重用其 heredoc／引號處理；可以不登記防護 handler。Codex 開場 handler 設 `additionalContextLimit: 0`，由本程式的字元上限控制輸出；官方預設約 2500 token 會將過長內容另存檔並只給預覽。Codex 須在 `/hooks` 審閱及信任新增或修改過的 hook，程式不代為信任，專案設定層亦須受信任。[Codex 官方設定及信任](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)

沒有可用 hook 的介面，可依 [CLAUDE 範本](../templates/CLAUDE.md) 或 [AGENTS 範本](../templates/AGENTS.md) 手動執行同一工具；這是指示要求，不能宣稱已自動注入。Cowork 附外掛 hooks，Python、工具名稱與工作目錄仍需在目標環境核對。

## 寫文件與派工前讀 skill

`skill_gate.py` 在修改 CLAUDE.md／AGENTS.md、skills 內容或規則目錄前查 `handoff-docs`；修改 docs 的 HANDOFF／ROADMAP／CHANGELOG、decisions／specs 與必讀清單時加查 `project-docs`；派工前只查 `handoff-docs`。未載入就擋下並提示讀取，成功載入後同一對話不用重讀；尚未讀取的重試仍會擋下。查狀態、讀檔與一般筆記不擋。

建議 Claude 用 Skill（外掛可能有名稱前綴），或完整 Read 對應 SKILL.md；Codex 可完整 `cat` 或 `Get-Content` 對應 SKILL.md。採用本地 skills 時，Claude 放 `.claude/skills/`，Codex 依[官方 skills 位置](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)放 `.agents/skills/`；一般非 Git 資料夾亦可直接讀工具包中的 skill。

紀錄採兩端官方 PostToolUse，檢查成功結果，不把失敗、指定局部行數、管線摘要或明示截斷的讀取算載入；Codex 官方說明 transcript 格式不穩定，本工具包不解析它。SessionStart 重置標記，壓縮後需重讀；清單若 full 模式完整載入兩份 skills，直接記錄。狀態放 `AI_OFFICE_STATE` 或使用者 `.ai-office-state`，不保存文件內容。

gate 涵蓋上述工具、apply_patch 檔名及常見 shell 寫檔，不宣稱能解析任意程式或外部工具的全部副作用。未安裝、未信任、逾時或平台沒有對應事件時，仍須由指示與平台權限配合。[Claude 逾時行為](https://code.claude.com/docs/en/hooks#timeouts)與[Codex 工具範圍](https://learn.chatgpt.com/docs/hooks#tool-coverage)有明列限制。

## 短派工指令

任務資料夾與中文短指令見 [工作管理工具說明](../tools/README-ai-management.md)。Codex 的 Bash hook 只有 command，無法分辨 unified exec 背景 yield 參數；因此預設短指令派出獨立 worker 後回傳，完成以 `--status` 查詢，`--wait` 留給獨立終端。Claude 背景等待仍可用 `run_in_background`。依據：[官方 handler 原始碼](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/unified_exec/exec_command.rs)的 pre_tool_use_payload。

## 背景畫面顯示任務、模型與強度

建議在 Claude Code 的 Bash／PowerShell 背景派工與背景等待，將工具呼叫的 `description` 寫成「任務名（模型・強度）」：

~~~json
{
  "command": "python dispatch.py 合約欄位整理",
  "run_in_background": true,
  "description": "合約欄位整理（gpt-6.1-sol・high）"
}
~~~

等待時 command 改為 `python dispatch.py 合約欄位整理 --wait`，description 仍相同。這是工具呼叫 JSON，不是 task.json 的欄位。畫面上給人看的內容是任務名與模型強度；短指令只用於實際執行，交辦與設定仍集中在任務資料夾。

依據：[官方 shell 工具欄位](https://code.claude.com/docs/en/hooks#pretooluse-input)包含 description 與 run_in_background；2026-10-07 使用者已實測 Claude Code App 的 Bash 背景面板，有 description 只顯示描述、沒有則顯示整條指令。本 repo 未重做 App 或 PowerShell 面板實測；Codex 的對應畫面與 description 參數未確認，請勿把這項實測延伸到其他介面。

skill_gate.py 先檢查標籤：中文全形括號、中央點 `・`、非空任務名、模型識別字及強度識別字；描述不放指令或路徑。未符合就 deny 並給上述例子，修改後可重試。涵蓋 dispatch.py 派出／--wait、底層 codex-run.py submit／wait 與 codex-queue.py；狀態、help、list、install、heredoc／字串中的示例不攔。不為任意背景命令要求此標籤。

格式檢查不代替設定核對：AI 請先讀 task.json，模型 null 時確認目前 CLI 選擇或明確指定可用模型，再填描述；不將範例當成所有帳號的可用模型。實際送出設定保存在 task-settings.json 與 summary.json，可供驗收。

## context 達 70% 的收尾提醒

[Claude 官方 statusLine](https://code.claude.com/docs/en/statusline#context-window-fields)提供 `session_id`、`context_window.used_percentage` 及 `current_usage`；用量是最近 API 回應的 input context，首次回應前或 /compact 後 current_usage 為 null。[UserPromptSubmit](https://code.claude.com/docs/en/hooks#userpromptsubmit)本身未列用量欄位。因此選用 context_status.py 接收官方 statusLine JSON，僅保存同 session 的百分比、來源與時間；wrapup_nudge.py 於每輪讀取，達 70% 且尚缺任一寫法 skill 時，提醒載入缺少的 handoff-docs／project-docs，將交接文件更新到可接手狀態。

提醒只輸出 additionalContext，不阻擋提交；同對話只提醒一次，即使後來壓縮也不重複。兩份 skills 已成功載入則不提醒；標記沿用 skill gate。SessionStart 使舊用量失效，等待新的 statusLine 數值；缺值、null、損壞或其他來源一律略過，不推算成 0%，也不解析 transcript。狀態放 AI_OFFICE_STATE 或使用者 .ai-office-state，與 gate 使用同一位置。

如決定採用此提醒，可先核對方案，再去掉 --dry-run：

~~~powershell
python "<工具包>/hooks/install_hooks.py" --platform claude --with-context-status --dry-run
~~~

安裝器合併 UserPromptSubmit；只有 --with-context-status 才設定 statusLine。既有狀態列的 command、padding 等設定備存到 hooks/statusline-original.json，接收相同原始 JSON 後轉交原 command（逾時 5 秒），顯示原輸出；再執行不重複包裝。原設定不合法時停止且不改檔。沒有既有狀態列時只顯示 context 百分比；既有 Python 狀態列亦可直接呼叫 context_status.record(data)，或將同一 JSON 傳給 --record-only。範例見 [statusline.example.json](statusline.example.json)，建議合併，不覆蓋整份設定。

轉交原指令在 Windows 依[官方 Windows statusLine 慣例](https://code.claude.com/docs/en/statusline#windows-configuration)尋找 Git Bash，沒有時用 PowerShell；保留原 padding、refreshInterval 等設定。Linux／macOS 用 Bash 或 sh。既有指令須能在所選 shell 執行，這項相容性仍請在目標 Windows 核對。

外掛附 UserPromptSubmit 與兩支程式，但不代為設定主機 statusLine；只採用收尾提醒時請同時保留 hook_state.py，並由 AI 合併 statusLine 的用量來源。未接上來源就不提醒，不能將「沒有提醒」當成低用量。復原可將 statusLine 還原成 statusline-original.json 內容或設定備份，再移除本次 UserPromptSubmit；來源程式保留到復原後才移除。

依 [Codex hooks](https://learn.chatgpt.com/docs/hooks#userpromptsubmit)，Codex 已有每輪事件，但官方 hook 輸入未列相同用量欄位，對等取得／自動提醒方式未確認；安裝器不替 Codex 設 Claude statusLine。Cowork、Claude Code App 是否提供這項 statusLine 來源與本程式的 Windows 整合未實測，採用時請以真實來源核對；兩端都可依範本，在介面明示高 context 時自行整理交接。
