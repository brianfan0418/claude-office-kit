# claude-office-kit 外掛

本目錄由 `tools/build_plugin.py` 產生；維護原始資源後重建，勿直接修改副本。

安裝前先了解使用者工作與環境，逐項決定採用哪些 skills 與 hooks，在封裝副本裁減未採用項目；完整兩種介面用法、官方依據與復原方式見 [採用指南](https://github.com/brianfan0418/claude-office-kit/blob/main/GUIDE-FOR-CLAUDE.md)。

新增工作管理資源見 [工具說明](tools/README-ai-management.md)：模型與額度查詢、CLI 更新及收件匣通知、官方文件下載、背景派工及狀態、文件落差與登記表。模型知識見 [knowledge/codex-models.md](knowledge/codex-models.md)。Codex 與 Claude 均可協助選用，工具不設定排程；執行資料請存授權工作區，維持外掛安裝目錄唯讀。

外掛結構已依官方格式封裝；本套 Python hooks 在 Cowork、Windows COM、主機 Codex 登入與 OCR／GPU 的整合未驗證。轉檔與工具依賴不會自動安裝。
