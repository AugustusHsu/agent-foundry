---
name: foundry-model-routing
description: 模型供應商路由 workflow。三種情況載入本文：① 撞到模型額度上限、② 要調整哪個角色用哪一家供應商的模型、③ 新增或移除一家供應商。本文負責把「現在有哪幾家可用」「哪個角色該用哪一家」「怎麼實際改過去」收斂成固定五步，含發卡與驗證。不得繞過本文直接改任何 agent 的供應商設定。
---

# foundry-model-routing：模型供應商路由

依 MYL-36 使用者裁定制定（裁定卡 `ask:MYL-36:platform-routing:v1`）。使用者給的目的原文：

> 「有不同服務商提供的模型會有不同觀點，可以補足，通常我是希望 review 跟寫 code 的 agent 用不同的模型」
>
> 「應該要有一個 workflow 知道跟處理目前能使用的平台模型，如果額度耗盡或是想要更改可以透過這個
> workflow 自動指派，目前 paperclip 先不實際改任何 agent 設定，提供這樣的功能即可」

所以本 workflow 的目標**不是省額度、也不是拚吞吐**，是**觀點互補**：讓寫 code 的和審 code 的
來自不同供應商，避免同一個模型的盲點在實作與審查兩端同時發生（規則本體＝protocol `M4`）。

## 0. 先分清兩條軸，別混

| 軸 | 管什麼 | 由誰定義 | 值 |
| --- | --- | --- | --- |
| **執行層平台** | 工單／狀態／看板放在哪 | `foundry-platform` ＋ `.foundry/config.yml` 的 `platform` | `github`／`local-md`／`paperclip` |
| **模型供應商** | 哪一家的模型在跑這個角色 | **本文** ＋ `.foundry/config.yml` 的 `model_routing` | `claude`／`codex`／`gemini`… |

兩者都曾被口語叫成「平台」，但換供應商不會換掉工單系統，換工單系統也不會換掉供應商。
**本文一律用「供應商」**；看到舊文件寫「平台路由」指的是本文這條軸。

## 1. 什麼時候跑

| 觸發 | 情境 | 進入點 |
| --- | --- | --- |
| `MR-1` **額度耗盡** | 某供應商回報額度／用量上限，工作跑不下去 | 步驟 1，並依 protocol `M5` 處置 |
| `MR-2` **調整路由** | 想改哪個角色用哪一家（含首次啟用路由） | 步驟 1 |
| `MR-3` **供應商增減** | 裝了新的 CLI、或某家不再使用 | 步驟 1，跑完更新登記表 |

不屬於本文範圍：同一供應商內的**層級與思考程度**升降（那是 protocol 第 8 節 `M1`～`M3`，
個案由執行者自行判定，不必跑本 workflow）。

## 2. 五個步驟

### 2.1 盤點：現在有哪幾家真的可用（機械層，不靠判斷）

```bash
python3 tools/model-routing/probe_providers.py            # markdown 表，可直接貼進工單留言
python3 tools/model-routing/probe_providers.py --format json
```

判定只看兩件可驗證的事：CLI 在不在 `PATH`、憑證檔在不在。輸出四種狀態：
`✅ 可用`／`⚠️ 已安裝、未登入`／`❓ 已安裝、登入狀態不明`／`— 未安裝`。

- **「平台欄位可以填某個值」不等於「那家可用」。** MYL-36 分析階段就犯過這個錯：
  Paperclip 的 `adapterType` 枚舉列了七、八家，實機只有兩家裝了。**一律以本步驟的輸出為準。**
- 盤點結果**不得憑印象填寫**，要附腳本輸出當證據。

### 2.2 讀現況：每個角色目前用哪一家

- **路由設定**：`.foundry/config.yml` 的 `model_routing` 段（schema 見
  `skills/foundry-platform/config-schema.md`）。整段缺席＝路由未啟用＝全隊都用預設供應商。
- **平台實況**：依 `.foundry/config.yml` 的 `platform` 查（見 §4）。
- **設定與實況不一致時以設定為準並發起同步**，不是改設定遷就現況（同 protocol 第 8、9 節的權威來源規則）。

### 2.3 產生指派方案：套政策，不即興

依 §3 的政策表算出「角色 → 供應商」對照表。方案必須同時列出：
每個角色的**現值 → 目標值**、變更理由、以及 `M4` 是否成立（實作與審查是否異廠）。

### 2.4 發卡：這一步不能自己決定

換供應商屬公司層設定變更，觸發 protocol `H6`，規則本體是 `M6`：
**本 workflow 只負責盤點、產方案、發卡、執行、驗證，不負責決定。**

卡片內容至少包含：盤點輸出、現值→目標值對照表、`M4` 成立與否、回退方式（改回原值即可，無資料遷移）。
發卡後依 protocol 第 4 節轉 `blocked` 等回覆——**不得先改再問**。

> 現況：**沒有常設授權**。使用者若要授予（類比 push 的 `P1`／`P2` 分級），走規範修訂在此登記，
> 未登記前每次都要發卡。

### 2.5 核可後：執行並驗證

依 §4 對應平台執行指派，然後**逐項回查**（不看指令回報成功，看查詢結果）：

- 平台側該 agent 的供應商欄位＝目標值。
- 該角色下一次執行確實跑在新供應商上（看 run 記錄或 CLI 版本輸出）。
- 把「角色 → 供應商」寫回 `.foundry/config.yml` 的 `model_routing`（由使用者或對應 workflow 寫入，
  agent 不得自行改本檔）。
- 工單留言留下證據：盤點輸出、卡片核可紀錄、平台回查結果。

