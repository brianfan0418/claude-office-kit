---
name: project-docs
description: 專案固定文件標準（AGENTS.md、CLAUDE.md、README、HANDOFF、ROADMAP、CHANGELOG、decisions、specs）。Codex 與 Claude 開新專案、開始或結束一段工作、要記錄決策、進度或變更時載入。範本在 templates 資料夾。
---

# 專案文件標準

原則：每種資訊只有一個家；檔案少而固定，需要才建；讀的人是沒有記憶的下一個 AI。寫法細節照 skill `handoff-docs`。

## 固定結構

```
<專案>\
  AGENTS.md              共用規則｜Codex 原生入口：專案一句話、常用指令、規則、按需檔索引（150 行內）
  CLAUDE.md              Claude Code 原生入口｜用 @AGENTS.md 匯入同一份規則
  README.md              必備｜專案是什麼、怎麼安裝和執行（給人和 AI）
  docs\
    HANDOFF.md           必備｜現在的狀態：進行中、下一步、卡住、等使用者（80 行內，覆寫不累積）
    ROADMAP.md           必備｜目標與優先順序：Now / Next / Later（是方向，不是承諾）
    CHANGELOG.md         必備｜發生過的重要變更，最新在上，日期 YYYY-MM-DD
    research\            需要才建｜專案研究與評估
    decisions\           需要才建｜架構或方向決策，一個決策一檔 NNNN-標題.md
    specs\NNN-功能\      需要才建｜大功能：spec.md（做什麼、為什麼）、plan.md（怎麼做）、tasks.md（清單）
    runbooks\            需要才建｜重複的操作程序：部署、還原、輪替金鑰
    archive\             需要才建｜過時但想留的文件，搬進來而不是刪
  scripts\               需要才建｜專案專用腳本
```

不先建空的資料夾；需要時才建。

建議兩端共用上述入口，專案規則只維護在 AGENTS.md；Claude Code 由 CLAUDE.md 匯入，Codex 直接讀 AGENTS.md。只用 Codex 時可省略 CLAUDE.md；只用 Claude Code 時仍保留其匯入的 AGENTS.md。這是依 [Codex 指示檔發現機制](https://learn.chatgpt.com/docs/agent-configuration/agents-md) 與 [Claude Code 的 @path 匯入](https://code.claude.com/docs/en/memory#import-additional-files) 做出的範本設計，官方查閱日 2026-10-07。Cowork 自動載入此組入口尚未確認，請在開場明確讀兩份原檔。

## 什麼資訊放哪

| 資訊 | 放哪 | 不要放 |
|---|---|---|
| 每次都要遵守的規則、踩過的坑 | AGENTS.md（太長就拆到 docs\ 再從入口指過去）；CLAUDE.md 只保留匯入與介面專用指示 | HANDOFF |
| 做到哪、下一步 | HANDOFF.md | AGENTS.md、CLAUDE.md、CHANGELOG |
| 接下來要做什麼、先後順序 | ROADMAP.md | HANDOFF（只放「正在做的」） |
| 已經做完的變更 | CHANGELOG.md 與系統處理紀錄 | ROADMAP |
| 為什麼選 A 不選 B | decisions\NNNN-*.md | CHANGELOG 只寫一行並連結過去 |
| 單一大功能的需求與設計 | specs\NNN-*\ | ROADMAP 只放一行標題 |
| 金鑰、密碼 | 環境變數或 .env（不納入交付） | 任何 .md |

## 開始一段工作

1. 核對入口載入：Codex 原生讀 AGENTS.md；Claude Code 原生讀 CLAUDE.md 並匯入 AGENTS.md。首次採用建議請 AI 說出兩項專案規則，與原文核對；未有原生載入的介面請明確讀原檔。
2. 讀 `docs\HANDOFF.md`，需要時才讀 ROADMAP 或 decisions。入口自動載入不代表 HANDOFF 全文也已載入，請核對開場清單結果。
3. HANDOFF 的「最後更新」超過 14 天，建議先用系統處理紀錄與實際檔案確認內容仍然正確。

做的過程：
- 做了方向或架構決定（換套件、改資料結構、放棄某方案）就寫 decisions\。
- 功能大到一個對話做不完，開 specs\NNN-功能\，tasks.md 每項完成才打勾，並寫驗證方式。

## 結束一段工作

對話要結束、或換下一件事之前：
1. 在原路徑覆寫 HANDOFF.md 成現在的狀態。它屬專案文件制度；受版本控制或制度管理的其他文件亦照制度更新並保存規定紀錄，其餘既有文件才另存保留原檔。
2. 完成的變更加到 CHANGELOG.md 最上面。
3. ROADMAP 有項目完成或優先順序變了就更新。
4. 建議保存系統處理紀錄，說明做了什麼；已有版本制度的專案沿用其制度。
5. 建議用 `Get-Content docs\HANDOFF.md -TotalCount 10` 與實際檔案確認真的寫進去。

原因：每段工作都要留下下一個人可以直接接手的乾淨狀態，否則下一個 AI 會重做或誤判已完成。開場 SessionStart hook 依專案 docs/session-start.json 載入全文或指定章節；沒有清單時仍讀 HANDOFF 前 60 行。建議將每輪要遵守的定案規格加入清單，由專案 AI 維護，採用說明見工具包 hooks/README-session-start.md。

## 開新專案

在工作資料夾的 `projects\` 下建專案資料夾，PowerShell 範例（路徑換成實際位置）：

```powershell
$skill = "${CLAUDE_PLUGIN_ROOT}\skills\project-docs\templates"
$proj  = "$env:USERPROFILE\AI工作區\projects\<專案名>"
New-Item -ItemType Directory -Force "$proj\docs" | Out-Null
Copy-Item "$skill\CLAUDE.md" "$proj\CLAUDE.md"
Copy-Item "$skill\AGENTS.md" "$proj\AGENTS.md"
Copy-Item "$skill\HANDOFF.md","$skill\ROADMAP.md","$skill\CHANGELOG.md" "$proj\docs\"
```

範本裡的 `<...>` 全部填掉或刪掉；共用內容填入 AGENTS.md，CLAUDE.md 保留 `@AGENTS.md`。README.md 寫短的：是什麼、怎麼用。若從已安裝的 skill 複製，請將 `$skill` 換成該 skill 的 templates 位置，不預設它只裝在 Claude 目錄。新專案確認兩個入口存在後，依「開始一段工作」核對目標介面的實際載入。

## 既有專案

已有自己文件制度的專案沿用它的制度，不強行搬家；要改成本標準前先問使用者。

## 範本

`templates\` 內有 AGENTS.md、CLAUDE.md、HANDOFF.md、ROADMAP.md、CHANGELOG.md、decision.md（決策紀錄）、spec.md、tasks.md。

AI 若需追蹤自身修改可選用 Git。
