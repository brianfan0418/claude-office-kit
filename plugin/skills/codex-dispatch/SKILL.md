---
name: codex-dispatch
description: 在 Windows 將大量讀檔、批次整理、依規格實作或第二意見交給 Codex CLI 執行，保留交辦、事件、結果與摘要。Codex 與 Claude 都可送出及驗收；用在長任務與跨對話接手需要執行記錄時。
---

# 派工執行與記錄

Codex 與 Claude 均可協助執行或驗收工作；這份 skill 提供 Codex CLI 的非互動派工介面。建議依任務與目前環境選擇受派者，並以產出與證據判斷完成。

CLI 旗標依官方[非互動執行](https://learn.chatgpt.com/docs/non-interactive-mode)與 `codex exec --help`（0.160.1，Linux）核對。Windows 分離行程、npm 入口與 Job Object 尚未在實機驗證，建議首次用虛構任務測試。模型與額度見 [codex-models.md](../../knowledge/codex-models.md)；工具行為及官方來源見 [README-ai-management.md](../../tools/README-ai-management.md)。

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

## 任務資料夾與短指令

派工前請完整載入本工具包 handoff-docs，將交辦存入 `tasks/合約欄位整理/brief.md`，帳號目錄、模型、強度、sandbox、網路與記憶體選項存入同資料夾的 `task.json`。設定範本與一次性部署方式見 [工具說明](../../tools/README-ai-management.md)；派工入口與相依工具部署到專案後，從根目錄執行：

```powershell
python dispatch.py 合約欄位整理
python dispatch.py 合約欄位整理 --status
python dispatch.py --list
```

Claude 的背景派工與背景等待，工具呼叫的 description 請填「任務名（模型・強度）」，例如「合約欄位整理（gpt-6.1-sol・high）」；畫面上看到的是任務名與模型強度。請先核對 task.json 與 CLI 選擇，模型 null 時不能猜；描述不放指令或路徑。工具 JSON、hook 檢查及本次使用者的 App 實測依據見 [背景標籤說明](../../hooks/README-session-start.md#背景畫面顯示任務模型與強度)。Codex 對等背景面板與 description 參數未確認，不虛構工具欄位；可在對話用同一描述回報。

短指令是實際執行入口。第一條派出獨立 worker，`ok:true` 表示確認啟動，送出動作結束不代表完成；輸出預設在 `inbox/codex/合約欄位整理/`。既有紀錄保留，新的交辦請用新名稱；未確認啟動先查狀態，不立刻重送。

如需等待，指令仍用任務名稱：

```powershell
python dispatch.py 合約欄位整理 --wait
```

等待分鐘數由 task.json 的 timeout 讀取；逾時為結束碼 2，worker 繼續。Claude 可用工具的背景執行功能（run_in_background）；Codex 的 Bash hook 只收到 command，無法分辨背景 yield，建議用單次 --status 或在獨立終端等待。前景等待與 sleep 輪詢受防護 hook 檢查，依據及機制見 [開場說明](../../hooks/README-session-start.md)。

完成後請讀 summary.json 與 result.md，核對交付物及完成標準；`ok:true` 只表示 CLI 成功及回覆存在，不能取代驗收。事件與錯誤在 events.jsonl、stderr.log；設定快照是 task-settings.json。

模型、effort、sandbox、codex_home、search、memory_max、min_free、max_wait 都由任務 JSON 設定，不加到背景命令。read-only 供只讀分析；workspace-write 允許工作區及輸出目錄。背景固定 approval_policy=never，需互動核准的動作會失敗，請交回實際錯誤，不擴大權限。Windows 記憶體上限選用，其他平台設 null；不自動接續、重試或切換帳號。

## 編碼、資料與驗收

交辦與輸出使用 UTF-8，建議用 `Get-Content -Encoding UTF8` 讀取。程式從交辦檔送出內容，避免長篇中文的 PowerShell 管線編碼差異。中間檔放輸出目錄的 `scratch/`，驗收後再決定清理；交付物放其他位置。

派工紀錄與帳號資料建議保留在私人工作區，不納入公開外掛。產出後可依 [maker-checker](../maker-checker/SKILL.md) 由另一個不帶前情的 Codex／Claude 對話核對；若需還原修改，以檔案備份或系統版本為準，Git 可選用。
