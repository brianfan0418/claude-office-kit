---
name: project-docs
description: 專案固定文件標準（CLAUDE.md、README、HANDOFF、ROADMAP、CHANGELOG、decisions、specs）。開新專案、開始或結束一段工作、要記錄決策、進度或變更時載入。範本在 templates 資料夾。
---

# 專案文件標準

原則：每種資訊只有一個家；檔案少而固定，需要才建；讀的人是沒有記憶的下一個 AI。寫法細節照 skill `handoff-docs`。

## 固定結構

```
<專案>\
  CLAUDE.md              必備｜AI 入口：專案一句話、常用指令、規則、按需檔索引（150 行內）
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

## 什麼資訊放哪

| 資訊 | 放哪 | 不要放 |
|---|---|---|
| 每次都要遵守的規則、踩過的坑 | CLAUDE.md（太長就拆到 docs\ 再從 CLAUDE.md 指過去） | HANDOFF |
| 做到哪、下一步 | HANDOFF.md | CLAUDE.md、CHANGELOG |
| 接下來要做什麼、先後順序 | ROADMAP.md | HANDOFF（只放「正在做的」） |
| 已經做完的變更 | CHANGELOG.md 與系統處理紀錄 | ROADMAP |
| 為什麼選 A 不選 B | decisions\NNNN-*.md | CHANGELOG 只寫一行並連結過去 |
| 單一大功能的需求與設計 | specs\NNN-*\ | ROADMAP 只放一行標題 |
| 金鑰、密碼 | 環境變數或 .env（不納入交付） | 任何 .md |

## 開始一段工作

1. 讀 CLAUDE.md（自動載入）、`docs\HANDOFF.md`，需要時才讀 ROADMAP 或 decisions。
2. HANDOFF 的「最後更新」超過 14 天，建議先用系統處理紀錄與實際檔案確認內容仍然正確。

做的過程：
- 做了方向或架構決定（換套件、改資料結構、放棄某方案）就寫 decisions\。
- 功能大到一個對話做不完，開 specs\NNN-功能\，tasks.md 每項完成才打勾，並寫驗證方式。

## 結束一段工作

對話要結束、或換下一件事之前：
1. 覆寫 HANDOFF.md 成現在的狀態。
2. 完成的變更加到 CHANGELOG.md 最上面。
3. ROADMAP 有項目完成或優先順序變了就更新。
4. 建議保存系統處理紀錄，說明做了什麼；已有版本制度的專案沿用其制度。
5. 建議用 `Get-Content docs\HANDOFF.md -TotalCount 10` 與實際檔案確認真的寫進去。

原因：每段工作都要留下下一個人可以直接接手的乾淨狀態，否則下一個 AI 會重做或誤判已完成。開場的 SessionStart hook 會把 HANDOFF 前 60 行放進 context，所以 HANDOFF 最重要的內容要放在最前面。

## 開新專案

在工作資料夾的 `projects\` 下建專案資料夾，PowerShell 範例（路徑換成實際位置）：

```powershell
$skill = "$env:USERPROFILE\.claude\skills\project-docs\templates"
$proj  = "$env:USERPROFILE\AI工作區\projects\<專案名>"
New-Item -ItemType Directory -Force "$proj\docs" | Out-Null
Copy-Item "$skill\CLAUDE.md" "$proj\CLAUDE.md"
Copy-Item "$skill\HANDOFF.md","$skill\ROADMAP.md","$skill\CHANGELOG.md" "$proj\docs\"
```

範本裡的 `<...>` 全部填掉或刪掉。README.md 寫短的：是什麼、怎麼用。

## 既有專案

已有自己文件制度的專案沿用它的制度，不強行搬家；要改成本標準前先問使用者。

## 範本

`templates\` 內有 CLAUDE.md、HANDOFF.md、ROADMAP.md、CHANGELOG.md、decision.md（決策紀錄）、spec.md、tasks.md。

AI 若需追蹤自身修改可選用 Git。
