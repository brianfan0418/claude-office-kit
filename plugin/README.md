# claude-office-kit 外掛

本目錄由 `tools/build_plugin.py` 產生；維護原始資源後重建，勿直接修改副本。

安裝前先了解使用者工作與環境，逐項決定採用哪些 skills 與 hooks，在封裝副本裁減未採用項目；完整兩種介面用法、官方依據與復原方式見 [採用指南](https://github.com/brianfan0418/claude-office-kit/blob/main/GUIDE-FOR-CLAUDE.md)。

新增工作管理資源見 [工具說明](tools/README-ai-management.md)：模型與額度查詢、CLI 更新及收件匣通知、官方文件下載、背景派工及狀態、文件落差與登記表。模型知識見 [knowledge/codex-models.md](knowledge/codex-models.md)。必讀清單、工具摘要、寫法 skill gate、背景標籤與 context 收尾提醒見 [開場說明](hooks/README-session-start.md)；[templates/](templates/) 附 JSON 清單、CLAUDE／AGENTS 範本及中文任務資料夾。Claude 背景畫面以 description 顯示「任務名（模型・強度）」，交辦及設定由任務檔讀取；Codex 對應畫面未確認。收尾提醒需另採用官方 statusLine 用量來源，外掛不代為設定。規則檔審查建議見採用指南的 prompt-audit 節。Codex 與 Claude 均可協助選用，工具不設定排程；執行資料請存授權工作區，維持外掛安裝目錄唯讀。

外掛結構已依官方格式封裝；本套 Python hooks 在 Cowork、Windows COM、主機 Codex 登入與 OCR／GPU 的整合未驗證。轉檔與工具依賴不會自動安裝。
