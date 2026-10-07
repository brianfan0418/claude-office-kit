# 專案工作規則（Codex）

本範本供專案 AI 與使用者依現有制度合併；工作資料夾：`<專案路徑>`。Codex 與 Claude 均可接續、派工與驗收，以文件及驗證證據交接。

- 開場、恢復與壓縮後請核對 `docs/session-start.json` 的載入結果；沒有可用 SessionStart hook 時，先執行工具包 `hooks/session_start.py --cwd <專案> --text --check`，再讀未載入的原文。缺檔先回報影響，補齊前不依該文件決定。
- 請由專案 AI 維護必讀清單：每輪都需遵守的規則、使用者已定案規格加入；過時、撤回或已併入其他文件的項目移出。每項寫明路徑、理由與 full／section／path 模式；section 列唯一標題。
- 寫新腳本前請先查工具登記表（工具包 `tools/REGISTRY.md`、專案 `scripts/REGISTRY.md` 或 `.ai-office/tools/REGISTRY.md`），已有的直接使用；新增後重建登記表。
- 寫規則、skill 或派工前請完整讀取工具包 `handoff-docs`；寫專案交接、決策與規格再讀 `project-docs`。採用 gate 後以成功讀取事件記錄；壓縮後重讀。
- 派工先寫 `tasks/<中文任務名稱>/brief.md` 與 `task.json`，背景命令用 `python dispatch.py 任務名稱`，進度加 `--status`。設定放任務檔；完成後讀 result.md、summary.json 並核對完成標準。
- 每輪結論、決定及修改更新至 `docs/HANDOFF.md`；預設沿用檔案版本制度，只有專案已採用 Git 才提交。
- 事實附原始檔路徑、頁碼或條號；查不到或未驗證就明示。私人文件與登入資料保留私人工作區。
- 寄信、提交表單、公開發布、付款或新增權限時，依使用者授權範圍處理；有阻擋時回報原因，不自行擴大權限。

採用方式及官方依據見工具包 `hooks/README-session-start.md`；讀範本不等於安裝 hook 或設定排程。若兩端共用本檔，Claude 專案 CLAUDE.md 可用原生 `@AGENTS.md` 匯入，Codex 依 AGENTS.md 機制載入。
