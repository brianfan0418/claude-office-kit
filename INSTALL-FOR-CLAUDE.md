# 安裝指示（給 Claude 讀）

使用者只會對你說一句「請讀這份並照做」。你的任務是把本工具包安裝到這台 Windows 電腦，讓你自己之後的工作有固定的規則、技能與安全攔截。

使用者不熟悉命令列。每一步先用白話說明要做什麼、為什麼，再執行；需要使用者決定時，逐項編號、選項用 A、B、C、標出你的建議。不要要求使用者自己開終端機輸入指令，指令由你執行。

## 全程原則

- 不覆蓋、不刪除使用者既有的檔案。要改既有檔案，先另存備份（檔名加 `.bak-日期`），再修改。
- 安裝軟體、修改 `settings.json`、建立資料夾之前，先說明並取得使用者明確同意。同一類動作可一次取得同意。
- 密碼、驗證碼、權杖遭拒時，停止該項並詢問使用者，不重複嘗試。不要求使用者把密碼貼給你。
- 指令結果不明（逾時、中斷）時，不重複執行；先查詢實際狀態。
- 標「未在 Windows 實測」的指令，是依官方文件與 PowerShell 行為寫的；失敗時把錯誤原文貼給使用者，不自行臆測原因，並在最後回報中列出。
- 每一步的「完成」條件都要實際檢查過才算完成，不以「指令沒報錯」代替。
- 指令以 PowerShell 執行。工具包所在資料夾稱為「工具包資料夾」，也就是本檔所在的資料夾。

## 步驟 0：確認工具包資料夾

做法：確認本檔所在資料夾內有 `templates\CLAUDE.md`、`skills\`、`hooks\`。

```powershell
Test-Path templates\CLAUDE.md, skills, hooks\block_dangerous.py
```

完成：三項都是 True。
停下問使用者：缺檔，或你只拿到本檔而沒有整個資料夾。請使用者提供工具包的壓縮檔或 GitHub 網址，下載到 `%USERPROFILE%\claude-office-kit` 後再繼續。

## 步驟 1：檢查環境

逐項檢查並記錄結果：

```powershell
(Get-CimInstance Win32_OperatingSystem).Caption
python --version
git --version
claude --version
codex --version
Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"
Get-Process olk -ErrorAction SilentlyContinue
```

判讀：

| 項目 | 需要 | 判斷 |
|---|---|---|
| Windows | Windows 10 或 11 | Caption 含 Windows 10 或 11 |
| Python | 必要，3.8 以上 | `python --version` 顯示 `Python 3.x`。若出現 Microsoft Store 視窗或沒有輸出，視為未安裝；改試 `py --version`，記下可用的指令名稱（`python` 或 `py`），後面步驟以 `<PY>` 代表 |
| Git for Windows | 必要 | `git --version` 有版本號 |
| Claude Code | 必要 | `claude --version` 有版本號。你本身若在 Claude Code 內執行，視為已安裝。本工具包的 CLAUDE.md、skills、hooks 由 Claude Code 讀取；Claude 桌面版的一般聊天不讀這些檔案，桌面版的 Code 功能是否同樣讀取，未在 Windows 實測 |
| Codex CLI | 選用 | `codex --version` 有版本號；沒有就跳過步驟 7 |
| Outlook 傳統版 | 選用（只有讀 Outlook 郵件的功能需要） | 登錄檔路徑存在，且沒有 `olk` 行程（`olk` 是新版 Outlook）。只有新版 Outlook 時，Outlook 相關功能無法使用，向使用者說明 |

向使用者回報檢查表，缺少的必要項目說明用途，請使用者同意後安裝（`winget` 指令未在 Windows 實測）：

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
```

Codex 需要 Node.js：`winget install -e --id OpenJS.NodeJS.LTS`，再 `npm install -g @openai/codex`；只有使用者同意使用 Codex 時才裝。

安裝完成後，關閉並重新開啟 PowerShell 的環境（或以完整路徑呼叫）再檢查一次，因為新安裝的程式要重新讀取 PATH。

完成：Python、Git、Claude Code 都有版本號；選用項目的狀態已告知使用者。
停下問使用者：`winget` 不存在或安裝失敗；公司電腦禁止安裝軟體（改請使用者洽詢資訊部門，其餘步驟能做的繼續做）。

