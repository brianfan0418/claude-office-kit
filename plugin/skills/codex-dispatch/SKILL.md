---
name: codex-dispatch
description: 把工作交給 Codex（OpenAI 的命令列程式工具）執行，以節省 Claude 額度與保留本對話的 context。用在大量讀檔或搜尋、整個資料夾的整理、機械性的批次修改、產出長文件、依規格寫程式、需要另一個模型家族看一遍的情況，包含使用者沒提到 Codex、但工作量大或重複性高的時候。Windows PowerShell 寫法。
---

# 把工作交給 Codex

Codex 是獨立的 AI 程式助理，用 `codex exec` 可以非互動地執行一份交辦，做完把結果寫成檔案。它不消耗 Claude 額度，也不佔用本對話的 context。

本檔的指令旗標已對照 `codex exec --help`（CLI 0.160.1，在 Linux 查證）。標註「未在 Windows 實測」的部分是依官方文件與 PowerShell 行為推得，第一次使用時要自己驗證，驗證後把實際結果改寫進本檔。

公司核准的企業版 Claude 與 Codex 之間派工不視為對外行為，不另設文件傳送同意步驟。寄信、送出表單與公開發布仍依使用者工作規則事先取得同意。

## 什麼時候派

派出：
- 讀很多檔、搜尋整個資料夾、整理大量資料。
- 機械性的批次修改（改檔名、統一格式、轉換檔案格式）。
- 依明確規格寫腳本或程式，並執行測試。
- 產出長文件的初稿。
- 需要另一個模型的第二意見（審查你自己的方案前，先請它獨立分析問題，最後才給它看你的方案）。

自己做：
- 寫交辦與讀結果的工作量接近直接做完。
- 執行過程需要依中途發現逐步調整方向。
- 單一檔案的小修改，或一兩個指令就能得到的資訊。

不論派不派，涉及對外寄送、付款、刪除、修改設定的動作都留在本對話，向使用者取得同意後由你執行。

## 前置檢查

```powershell
codex --version
codex login status
```

- 找不到 `codex`：Codex 尚未安裝。說明用途後，請使用者同意再安裝（需要 Node.js：`npm install -g @openai/codex`，未在 Windows 實測）。
- 未登入：執行 `codex login`，瀏覽器會開啟 ChatGPT 登入頁，由使用者本人完成登入。登入遭拒時停止並詢問使用者，不重複嘗試，也不要求使用者把密碼或驗證碼貼給你。
- Codex 使用使用者的 ChatGPT 訂閱額度，額度不足時會回報錯誤；此時改由本對話或 subagent 做。
- Codex 在 Windows 的沙箱行為與 Linux 不同（官方文件另有 Windows 專節），未在 Windows 實測；第一次先派一個小任務確認它能讀寫檔案。

## 派工流程

1. 寫交辦檔，存成 `<工作資料夾>\inbox\codex\<任務名>\brief.md`（格式見下節）。
2. 建立輸出資料夾 `<工作資料夾>\inbox\codex\<任務名>\out\`。
3. 執行：

```powershell
$task = "$env:USERPROFILE\AI工作區\inbox\codex\<任務名>"
codex exec -C "<專案資料夾>" -s workspace-write `
  -o "$task\out\final-message.md" `
  "請完整讀取 $task\brief.md，照裡面的要求執行。交付物寫到 $task\out\，最後的回報寫成三段：做了什麼、證據、沒做或不確定的。"
```

4. 確認結束碼與輸出：

```powershell
$LASTEXITCODE
Get-Content "$task\out\final-message.md"
```

### 旗標

| 旗標 | 用途 |
|---|---|
| `-C <資料夾>` | Codex 的工作根目錄；只給它需要的資料夾，不給整個使用者資料夾 |
| `-s read-only` | 只讀不寫的審查、分析；Codex 無法修改任何檔案 |
| `-s workspace-write` | 允許修改工作根目錄內的檔案；會改檔案的工作用這個 |
| `-o <檔案>` | 把 Codex 最後一則回覆寫進檔案，方便你讀取 |
| `-m <模型>` | 指定模型；不指定就用 Codex 設定檔的預設，可用的模型清單以 Codex 自己的說明為準 |
| `-c model_reasoning_effort=high` | 提高推理強度；判斷類工作（審查、查證）用，機械性工作維持預設 |
| `--search`（放在 `exec` 之前：`codex --search exec ...`） | 允許上網搜尋；只有交辦需要查網路資料時才加 |
| `--json` | 事件流以 JSON 逐行輸出，除錯用 |
| `--skip-git-repo-check` | 工作根目錄不是 git 資料夾時才需要；工作資料夾應已納入 git，一般用不到 |

不加 `-s` 時沿用使用者的 Codex 設定；要寫檔就明確傳 `-s workspace-write`，避免預設值不同造成「做完卻沒改到檔案」。不使用 `--dangerously-bypass-approvals-and-sandbox`，除非使用者明確同意。

### 長時間的工作

超過幾分鐘的工作在背景執行，本對話繼續做別的事：用 Claude Code 的背景執行功能，或：

```powershell
Start-Process -NoNewWindow -FilePath codex -ArgumentList @('exec','-C',$proj,'-s','workspace-write','-o',"$task\out\final-message.md",$prompt) `
  -RedirectStandardOutput "$task\out\stdout.log" -RedirectStandardError "$task\out\stderr.log"
```

