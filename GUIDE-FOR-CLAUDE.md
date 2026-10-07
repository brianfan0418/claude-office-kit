# AI 資源採用建議

本指南供您與您的 AI 參考，建議依您的工作及現有環境選用資源，由您逐項選擇。讀取本指南不授權批次安裝，也不授權寄信、提交表單或公開發布。

Codex 與 Claude 均可協助資源盤點、派工、執行與驗收；以下 Claude Code／Cowork 欄說明的是不同執行環境，資源選擇不預設其中一個 AI 較高或較低。

## 工作與環境的建議盤點

1. 建議詢問工作種類、希望改善的問題、正式文件的核對方式、是否跨對話接手，以及現有規則與文件庫。
2. 建議確認使用的是 Codex App／CLI、Claude Code 或 Claude 桌面版 Cowork；記錄作業系統、可存取的資料夾、企業帳號與管理員允許的功能。檢查現有 skills、hooks、OCR 與 Outlook，不為盤點而安裝軟體。
3. 建議依 README 的適用情境提出一張表：資源、能解決的問題、所需工具、會改動的檔案、備份／復原方式、未查證事項。沒有對應問題的資源不提出安裝建議。
4. 如您方便，可對每項選擇「採用、沿用既有、暫不採用」。只執行已選項目；已有明確採用指示時直接完成其必要步驟，不再次詢問同一項。
5. 建議既有同名 skill 或規則先比對，列出差異；備份後合併已獲同意的內容，不直接用整份範本覆蓋。

## 執行與復原

- 建議Claude Code：可由 Claude／Codex 協助執行命令；先確認工作區與 repo 的絕對路徑。下文 `<office-kit>` 指本 repo，`<工作區>` 指使用者選定的資料夾，實際執行前替換佔位文字。
- 建議採用單一 skill 時，複製完整 `skills/<名稱>/`（含 references 或 templates）至目標專案 `.claude/skills/`；跨專案採用才放使用者 `.claude/skills/`。替換 `<工具包資料夾>` 為 repo 絕對路徑，先備份同名檔案。
- 建議Cowork：先取得使用者對資料夾存取的授權。外掛依下一節裁減，只包含使用者採用的 skills 與 hooks；不能把安裝整個外掛當成逐項選擇的替代。
- 如需寫入設定或新增依賴，建議先列出已選資源所需的具體動作。所需執行環境及帳號登入由您選擇；既有企業版 Claude 與 Codex 的工作派工不另設文件傳送同意步驟。
- 建議完成時以虛構文件驗證所選功能，回報已採用項目、測試證據與未驗證部分。復原時停用外掛／移除本次新增設定，再還原備份；使用者文件保留。

## 各項資源的兩種用法