## 步驟 2：建立工作資料夾

說明：這個資料夾是你和使用者共用的工作區，所有文件、專案與紀錄都放在這裡，之後的版本控制也針對它。

預設位置 `%USERPROFILE%\AI工作區\`。先問使用者要不要用這個名稱與位置（選項 A：用預設，建議；B：使用者指定）。

```powershell
$ws = "$env:USERPROFILE\AI工作區"
New-Item -ItemType Directory -Force "$ws\knowledge","$ws\projects","$ws\inbox","$ws\tools" | Out-Null
```

資料夾內建立兩個檔案（已存在就不覆蓋，改為向使用者說明）：

1. `$ws\CLAUDE.md`，內容：

```markdown
# 工作資料夾

個人規則在 `%USERPROFILE%\.claude\CLAUDE.md`。

- `knowledge\`：跨專案的研究與參考
- `projects\`：各專案，一案一資料夾，文件結構照 skill `project-docs`
- `inbox\`：待處理的檔案；處理完歸檔到對應專案
- `tools\`：共用腳本
- `ops-log.md`：不會留下 git 紀錄的變更紀錄，格式 `日期 [類別] 內容`
```

2. `$ws\ops-log.md`，第一行：`<今天日期> [安裝] 建立工作資料夾與 claude-office-kit`（日期取自 `Get-Date -Format yyyy-MM-dd`）。

完成：`Get-ChildItem $ws` 列出 `knowledge`、`projects`、`inbox`、`tools`、`CLAUDE.md`、`ops-log.md`。
停下問使用者：目標路徑已存在且內容不是空的；路徑含中文造成後續指令失敗（改用英文名稱 `AI-Workspace`，並告知使用者）。

## 步驟 3：設定使用者層級的 CLAUDE.md

說明：這份檔案是你每次開工前都會讀到的個人規則。

