# claude-office-kit

供 Claude 與使用者逐項選用的 AI 工作資源目錄，包含規則範本、skills、hooks、文件轉檔、Codex 派工與 Outlook 監看。取得本 repo 不代表同意安裝全部資源。

先請 Claude 讀 [GUIDE-FOR-CLAUDE.md](GUIDE-FOR-CLAUDE.md)，了解工作內容、Claude Code 或桌面版 Cowork、既有工具與設定，再提出採用建議，由使用者逐項決定。既有規則與流程先比對，避免重複安裝。

## 資源與適用情境

| 資源 | 用途 | 適用情境 |
|---|---|---|
| [規則範本](templates/CLAUDE.md) | 證據、授權、落檔與回覆原則 | 尚無工作規則，或需要整理既有規則 |
| [handoff-docs](skills/handoff-docs/SKILL.md) | 撰寫可檢查的規則、交辦與交接文件 | 多次對話接手同一項工作 |
| [project-docs](skills/project-docs/SKILL.md) | 專案文件結構與範本 | 需要追蹤進度、決策與下一步 |
| [evidence-discipline](skills/evidence-discipline/SKILL.md) | 原文引用、查證與核對表 | 正式文件、事實與數字須可追溯 |
| [maker-checker](skills/maker-checker/SKILL.md) | 由另一個不帶前情的對話驗收 | 抽取欄位、審閱與批次修改需要獨立核對 |
| [codex-dispatch](skills/codex-dispatch/SKILL.md) | 在 Windows 派工作業給 Codex | 大量讀檔、批次處理或第二意見，且已有企業訂閱與 CLI |
| [doc-library](skills/doc-library/SKILL.md) | 文件收錄、查詢、OCR 核對與健檢 | 經常查詢 Word、PDF、Excel、PowerPoint |
| [session_start.py](hooks/session_start.py) | 開場載入交接檔與未完成待辦 | 工作常跨越多個對話 |
| [block_dangerous.py](hooks/block_dangerous.py) | 攔截部分破壞性指令與自身設定修改 | Claude 有執行指令或改檔權限；仍須搭配平台權限控制 |
| [install_hooks.py](hooks/install_hooks.py)、[設定範例](hooks/settings.example.json) | 備份並合併兩個 hooks 的使用者設定 | 使用 Claude Code 且已決定採用兩個 hooks |
| [convert_docs.py](tools/convert_docs.py)、[說明](tools/README-convert-docs.md) | 原檔唯讀，產生 Markdown、索引與來源資訊 | 需要全文查詢、引用或合約登錄；先盤點既有 OCR 工具 |
| [outlook-watch.py](tools/outlook-watch.py)、[說明](tools/README-outlook-watch.md) | 在 Windows 以 Outlook COM 監看新信與附件 | 已使用傳統版 Outlook，需供 Claude 讀取新信提示 |
| [plugin/](plugin/) | 依官方結構封裝 skills、hooks 與所需工具 | 在 Cowork 使用選定資源；安裝前依指南裁減未採用項目 |
| [build_plugin.py](tools/build_plugin.py) | 從原始檔重建外掛副本 | 維護或封裝外掛，避免副本與原始檔不同步 |

每項資源的「Claude Code 用法」與「Claude 桌面版 Cowork 用法」均列於[指南](GUIDE-FOR-CLAUDE.md)。Python、Git、Codex、OCR 與 Outlook 只在所選資源需要時檢查，缺少時先說明用途，由使用者決定是否安裝。

## 合約資源

合約主檔、登錄／比對／初審 skills、台灣法審閱手冊與面板已拆至獨立 repo：[claude-contract-kit](https://github.com/brianfan0418/claude-contract-kit)。需要文件轉檔時，可搭配本 repo 的 doc-library；兩個 repo 可以分別使用。

## 驗證

在本 repo 根目錄執行：

```text
python3 -m unittest discover -s hooks
python3 -m unittest discover -s tools
python3 tools/build_plugin.py --check
claude plugin validate plugin
```

Windows 可將 `python3` 換成已確認可用的 `python` 或 `py -3`。測試涵蓋範圍與未實測環境見 [docs/HANDOFF.md](docs/HANDOFF.md)。外掛產生器的 `--check` 只比對副本，不修改檔案。

## 授權

MIT，見 [LICENSE](LICENSE)。
