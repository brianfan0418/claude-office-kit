---
name: codex-models
description: Codex 的模型用途、推理強度、企業帳號與額度查詢觀念
type: reference
status: current
updated: 2026-10-07
---

# Codex 模型與使用額度

官方資料查閱日：2026-10-07。以下供您與您的 AI 選用；Codex 與 Claude 都可協助判斷任務、執行與驗收，建議依工具可用性、工作需求及公司政策選擇。

## 模型清單與用途

<!-- CODEX-MODELS:BEGIN -->
資料日期：2026-10-07；CLI 版本：0.160.1；來源：models_cache.json（可見條目；本機觀察）。
以下為帳號／客戶端回傳的可見清單快照，企業管理員可限制實際存取。

| 模型 | 回傳的用途描述 | CLI 預設強度 | 支援強度 |
|---|---|---|---|
| gpt-6.1-sol | Latest workhorse model for coding and everyday work. | low | low、medium、high、xhigh、max、ultra |
| gpt-6-astra | Frontier intelligence for the most demanding work. | medium | low、medium、high、xhigh、max、ultra |
| gpt-6-sol | Previous generation workhorse model. | medium | low、medium、high、xhigh、max、ultra |
| gpt-6-luna | Fast and affordable model for easier tasks. | medium | low、medium、high、xhigh、max |
| gpt-5.6-sol | Older generation workhorse model. | low | low、medium、high、xhigh、max、ultra |
| gpt-5.6-terra | Older balanced model for straightforward work. | medium | low、medium、high、xhigh、max、ultra |
| gpt-5.6-luna | Older fast and efficient model. | medium | low、medium、high、xhigh、max |
<!-- CODEX-MODELS:END -->

依 [OpenAI 官方模型說明](https://learn.chatgpt.com/docs/models)，一般跨文件、程式與長時間工作可考慮 `gpt-6.1-sol`；最複雜、需要持續判斷的工作可考慮 `gpt-6-astra`；抽取、分類、轉換與固定格式摘要可考慮 `gpt-6-luna`。表中的上一代與舊世代模型供既有流程參考，建議先以代表性任務比較再更換。

清單以客戶端回傳資料為準，不代表所有企業帳號均已獲准使用。GPT-6.1 Sol 的企業啟用由管理員控制；更新 CLI 不會授予模型權限。隱藏條目不列為日常派工選項；完整清單可由 AI 檢查 `models_cache.json` 的 `visibility`，或使用官方 [`model/list`](https://learn.chatgpt.com/docs/app-server#list-models-modellist) 的 `includeHidden`。

## 推理強度

建議先用 CLI 回傳的預設強度，再按工作調整：`low` 適合範圍明確的小任務，`medium` 適合需要規劃的日常工作，`high`／`xhigh` 可用於多來源核對、複雜審閱及取捨分析。`max` 增加單項工作的推理時間；`ultra` 可將複雜任務分交代理人並行。一般工作不必預設選最高強度，Luna 不支援 Ultra。[官方選擇說明](https://learn.chatgpt.com/docs/models#pick-a-reasoning-effort)

派工設定請寫入任務資料夾的 task.json，背景命令只保留名稱；以下可由 Codex 或 Claude 協助填妥：

```json
{"version": 1, "model": "gpt-6.1-sol", "effort": "high", "sandbox": "read-only"}
```

寫好同資料夾 brief.md 並部署專案入口後，用 `python dispatch.py 文件核對` 送出、加 `--status` 查進度。完整任務格式與來源見 [工具說明](../tools/README-ai-management.md)。

建議只使用表中該模型支援的強度。CLI 的 `model_reasoning_effort`、OpenAI API 的 `reasoning.effort`、Claude 的推理控制不是共同刻度；名稱相同也不能推定效果或預設值相同。此檔的預設欄是 CLI 觀察值，API 請另查[推理文件](https://developers.openai.com/api/docs/guides/reasoning)。

## 帳號與額度

Codex 可以透過 ChatGPT 帳號登入或 API 金鑰使用。企業模型、功能及用量取決於登入方式、方案與工作區設定；API 的用量及計費不能當成 ChatGPT 訂閱剩餘額度。企業費率與信用額度請依合約及管理介面核對，不從個人方案推算。[官方用量說明](https://learn.chatgpt.com/docs/pricing)

建議先用 `codex login status` 確認登入狀態；`CODEX_HOME` 可指定不同的本機設定與登入資料位置，但本工具包不自動切換帳號，也不搬移憑證。是否採用多帳號由您與公司決定。[官方設定說明](https://learn.chatgpt.com/docs/config-basics)

目前帳號的限制視窗可由 [codex-quota.py](../tools/codex-quota.py) 呼叫官方 `account/rateLimits/read` 取得。可能有多個模型額度桶、不同長度的視窗或空值；建議依回傳的視窗長度與重置時間解讀。無資料代表查不到，不能當成 0% 已用或無限額度。本機 token 紀錄也不等於企業帳單。[App Server 帳號介面](https://learn.chatgpt.com/docs/app-server)

Claude 的對應查詢入口與企業限制說明見 [claude-quota.py](../tools/claude-quota.py) 及[工作管理工具說明](../tools/README-ai-management.md)。工作可在兩個 AI 之間分配，各自的用量仍依其帳號計算。

## 如何更新此檔

建議由您的 AI 執行 [codex-autoupdate.py](../tools/codex-autoupdate.py)，以 `--knowledge` 指向已採用的這份文件。程式從官方 App Server 取得可見模型，只替換 `CODEX-MODELS` 標記內的清單、更新 frontmatter 日期、重建同目錄 `INDEX.md`，並在指定收件匣寫通知；新模型用途未回傳時標示「未提供」，供後續查官方說明。

CLI 快取格式觀察：頂層含 `fetched_at`、`client_version`、`models`；模型條目使用 `slug`、`description`、`visibility`、`default_reasoning_level`、`supported_reasoning_levels[].effort`。格式不是穩定公開 API；本工具只匯出上述必要欄位，不匯出快取的其他頂層資料。若需從既有快取產生離線快照，可用 `--refresh-only --cache <檔案>`；日期沿用快取的 `fetched_at`，不是執行日。

程式與 Windows 工作排程器的設定範例見[工具說明](../tools/README-ai-management.md)。本工具包不建立排程，是否採用及執行頻率可由您與您的 AI 決定。
