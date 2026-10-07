---
name: codex-dispatch
description: 在 Windows 將大量讀檔、批次整理、依規格實作或第二意見交給 Codex CLI 執行，保留交辦、事件、結果與摘要。Codex 與 Claude 都可送出及驗收；用在長任務與跨對話接手需要執行記錄時。
---

# 派工執行與記錄

Codex 與 Claude 均可協助執行或驗收工作；這份 skill 提供 Codex CLI 的非互動派工介面。建議依任務與目前環境選擇受派者，並以產出與證據判斷完成。

CLI 旗標依官方[非互動執行](https://learn.chatgpt.com/docs/noninteractive)與 `codex exec --help`（0.160.1，Linux）核對。Windows 分離行程、npm 入口與 Job Object 尚未在實機驗證，建議首次用虛構任務測試。模型與額度見 [codex-models.md](../../knowledge/codex-models.md)；工具行為及官方來源見 [README-ai-management.md](../../tools/README-ai-management.md)。

公司核准的企業版 Claude 與 Codex 之間派工不視為對外行為，不另設文件傳送同意步驟。寄信、提交表單與公開發布仍依使用者工作規則取得同意。

## 建議派工的情境

大量讀檔、批次修改、長文件初稿、依規格寫程式與第二意見，可考慮派給另一個任務。交辦與收回的工作量接近直接做完，或須依中途發現持續調整時，可在目前對話處理。

建議將尚需使用者決定的對外寄送、付款、刪除及設定變更留在目前對話；交辦中列明允許的動作與停止條件，不因背景執行擴大授權。

## 前置確認

```powershell
codex --version
codex login status
```

找不到 CLI 時，建議先說明需要 Python、Node.js 及 Codex CLI；由使用者選擇安裝環境。官方 npm 指令為 `npm install -g @openai/codex`。登入由使用者本人完成 `codex login`；認證遭拒時停止，不要求使用者貼密碼或驗證碼。

派工預設一般資料夾，不需要建立 Git。建議先確認本次工作區、輸出目錄與資料範圍；模型權限或額度不足時回報實際錯誤，再由您與使用者選擇後續工作方式。

## 交辦五要素

建議以 UTF-8 寫成 `brief.md`，包含：

1. 目標與原因：結果要能解決什麼問題。
2. 背景：檔案完整路徑、已知錯誤與已試做法；對方沒有本對話的記憶。
3. 範圍：可以改的檔案、授權動作及回報語言。
4. 完成標準：需核對的內容、指令與結果。
5. 停止條件：需新增權限、缺少資料或認證失敗時交回什麼資訊。

第二意見建議先請對方獨立分析問題，再提供自己的方案供比較；交辦不要預先指定想得到的結論。

## 送出、等待與收回

```powershell
python "<工具包資料夾>/tools/codex-run.py" submit `
  --brief "<工作資料夾>/brief.md" --cwd "<工作資料夾>" `
  --out "<工作資料夾>/inbox/codex/task-01" --model gpt-6.1-sol --effort high
```

輸出目錄須尚不存在，由程式建立。建議記下 JSON 的 `id`；只有 `ok:true` 才表示已確認啟動。未確認時先查 `status`，不立刻重送。

```powershell
python "<工具包資料夾>/tools/codex-run.py" status "<工作資料夾>/inbox/codex/task-01"
python "<工具包資料夾>/tools/dispatch-status.py" "<工作資料夾>/inbox/codex" --json
```

需要等待完成時，建議用 AI 工具的背景執行功能（`run_in_background: true`）執行：

```powershell
python "<工具包資料夾>/tools/codex-run.py" wait "<工作資料夾>/inbox/codex/task-01" --timeout 120
```

若目前介面沒有背景執行功能，可在獨立終端等待。前景等待與 sleep 輪詢會由 `block_dangerous.py` 攔截，讓使用者仍能在目前對話提出新資訊。等待逾時結束碼為 2，工作繼續；可稍後查狀態。

完成後建議讀 `summary.json` 與 `result.md`，核對交付物和完成標準；摘要的 `ok:true` 只表示 CLI 成功及最後回覆存在，不能取代文件或程式驗收。事件與錯誤保留於 `events.jsonl`、`stderr.log`；資料缺漏時如實回報。

## 選用參數

| 參數 | 用途 |
|---|---|
| `--model`、`--effort` | 指定模型與其支援強度；不指定則沿用 CLI 設定 |
| `--search` | 交辦需查公開網路資料時選用 |
| `--sandbox read-only` | 只讀分析；最後回覆由 CLI 保存 |
| `--sandbox workspace-write` | 預設；寫入工作區及明列的輸出目錄 |
| `--codex-home` | 使用已核准的帳號目錄；不自動切換帳號 |
| `--memory-max 2G` | Windows 選用的 worker 與子行程合計 committed memory 上限 |

背景任務使用 `approval_policy="never"`，需要互動核准的動作會失敗；請交回實際錯誤，不改用繞過核准的旗標。本版不自動接續或重試失敗任務，可用新交辦引用先前紀錄與已完成產出。

如需先等記憶體達門檻再派出，可背景執行 `codex-queue.py --min-free 3G --max-wait 60` 加相同派工參數。`dispatch-status.py` 或開場 hook 可盤點執行中及需要處理的工作；不以短間隔輪詢取代背景等待。

## 編碼、資料與驗收

交辦與輸出使用 UTF-8，建議用 `Get-Content -Encoding UTF8` 讀取。程式從交辦檔送出內容，避免長篇中文的 PowerShell 管線編碼差異。中間檔放輸出目錄的 `scratch/`，驗收後再決定清理；交付物放其他位置。

派工紀錄與帳號資料建議保留在私人工作區，不納入公開外掛。產出後可依 [maker-checker](../maker-checker/SKILL.md) 由另一個不帶前情的 Codex／Claude 對話核對；若需還原修改，以檔案備份或系統版本為準，Git 可選用。