## 3. 路由政策

### 3.1 角色 × 工作性質 → 供應商

政策的判準是**工作性質**，不是「哪家比較強」——後者會隨版本翻盤，前者不會。

| 工作性質 | 角色 | 對供應商的要求 |
| --- | --- | --- |
| 需即時來回互動、需求探索 | CEO、Product Analyst | 互動延遲低、能追問；**留在使用者慣用的那家** |
| 跨檔案推理、設計 | Tech Lead | 長上下文、跨檔案推理 |
| 規格明確的實作 | Developer | 可批量、非同步；**與審查方異廠**（`M4`） |
| 審查 | Code Reviewer | 與實作方異廠（`M4`），這是本 workflow 的主要動機 |
| 補測試／跑測試 | QA Engineer | 產出可機械驗證，異廠風險低 |
| 機械性流轉 | Scrum Master | 規格明確，對供應商最不敏感 |

### 3.2 硬約束

- `M4` **實作與審查異廠**（protocol 第 8 節）：可用供應商 ≥2 且路由已啟用時，
  同一張工單的 Developer 與 Code Reviewer 不得是同一家。
- **一次只換一個角色**，跑完一輪再擴大——換供應商的退步（品質下降、格式不合）
  往往要跑幾張單才看得出來，一次全換會分不清是哪一項改動造成的。
- **角色規範怎麼載入要先確認**：Foundry 的 skill 是 `SKILL.md` ＋ frontmatter 格式。
  換到非 Claude 的供應商時，角色規範靠 repo 根的 `AGENTS.md`（雙入口檔）進 context——
  **目標專案沒有 `AGENTS.md` 就先補，這是換供應商的硬前置**。

### 3.3 現況（2026-09-03）

- 盤點：`claude`、`codex` 兩家可用（實機驗證，見 §2.1 腳本輸出）。
- 路由：**未啟用**。7 個 agent 全部在 `claude_local`；使用者裁定「先不實際改任何 agent 設定」。
- 因此 `M4` **條件成立但尚未生效**——可用供應商夠了，但沒有任何角色被指派到第二家。
  這是使用者知情下的狀態，不是待辦缺陷（見 `docs/standards/known-drift.md` `R6`）。

## 4. 各平台怎麼落實指派

執行層平台不同，「指派供應商」這個動作的落點也不同。

### paperclip

```bash
PAPERCLIP_API_BASE="${PAPERCLIP_API_URL%/}"; PAPERCLIP_API_BASE="${PAPERCLIP_API_BASE%/api}"
curl -s -X PATCH -H "Authorization: Bearer $PAPERCLIP_API_KEY" -H "Content-Type: application/json" \
  -d '{"adapterType":"codex_local","adapterConfig":{"model":"<型號>"}}' \
  "$PAPERCLIP_API_BASE/api/agents/<agentId>"
```

三個已實測的陷阱（詳見 `docs/standards/known-drift.md`）：

- `L4` body 只要帶任一 `instructions*` 欄位就 **整包 403**；只送要改的欄位。
- `L4` `adapterConfig` 是**合併語意**不是覆寫，只送 `model`／`effort` 不會清掉其他鍵。
- `L5` `GET /api/llms/agent-configuration/{adapterType}.txt` 對 agent **回 403**，
  agent 讀不到各 adapter 的設定 schema。⇒ 換到沒用過的 adapter 時，
  `adapterConfig` 的欄位名與允許值**無法事先查證**，第一次寫入要當成試驗：
  失敗就原樣回報錯誤、發卡請使用者查，**不要換寫法連續重試**（同 `H6`）。

### github／local-md

這兩個平台沒有「agent 註冊表」這種東西——供應商就是**你啟動哪一支 CLI**。所以：

- 指派結果寫在 `.foundry/config.yml` 的 `model_routing` 段，那份就是唯一真相。
- 執行者（人或排程）依該表決定用哪支 CLI 跑哪個角色的工單。
- 驗證方式：跑起來後比對 CLI 版本輸出與該角色設定的供應商是否一致。

## 5. 額度耗盡怎麼辦（`MR-1`）

規則本體是 protocol `M5`，本節只講操作順序：

1. **停下，不重試。** 額度牆不會因為換個說法或指數退避而消失。
2. **不自行降級模型。** 已實測無效並記入反悔錄 `R1`——`--fallback-model` 只涵蓋
   overloaded／not available，**不涵蓋額度用盡**。
3. 跑 §2.1 盤點，看還有哪幾家可用。
4. 依 §2.3 產替代方案 → §2.4 發卡（含「這是臨時改派還是永久改路由」）。
5. 使用者核可後執行；**臨時改派要在卡上寫明何時改回**，否則臨時值會靜悄悄變成新預設，
   造成規範與實況漂移。

> 為什麼要走這一整套而不是當場換一家跑完：換供應商會同時改變產出風格與規範載入方式，
> 沒有留下裁定紀錄的話，下一個 session 看到「這張單的產出和規範對不上」會查不出原因。

## 6. 檔案地圖

| 檔案 | 內容 |
| --- | --- |
| `SKILL.md`（本文） | 五步流程、路由政策、各平台落實方式 |
| `tools/model-routing/probe_providers.py` | 步驟 1 的盤點腳本（供應商登記表也在這裡） |
| `skills/foundry-protocol/SKILL.md` 第 8 節 | 規則本體：`M4`／`M5`／`M6` |
| `skills/foundry-platform/config-schema.md` | `model_routing` 段的欄位定義 |
| `docs/standards/known-drift.md` | `L4`／`L5` 平台限制、`R1`／`R6` 反悔錄 |