| 資源 | Claude Code 用法 | Claude 桌面版 Cowork 用法 |
|---|---|---|
| `templates/CLAUDE.md` | 建議依使用者工作填佔位；與既有專案或使用者 `CLAUDE.md` 合併，重開對話核對載入 | 建議由您的 AI 讀取範本，將已採用規則加入使用者核准的 Cowork 指示；自動載入 `CLAUDE.md` 的對等機制未查證，不能宣稱已生效 |
| `handoff-docs` | 建議複製 skill；修改文件前載入，核對指示、證據與待決事項 | 建議選入外掛 `skills/handoff-docs/`；從 skills 清單選用，寫交接文件並檢查 |
| `project-docs` | 建議複製 skill 與 templates；建立缺少的專案文件，沿用已有制度 | 建議選入外掛 `skills/project-docs/`；在授權資料夾建立文件，預設不建立版本控制環境，沿用系統版本與處理紀錄 |
| `evidence-discipline` | 建議複製 skill；產生引用表並核對原檔、頁碼／條號與逐字引句 | 建議選入外掛 `skills/evidence-discipline/`；提供原檔或授權資料夾，以同一引用表驗證；讀不到原檔就標示無法核對 |
| `maker-checker` | 建議複製 skill；由不帶前情的新對話或 subagent 核對完成標準 | 建議選入外掛 `skills/maker-checker/`；另開 Cowork 任務，只提供原檔、產出與標準；本外掛未配置 agents，不宣稱已有自動驗收代理人 |
| `codex-dispatch` | 建議複製 skill；檢查現有 Codex CLI 與登入，用虛構文件測試讀寫與回報落檔 | 建議選入外掛 `skills/codex-dispatch/`；僅在當前環境實際能執行 Codex CLI 時派工；Windows 主機 CLI 與企業登入能否由 Cowork 使用未查證，無法執行時改開獨立任務核對 |
| `doc-library` | 建議複製 skill；先盤點 OCR，再依 `tools/README-convert-docs.md` 收錄、查詢與健檢 | 建議選入外掛 `skills/doc-library/` 與 `tools/`；確認 Python、格式依賴與授權路徑後才轉檔；主機 OCR 與 GPU 可用性未查證 |
| `session_start.py`／`session-start.json` | 建議由專案 AI 維護必讀清單，以全文／章節／路徑載入；附每支工具一句用途與工作摘要；用缺檔／超量示例核對 | 建議保留外掛 SessionStart，複製清單到授權專案；核對工作目錄及 Python，Cowork 未實測 |
| `skill_gate.py`／`hook_state.py` | 建議合併工具事件；檢查寫法 skill，背景派工／等待的 description 須「任務名（模型・強度）」 | 建議保留 gate 並用假輸入核對；Cowork 事件與背景顯示未實測 |
| `wrapup_nudge.py`／`context_status.py` | 建議選用官方 statusLine 用量＋UserPromptSubmit；context 達 70% 且尚缺 skill 時提醒一次收尾，原 statusLine 可沿用 | 用量來源未確認；只保留 hook 不會憑空取得用量，請先核對目標環境 |
| `block_dangerous.py` | 建議合併 `PreToolUse` 設定；用 JSON 假輸入測試阻擋結果，不實際執行破壞性指令 | 建議保留外掛的 `PreToolUse` 事件；以假輸入與平台實際工具名稱核對 matcher；本套攔截範圍在 Cowork 未驗證，不視為完整安全邊界 |
| `install_hooks.py`／設定範例 | 建議先 dry-run；收尾用量選 --with-context-status，備份並轉交既有狀態列；只採用部分時合併所選事件 | 建議由 hooks/hooks.json 載入；外掛不設定主機 statusLine，不執行使用者層安裝器 |
| `convert_docs.py` | 建議依轉檔說明，只安裝選定格式所需依賴；以 `--help`、虛構檔轉換與 `--lint` 驗證 | 建議外掛附轉檔程式與說明；在 Cowork 確認依賴，輸出寫至授權工作資料夾，不寫入外掛安裝目錄 |
| `outlook-watch.py` | 建議依 Outlook 說明在 Windows、傳統版 Outlook 與 pywin32 環境測試；工作排程器由使用者另行選擇 | 建議Cowork 執行 Windows Outlook COM 的能力未查證；若主機已有 inbox，可讀授權的匯出資料夾；外掛不等於 Outlook 連接器，也不安裝排程 |
| `plugin/`／`build_plugin.py` | 建議可用 `claude --plugin-dir "<office-kit>/plugin"` 測試；已有單獨 skills／hooks 時先避免重複載入 | 建議依下一節裁減與封裝後，上傳自訂外掛；可沿用您目前的介面 |
| `knowledge/codex-models.md` | 建議由任一 AI 依官方來源及日期選模型，知識可複製到私人工作區 | 建議選入外掛 `knowledge/` 供查閱；需自動更新時另複製到授權工作區，外掛副本維持唯讀 |
| `codex-quota.py`／`claude-quota.py` | 建議查目前 Codex 登入帳號；Claude 查 `/usage`，企業即時剩餘額度 API 未查得 | 建議先核對能否存取主機 CLI；不能執行時使用產品 Usage 畫面，不以空值代替剩餘額度 |
| `codex-autoupdate.py` | 建議先 dry-run，再按工具說明選用升級與收件匣通知；不自動設排程 | 建議由主機上的 Codex／Claude 管理 CLI 更新；Cowork 內存取主機 npm 與登入尚未驗證，知識請更新私人工作區副本 |
| `official-docs-fetch.py` | 建議下載到私人參考目錄；重跑更新，先看 manifest 的成功／失敗及日期 | 建議僅在當前環境有 Python 及網路時下載到授權資料夾；也可讀取主機已下載文件 |
| `dispatch.py`／任務範本／派工引擎 | 建議部署入口，交辦／設定存 tasks；背景畫面由 description 顯示「任務名（模型・強度）」；結果另驗收 | 建議僅在實際可執行 CLI 時採用；短指令供執行，背景畫面機制與 Windows 主機整合未驗證 |
| `doc-audit.py` | 建議以修改時間及本機連結核對文件落差，Git 檢查選用 | 建議對授權工作資料夾執行；修改時間只作線索，不自動改寫使用者文件 |
| `registry.py`／`REGISTRY.md`／`INDEX.md` | 建議寫新工具前先查登記表，修改檔頭或 frontmatter 後重建 | 建議查閱外掛附的登記表及知識索引；私人新增資源的索引寫在工作區，不修改安裝副本 |