先確認 Claude 設定資料夾：預設是 `%USERPROFILE%\.claude\`。若系統設有環境變數 `CLAUDE_CONFIG_DIR`，以它為準（未在 Windows 實測）。後面稱 `$cl`。

```powershell
$cl = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { "$env:USERPROFILE\.claude" }
New-Item -ItemType Directory -Force $cl | Out-Null
Test-Path "$cl\CLAUDE.md"
```

向使用者詢問（一次問完）：
1. 怎麼稱呼您？
2. 您的職務與主要處理的工作？（一句話；用於填寫範本的使用者背景）
3. 您是否熟悉命令列？（不熟悉就在背景欄寫明）

填寫範本 `templates\CLAUDE.md`：只替換這四種預留位置，其餘 `<…>`（例如 `<專案>`）是通用寫法，保持原樣：

| 預留位置 | 填入 |
|---|---|
| `<使用者稱呼>` | 使用者的稱呼 |
| `<工作資料夾路徑>` | 步驟 2 的完整路徑 |
| `<工作資料夾>` | 同上（完整路徑） |
| `<使用者的職務與熟悉的領域；不熟悉命令列時寫明>` | 使用者回答的內容 |

做法：
- `$cl\CLAUDE.md` 不存在：把填好的內容寫入。
- 已存在：先備份為 `CLAUDE.md.bak-<日期>`。然後讀完兩份，向使用者說明合併計畫：保留使用者原有的每一條規則，把範本中原檔沒有涵蓋的章節接在後面；兩邊內容衝突時，列出兩種寫法請使用者選，不自行取捨。合併後的檔案給使用者確認再寫入。

完成：
```powershell
Select-String -Path "$cl\CLAUDE.md" -Pattern '<使用者稱呼>|<工作資料夾路徑>|<工作資料夾>|<使用者的職務'
(Get-Content "$cl\CLAUDE.md").Count
```
第一個指令沒有輸出；檔案行數大於 0，且「證據紀律」章節存在。
停下問使用者：合併時兩邊規則衝突；使用者不確定怎麼回答上面的問題（先用「未填寫」，告知之後可補）。

## 步驟 4：安裝 skills

說明：skill 是你需要時才載入的作業手冊，平時不佔用記憶。核心共 5 個：`handoff-docs`（寫給 AI 看的文件）、`project-docs`（專案文件結構）、`codex-dispatch`（把工作交給 Codex）、`maker-checker`（做與驗分開）、`evidence-discipline`（證據紀律）。

```powershell
$kit = "<工具包資料夾>"
foreach ($s in "handoff-docs","project-docs","codex-dispatch","maker-checker","evidence-discipline") {
  $dst = "$cl\skills\$s"
  if (Test-Path $dst) { "已存在：$s" } else { New-Item -ItemType Directory -Force "$cl\skills" | Out-Null; Copy-Item -Recurse "$kit\skills\$s" $dst; "已安裝：$s" }
}
```

同名 skill 已存在時，不覆蓋：向使用者說明，選項 A：保留原有的（建議）；B：原有的另存 `<名稱>.bak-日期` 後以本工具包的取代。

`contracts\skills\` 底下的 skill 屬於合約與法務功能（說明見 `contracts\README.md`）：向使用者說明用途，使用者需要時以同樣方式安裝。

完成：
```powershell
Get-ChildItem "$cl\skills" -Directory | ForEach-Object { "$($_.Name): " + (Test-Path "$($_.FullName)\SKILL.md") }
```
每個已安裝的 skill 都顯示 True。
停下問使用者：同名 skill 已存在。

## 步驟 5：安裝 hooks

說明：hook 是自動執行的小程式。`session_start.py` 在每次開工時把目前專案的交接檔放進你的記憶；`block_dangerous.py` 在你要執行遞迴刪除、格式化磁碟、強制推送、`git reset --hard`、修改自己的設定檔時先擋下，並請你改用較安全的做法。它們是保護使用者資料的最後一道防線，因為規則寫在文件裡只能靠自覺。

1. 先在工具包資料夾執行測試：

```powershell
Set-Location $kit
<PY> -m unittest hooks/test_block_dangerous.py
```
完成：輸出結尾是 `OK`。失敗時把輸出原文貼給使用者，停止本步驟。

2. 向使用者說明會修改 `settings.json`（備份在同資料夾的 `settings.json.bak-日期`），取得同意後執行安裝腳本。先用 `--dry-run` 看計畫：

```powershell
<PY> hooks\install_hooks.py --claude-dir $cl --python <PY> --dry-run
<PY> hooks\install_hooks.py --claude-dir $cl --python <PY>
```

腳本會複製兩支 hook 到 `$cl\hooks\`，並把設定合併進 `settings.json`：既有的權限與其他 hook 原樣保留，重複執行不會重複加入。`settings.json` 不是合法 JSON 時腳本停止、不改任何檔案（結束碼 2），此時把錯誤原文給使用者看，請使用者決定。設定範例見 `hooks\settings.example.json`。

3. 驗證檔案與設定：

```powershell
Test-Path "$cl\hooks\session_start.py","$cl\hooks\block_dangerous.py"
Get-Content "$cl\settings.json" -Raw | ConvertFrom-Json | Select-Object -ExpandProperty hooks | ConvertTo-Json -Depth 6
```
完成：兩個檔案存在；輸出的 `SessionStart` 與 `PreToolUse` 各有一筆指令，路徑指向 `$cl\hooks\`。

4. 直接執行 hook 驗證行為（不經 Claude Code）：

```powershell
'{"tool_name":"PowerShell","tool_input":{"command":"Remove-Item -Recurse C:\\no-such-folder"}}' | <PY> "$cl\hooks\block_dangerous.py"
'{"tool_name":"PowerShell","tool_input":{"command":"Get-ChildItem"}}' | <PY> "$cl\hooks\block_dangerous.py"
```
完成：第一個輸出一段 JSON，含 `"permissionDecision": "deny"`；第二個沒有輸出。

`session_start.py` 的驗證：在 `$env:TEMP\kit-test\docs\` 建 `HANDOFF.md`（寫幾行文字），執行 `'{"cwd":"<該資料夾>"}' | <PY> "$cl\hooks\session_start.py"`，輸出應是含 `additionalContext` 的 JSON。驗完後逐一移除測試檔案：先 `Remove-Item` 該檔案，再 `Remove-Item` 空的 `docs` 與 `kit-test` 資料夾（不加 `-Recurse`，因為新裝的攔截會擋下遞迴刪除）。

停下問使用者：使用者原有的 hook 設定與本工具包的同一事件衝突，或使用者不同意修改 `settings.json`（則略過本步驟，告知保護功能因此未啟用）。

注意：hook 在新的工作階段才會載入，所以要使用者重新開啟 Claude Code 後，才能做步驟 8 的實際驗證（是否需要重開，未在 Windows 實測）。安裝後，修改 `settings.json` 與 hooks 的 Edit 或 Write 動作會跳出確認視窗，這是設計的保護，不是故障。

## 步驟 6：用 git 管理工作資料夾

說明給使用者聽：「git 是版本紀錄工具。每次提交（commit）就像存一個還原點。AI 如果改壞了檔案，可以退回之前的版本；每次改了什麼、什麼時候改的，也都有紀錄。紀錄只存在這台電腦，不會上傳到網路。」

```powershell
Set-Location $ws
git init
git config user.name
git config user.email
```

若姓名與電子郵件沒有設定，詢問使用者要用什麼名字與信箱（只用於本資料夾的紀錄，不會公開），然後只設定在此資料夾：`git config user.name "<姓名>"`、`git config user.email "<信箱>"`。

建立 `$ws\.gitignore`（已存在就不覆蓋，只補上缺的行）：

```
.env
*.key
*.pem
*.pfx
~$*
Thumbs.db
inbox/codex/**/scratch/
```

提交：

```powershell
git add -A
git commit -m "初始化工作資料夾"
```

完成：`git log --oneline` 至少有一筆；`git status --short` 沒有輸出。
停下問使用者：資料夾內已有大量既有檔案（超過 1000 個檔案或單檔超過 50 MB）時，先問使用者要不要全部納入版本控制。
不要設定遠端（remote）、不要 push；要上傳到網路由使用者決定。

## 步驟 7：Codex（選用）

只有使用者同意使用 Codex 時才做。

```powershell
codex login status
```

未登入就執行 `codex login`，由使用者在瀏覽器完成登入。完成：`codex login status` 顯示已登入。接著照 skill `codex-dispatch` 派一個小任務確認可用，例如請它列出 `$ws` 的資料夾結構並寫到檔案，確認檔案內容正確。登入遭拒時停止並詢問使用者。

## 步驟 8：最終驗證與回報

1. 請使用者關閉並重新開啟 Claude Code，在工作資料夾開新對話。
2. 在 `$ws\projects\` 建一個示範專案 `_範例`（`docs\HANDOFF.md` 寫「示範：下一步是確認安裝完成」），開新對話時，你應該在開場的 context 看到這份交接檔。看不到時，檢查 `settings.json` 的 SessionStart 設定與 Python 指令名稱。
3. 實際測試攔截：請自己在新對話中執行 `Remove-Item -Recurse "$env:TEMP\no-such-folder"`，預期被攔截並收到改用資源回收筒的說明。沒有被攔截時，回到步驟 5 檢查。
4. 示範專案用完後，檔案逐一移除（不用 `-Recurse`），再 `git add -A; git commit -m "移除安裝示範專案"`。
5. 追加一行到 `$ws\ops-log.md`：`<日期> [安裝] 安裝 claude-office-kit：CLAUDE.md、5 個 skills、2 個 hooks、git`，並 commit。

向使用者回報（白話，不超過 15 行）：
- 裝了什麼：CLAUDE.md（位置）、5 個 skills、2 個保護 hooks、工作資料夾與 git。
- 備份在哪：列出所有 `.bak-日期` 檔案。
- 未完成或略過的項目與原因。
- 如何復原：還原 `settings.json.bak-日期`、刪掉 `$cl\hooks\` 內兩支檔案；工作資料夾的變更用 `git log` 與 `git restore` 還原。
- 未在 Windows 實測的項目清單。
- 之後怎麼用：直接說工作內容；要查文件內容時，我會附上檔案、頁碼與原文；大量工作我會建議交給 Codex。

完成：步驟 1 至 6 的完成條件都成立，使用者已收到回報。
