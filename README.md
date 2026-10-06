# claude-office-kit

讓 Claude 管好自己的工具包：一組給 Claude 讀的規則、技能與安全攔截，使用者只需要對 Claude 說「請讀 `INSTALL-FOR-CLAUDE.md` 並照做」，Claude 會自己完成安裝。

它處理四件事：

- Claude 不再每次開工都忘記前情：進度寫在固定的交接檔，開場自動載入。
- 事實有出處：每個事實陳述附檔案、頁碼或條號、原文引句，找不到就寫「未載明」。
- 做與驗分開：產出者與驗收者是不同的對話，驗收者不帶前情，依完成標準逐項核對。
- 大量或機械性的工作交給 Codex 處理，節省 Claude 額度。

## 適用對象

- Windows 10 或 11。
- 使用 Claude Code，或 Claude 桌面版中使用 Claude Code 的功能（桌面版是否讀取這些檔案未在 Windows 實測）。
- Codex CLI 為選用；沒有 Codex 時，派工改用 Claude 的 subagent。
- 需要 Python 3.8 以上與 Git for Windows；缺少時安裝程序會請使用者同意後安裝。
- 不需要會用命令列：指令由 Claude 執行。

## 使用方式

1. 取得本資料夾（下載壓縮檔，或 `git clone`）。
2. 開啟 Claude Code，對 Claude 說：「請讀這份並照做」，並指向 `INSTALL-FOR-CLAUDE.md`。
3. 依 Claude 的說明回答問題、同意或拒絕各項動作。安裝完成時 Claude 會回報裝了什麼、備份在哪、如何復原。

安裝程序不會覆蓋既有檔案：既有的 `CLAUDE.md` 與 `settings.json` 先備份再合併。

## 目錄

| 路徑 | 內容 |
|---|---|
| `INSTALL-FOR-CLAUDE.md` | 給 Claude 的安裝指示：檢查環境、建立工作資料夾、安裝規則與 skills、掛上 hooks、git 版本控制、驗證 |
| `templates/CLAUDE.md` | 個人規則範本：證據紀律、理解目的、可還原才直接做、對外行為先給草稿、刪除走資源回收筒、做與驗分開、落檔位置、回覆格式 |
| `skills/handoff-docs/` | 寫給 AI 看的文件（規則、交辦、交接單）的寫法 |
| `skills/project-docs/` | 專案固定文件結構與範本（HANDOFF、ROADMAP、CHANGELOG、決策紀錄） |
| `skills/codex-dispatch/` | 在 Windows 上用 `codex exec` 派工與驗收 |
| `skills/maker-checker/` | 做與驗分開的流程與驗收單 |
| `skills/evidence-discipline/` | 證據紀律作業手冊：引用表、自我核對、獨立核對 |
| `hooks/session_start.py` | SessionStart hook：開場載入交接檔前 60 行與未完成待辦 |
| `hooks/block_dangerous.py` | PreToolUse hook：攔截遞迴刪除、格式化磁碟、強制推送、`git reset --hard`、修改 Claude 自己的設定 |
| `hooks/test_block_dangerous.py` | 攔截規則的單元測試 |
| `hooks/install_hooks.py` | 複製 hooks 並合併進 `settings.json`（保留既有設定、先備份） |
| `hooks/settings.example.json` | hooks 設定範例 |
| `contracts/` | 合約與法務管理的內容，見 [contracts/README.md](contracts/README.md) |

## 測試

```powershell
python -m unittest hooks/test_block_dangerous.py
```

## 授權

MIT，全文見 `LICENSE`。