（`Start-Process` 寫法未在 Windows 實測；`codex` 若是 `.cmd` 包裝檔，`-FilePath` 要改成 `codex.cmd`。）完成前讀 `final-message.md` 是否存在，不用短間隔反覆輪詢；等待上限設為預估耗時的兩倍以上。

### 中文與編碼

- 把交辦寫成檔案，命令列只放一句「請讀取這個檔案並照做」，避免長篇中文經過 PowerShell 管線傳給外部程式時編碼出錯。
- 交辦檔與輸出一律存成 UTF-8。Windows PowerShell 5.1 預設輸出編碼不是 UTF-8，要用管線傳中文時先執行 `$OutputEncoding = [System.Text.Encoding]::UTF8`（未在 Windows 實測）。
- 用 `Get-Content -Encoding UTF8` 讀取輸出，看到亂碼先查編碼，不要推測檔案內容有問題。

## 交辦的寫法

Codex 沒有本對話的記憶，也沒有你讀過的檔案。交辦檔包含五要素：

```markdown
# <任務名>

## 目標
要做成什麼，以及為什麼。

## 背景
相關檔案的完整路徑、已知的錯誤訊息、已經試過的做法、需遵守的專案規則。

## 限制
- 只能修改：<路徑>
- 不能碰：<路徑或動作>，例如不刪除檔案、不寄信、不修改設定
- 輸出放在：<輸出資料夾>
- 中間檔放在輸出資料夾的 scratch\ 底下

## 完成標準
- 執行 <指令>，預期結果是 <結果>
- 交付物清單：<檔案與內容要求>

## 停止條件
遇到下列情況停下並回報，不要自己決定：需要刪除檔案、需要修改共用設定、
需要使用者同意、證據不足無法判斷、同一個錯誤試兩次沒有新資訊。

## 回報格式
三段：做了什麼（檔案清單）、證據（執行的指令與輸出重點，失敗的輸出照貼）、沒做或不確定的。
長內容寫成檔案，回報只放路徑。標出「查不到、沒驗證」的部分，不要編造。
```

撰寫原則：
- 給目標與完成標準，不逐步規定做法；只有流程本身是要求時才列步驟。
- 研究與調查類的交辦，額外寫明：最後要支持什麼判斷、必答問題（條列）、範圍（時間、版本、包含與不包含）、證據要求。沒有邊界的交辦只會得到淺薄的回報。
- 規則沒寫、而這次必須遵守的限制才寫進交辦；Codex 會讀專案資料夾裡的 `AGENTS.md`，需要它遵守的專案規則放在那裡。
- 兩個 Codex 任務同時執行時，各自指定不同的輸出資料夾，避免互相覆蓋。
- Codex 執行期間不要修改它正在讀的檔案；要改就等它結束，或在複製的資料夾改。

## 驗收

收到結果不等於完成。照 skill `maker-checker`：

1. 逐項對照交辦的完成標準，看證據而不是看「已完成」的宣告。
2. 關鍵事實自己抽查：打開產出的檔案、重跑它報告的測試指令。
3. 回報「查無」「沒有」「無法判定」的，派另一個新的 Codex 或 subagent 回原始資料查證；這類陳述取決於查詢範圍是否正確，報告內看不出對錯。
4. 有缺口時，用 `codex exec resume --last` 接續同一段對話只補缺的部分（`resume` 保留它的紀錄，不必重查），附上缺什麼。
5. 同一件事原樣重試不超過兩輪；第三次前換方法、換模型或換問題定義，仍失敗就回報使用者。

## 失敗時

| 現象 | 處理 |
|---|---|
| 結束碼不是 0 | 讀 `stderr.log` 或終端輸出的最後 30 行，把原文貼給使用者，不摘要 |
| 驗證失敗（401、未登入） | 停止，請使用者重新登入；不重複嘗試 |
| 逾時、中斷、不確定有沒有改到檔案 | 不重複派工；先用 `git status` 與 `git diff` 查實際狀態，確認沒生效才重做 |
| 改到不該改的檔案 | `git restore <檔案>` 還原，向使用者說明，修改交辦的限制後再派 |
| 亂碼 | 見「中文與編碼」 |