以上新增工具的指令、來源與 Windows 排程器說明見 [README-ai-management.md](tools/README-ai-management.md)。建議先以虛構工作驗證選定項目，再由您與 AI 決定是否排程；本工具包及外掛都不建立排程。

## Codex 與 Claude 的開場支援

兩端可用同一 `docs/session-start.json`、工具摘要及寫法檢查。建議 Codex 合併 [AGENTS 範本](templates/AGENTS.md)，Claude 合併 [CLAUDE 範本](templates/CLAUDE.md)；共用規則可由 Claude 用原生 `@AGENTS.md` 匯入。Codex 已有 SessionStart／PreToolUse／PostToolUse，安裝器選 `--platform codex`，在 `/hooks` 審閱及信任；不假設 Codex 解析 Claude 的 `@path`。官方依據、長度設定、手動備援及缺檔處理見 [開場說明](hooks/README-session-start.md)。

寫新腳本前建議查開場所列登記表；寫規則、skill 及派工前完整載入 handoff-docs，專案文件另讀 project-docs。清單由 AI 依現行規則與定案自行增減，hook 不替它挑文件。採用本地 skills 時 Claude 用 `.claude/skills`，Codex 用 `.agents/skills`，亦可直接讀原檔；兩端派工均用任務名稱短指令。

Claude Code 背景派工與背景等待，建議把工具 description 寫成「合約欄位整理（gpt-6.1-sol・high）」這種「任務名（模型・強度）」；設定核對後再填，短指令只供執行，畫面給人看的內容是描述。Bash App 顯示方式為本次使用者已實測，Codex 對等畫面未確認。收尾提醒、官方用量來源、既有狀態列的合併／復原與未實測介面，統一見 [開場說明](hooks/README-session-start.md)。

## 建議執行官方規則檔審查

供協助採用的 AI 參考，查閱日期：2026-10-07。建議請使用者在 Claude Code v2.1.283 以上的對話執行 `/doctor prompt-audit`，別名是 `/checkup prompt-audit`；這不是終端的 `claude doctor`。它檢查為舊模型寫的指示、不存在的檔案或指令，以及互相矛盾的規則檔，先提出報告與建議修改，使用者同意後才改檔。[官方記憶文件](https://code.claude.com/docs/en/memory#audit-your-instruction-files)、[官方命令說明](https://code.claude.com/docs/en/commands)

預設範圍是 CLAUDE.md、CLAUDE.local.md、AGENTS.md，以及專案 `.claude/` 與使用者 `~/.claude/` 下的 rules、skills、commands、subagents、output styles。若想先核對單一文件或資料夾，可指定路徑，例如：

~~~text
/doctor prompt-audit .claude/skills/某技能
~~~

審查經由內建 `/claude-api` skill 執行；skillOverrides 關閉該 skill，或設定 disableBundledSkills 時無法使用。若不可用，建議先確認版本與設定，依企業管理制度處理，不自行改管理員設定。[官方使用限制](https://code.claude.com/docs/en/memory#audit-your-instruction-files)

Cowork 是否支援這個內建命令尚未確認。[Cowork 外掛文件](https://support.claude.com/en/articles/13837440-use-plugins-in-claude)確認外掛 skills／commands 可使用，但未證明 Claude Code 的這個內建命令可用。Codex 的專用對等功能亦未確認；[官方 developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli)的 /review 是程式審查，不能當成同一功能。可請 Codex 或 Claude 直接讀已授權的規則檔，先列問題、來源與建議，依既有修改授權處理；這是人工交辦方式。OpenAI 也建議隨模型更替重新審查 skills、AGENTS.md 及提示，見[官方指示檔整理建議](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)。

## Cowork 外掛結構與封裝

查閱日期：2026-10-07。依 [Anthropic 外掛製作 skill](https://github.com/anthropics/knowledge-work-plugins/blob/main/cowork-plugin-management/skills/create-cowork-plugin/SKILL.md) 與 [Claude Code 外掛參考](https://code.claude.com/docs/en/plugins-reference)，目錄為：

```text
plugin/
  .claude-plugin/plugin.json
  skills/<skill-name>/SKILL.md
  hooks/hooks.json
  hooks/session_start.py
  hooks/block_dangerous.py
  hooks/skill_gate.py
  hooks/hook_state.py
  hooks/wrapup_nudge.py
  hooks/context_status.py
  hooks/statusline.example.json
  templates/                必讀清單、CLAUDE／AGENTS 及任務資料夾範本
  tools/                    所附 Python 程式與說明
  knowledge/                模型知識及自動產生索引
  README.md
```

manifest 位於 `.claude-plugin/`，skills 與 hooks 位於外掛根目錄。hook 指令使用 `${CLAUDE_PLUGIN_ROOT}` 定位附帶程式；所需 Python 必須實際存在。本 repo 不封裝憑證、公司文件、帳號設定或主機排程。

如需封裝，建議由您的 AI 協助：

1. 建議執行 `python "<office-kit>/tools/build_plugin.py" --out "<工作區>/待封裝外掛"` 建立完整副本；在該副本移除未採用的 skill 目錄，並從 `hooks/hooks.json` 移除未採用的事件。未採用任何 hook 時移除該設定檔與程式；轉檔、Outlook、工作管理均未採用時可移除 `tools/`。只留部分工具時，建議按工具說明保留相依的 `office_common.py`、`codex_rpc.py`、`registry.py` 與 `win_memory.py`；短派工另需 dispatch.py、codex-run.py、dispatch-status.py；模型知識未採用時可移除 `knowledge/`。
2. 建議用 `claude plugin validate "<工作區>/待封裝外掛"` 驗證；CLI 不可用時核對 manifest JSON、skill frontmatter、hook JSON 與所指檔案。這只能確認結構，不代表 Cowork 已實測。
3. 建議將外掛目錄的「內容」壓成 ZIP，壓縮檔根目錄直接包含 `.claude-plugin/plugin.json`，不要多包一層。依官方製作 skill，ZIP 可命名為 `office-work-kit.plugin`。Windows 壓縮工具須確認包含隱藏目錄 `.claude-plugin/`；使用 Python `zipfile` 可避免漏檔。
4. 建議依 [官方使用說明](https://support.claude.com/en/articles/13837440-use-plugins-in-claude)，在桌面版先進 Cowork，再開 Customize → Plugins，上傳自訂外掛檔；企業限制安裝時由管理員處理。官方支援自訂外掛上傳，本版桌面 UI 的按鈕位置與上傳流程未實測。
5. 建議開啟新任務，從 `/` 或 `+` 的 skills 清單確認已採用技能；依上表驗證。hook 無輸出時先查假輸入結果與執行紀錄，不能直接宣稱防護有效。

[官方說明](https://support.claude.com/en/articles/13837440-use-plugins-in-claude) 已確認 skills 可跨介面使用，hooks 在 Cowork 與 Claude Code 執行，聊天介面不執行 hooks。本套程式的 Python、工具 matcher、工作目錄與 Windows 主機整合仍屬未驗證。

## 合約資源另行選擇

需要合約登錄、比對或初審時，建議閱讀 `claude-contract-kit`（請沿用您取得合約工具包的位置） 的 README，逐項決定採用該 repo 的 skills 與手冊。確認兩個 repo 的本機位置，各自使用根目錄路徑；合約資料放在私人工作資料夾。doc-library 只負責轉檔與查詢，轉檔完成不代表合約欄位已驗證。

AI 若需追蹤自身修改可選用 Git。
