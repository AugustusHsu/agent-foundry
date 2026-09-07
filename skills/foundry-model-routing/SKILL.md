---
name: foundry-model-routing
description: 模型供應商路由 workflow。三種情況載入本文：① 撞到模型額度上限、② 要調整哪個角色用哪一家供應商的模型、③ 新增或移除一家供應商。本文負責把「現在有哪幾家可用」「哪個角色該用哪一家」「怎麼實際改過去」收斂成固定流程，並依 M6 的兩級分成兩條路徑：已核可 profile 之間的整批切換不必發卡，其餘一律發卡。不得繞過本文直接改任何 agent 的供應商設定。
---

# foundry-model-routing：模型供應商路由

依 MYL-36 使用者裁定制定（裁定卡 `ask:MYL-36:platform-routing:v1`）。使用者給的目的原文：

> 「有不同服務商提供的模型會有不同觀點，可以補足，通常我是希望 review 跟寫 code 的 agent 用不同的模型」
>
> 「應該要有一個 workflow 知道跟處理目前能使用的平台模型，如果額度耗盡或是想要更改可以透過這個
> workflow 自動指派，目前 paperclip 先不實際改任何 agent 設定，提供這樣的功能即可」

所以本 workflow 的目標**不是省額度、也不是拚吞吐**，是**觀點互補**：讓寫 code 的和審 code 的
來自不同供應商，避免同一個模型的盲點在實作與審查兩端同時發生（規則本體＝protocol `M4`）。

## 0. 先分清三件事，別混

| | 管什麼 | 由誰定義 | 值 |
| --- | --- | --- | --- |
| **軸 B：文檔與協作工具** | 工單／狀態／看板放在哪 | `foundry-platform` ＋ `.foundry/config.yml` 的 `devtools_platform` | `github`／`gitlab`／`local-md`／`paperclip` |
| **軸 A：AI 平台** | agent 在哪個殼裡跑、被誰喚醒 | **`foundry-ai-platform`** ＋ `.foundry/config.yml` 的 `ai_platform` | `paperclip`／`claude-code`／`codex` |
| **模型供應商** | 哪一家的模型在跑這個角色 | **本文** ＋ `.foundry/config.yml` 的 `model_routing` | `claude`／`codex`／`gemini`… |

三者都曾被口語叫成「平台」，但換供應商不會換掉工單系統，換工單系統也不會換掉供應商。
**本文一律用「供應商」**；看到舊文件寫「平台路由」指的是本表第三列這一條。

⚠️ **`codex` 這個字在軸 A 與供應商兩個值域裡都出現，意思不同**：軸 A 的 `codex` 指
「agent 跑在 Codex 這個殼裡」，供應商的 `codex` 指「這個角色用 OpenAI 的模型」。看到這個字先確認在講哪一欄。

**軸 A 會限縮本文的可行值域**（MYL-78）：`ai_platform: paperclip` 時平台可以替不同角色掛不同
adapter，per-role 路由才有落點；`ai_platform: claude-code`／`codex` 時一個 session 就是一家供應商，
`model_routing` 的 per-role 設定**無處落地**，`M4` 只能靠開兩個 session 分別扮演而形式成立。
**軸 A 的定義與能力對照表一律以 `skills/foundry-ai-platform/SKILL.md` 為準，本表只給一句話指路**——
同一條軸不留第二份定義。

## 1. 什麼時候跑

| 觸發 | 情境 | 進入點 |
| --- | --- | --- |
| `MR-1` **額度耗盡** | 某供應商回報額度／用量上限，工作跑不下去 | 步驟 2.1，並依 protocol `M5` 處置。**已核可 profile 涵蓋得了這次的話走路徑 A**（見 §2） |
| `MR-2` **調整路由** | 想改哪個角色用哪一家（含首次啟用路由） | 步驟 2.1，**恆走路徑 B** |
| `MR-3` **供應商增減** | 裝了新的 CLI、或某家不再使用 | 步驟 2.1，**恆走路徑 B**，跑完更新登記表 |

⚠️ **`MR-1` 是唯一可能走路徑 A 的觸發**，而且不是自動走：要先確認已登記的 profile 裡有一套涵蓋得了
這次的情形，而且你不打算改它。`MR-2`／`MR-3` 的本質就是「決定哪些配置算合法」，那一定是使用者的事。

不屬於本文範圍：同一供應商內的**層級與思考程度**升降（那是 protocol 第 8 節 `M1`～`M3`，
個案由執行者自行判定，不必跑本 workflow）。

## 2. 兩條路徑：先判自己在哪一條

`M6` 自 MYL-128 起分兩級（protocol 第 8 節「供應商切換權限分級表」），本文的流程跟著分兩條。
**開工前先判在哪一條；判錯的兩個方向代價不對稱**——把 B 當成 A 走，是在沒有核可的情況下改公司層設定；
把 A 當成 B 走，只是多發一張卡、多等一輪。所以拿不準時走 B。

| 路徑 | 什麼時候走 | 要不要發卡 | 步驟 |
| --- | --- | --- | --- |
| **A：已核可 profile 之間的整批切換**（`M6` 第 1 級） | `.foundry/config.yml` 已有 `model_routing` 段，而你要做的就是把 `active` 換成另一個**已登記**的 profile（含額度恢復後切回），**且目標 profile 一字未改** | **不必**（常設授權） | 2.1 → 2.2 → 2.3 → 2.4 |
| **B：其餘全部**（`M6` 第 2 級） | 首次啟用路由（連 `model_routing` 段都還沒有）、profile 的新增／修改／刪除、或要把某個角色改成當前 profile 沒寫的供應商 | **要** | 2.1 → 2.2 → 2.5 → 2.6 → 2.7 |

**判準只有一句：你要套過去的那套配置，使用者核可過沒有？** 核可過的走 A，其餘全部走 B。
⚠️ **「只差一個角色」不是 A 的小變體，是 B。** 第 1 級的全部效力來自「目標 profile 一字未改」——
只要動了目標 profile 的任何一個欄位，這次切換就不是任何人核可過的那一套了。

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

### 2.2 讀現況：每個角色目前用哪一家（兩條路徑都要）

- **路由設定**：`.foundry/config.yml` 的 `model_routing` 段（schema 見
  `skills/foundry-platform/config-schema.md`）。整段缺席＝路由未啟用＝全隊都用預設供應商。
  有這一段時，**生效的是 `profiles[active]` 那一套**，不是所有 profile 的聯集——
  非 active 的 profile 是備選，不是現況。
- **平台實況**：依 `.foundry/config.yml` 的 `devtools_platform` 查（見 §4）。
- **設定與實況不一致時以設定為準並發起同步**，不是改設定遷就現況（同 protocol 第 8、9 節的權威來源規則）。

### 2.3 路徑 A：套用已核可的 profile（逐角色套用、逐角色回查）

先確認三件事，任一不成立就退回路徑 B：目標 profile **已登記**、你**沒有改它**、
它列到的每一家在 2.1 的輸出裡都是 `✅ 可用`。第三項不成立時是**環境問題不是設定非法**，
依 `M5` 停下發卡，不要改設定遷就環境。

`devtools_platform: paperclip` 上這三項檢查連同下面的逐角色套用與回查都由
`tools/model-routing/apply_profile.py` 機械執行（`--check` 先對帳、`--dry-run` 看將送出的
每一筆、`--apply` 才寫）。**先跑 `--dry-run` 再跑 `--apply`**；下面這幾條講的是它在做什麼，
以及在沒有這支工具的平台上要手動守住哪幾件事。

然後依 §4 對應平台**逐角色**執行，且**每套用一個角色立刻回查**：

- 回查看的是**查詢回來的值**，不是送出去的 payload，也不是指令回報成功。
- **任一格回查不符就停在那裡，不續套下一個角色。** 停在中間是刻意的：
  半套的狀態看得出來、查得到停在哪一格；套完才發現不對就分不清是哪一步壞的。
- 全部套完後更新 `.foundry/config.yml` 的 `model_routing.active`。
  **只准動這一欄**——profile 的內容是使用者專屬（`M6` 第 2 級）。

### 2.4 路徑 A：留下執行單

路徑 A 不發卡，所以**執行單就是這次切換的全部稽核痕跡**；沒有它，一次合法的切換
和一次沒人核可的切換在事後長得一模一樣。內容至少包含：

- 2.1 的盤點輸出（原樣貼上，不轉述）。
- 切換前後對照表：`active` 舊值 → 新值，以及逐角色的現值 → 目標值。
- **逐角色的回查結果**（每一格分別列出，不是一句「全部成功」）。
- **回退指令**：切回原本那個 profile 的完整指令（`M5`(d)：臨時改派要寫得出怎麼改回來）。
- 這次適用的是 `M6` 第 1 級、依據是哪一次核可（哪張卡／哪份計畫）。

`devtools_platform: paperclip` 上這一步不必手抄——`apply_profile.py` 的 `--apply` 會把上面
每一項組成一份報告，然後二選一放好：

```bash
# 貼回既有工單（那張單就是這次切換的稽核落點）
python3 tools/model-routing/apply_profile.py --profile <名> --apply --issue MYL-nnn

# 或另開一張切換執行單（描述由 templates/switch-execution-issue.md 產生）
python3 tools/model-routing/apply_profile.py --profile <名> --apply --create-issue --parent MYL-nnn
```

套用完到被改動的 agent 真正跑起來之前，錯的值是**沉默**的（心跳關掉的 agent 可以沉默好幾天）。
要當場問供應商收不收，加 `--smoke`；`--apply` 收尾會印一行帶著實際寫入值的指令，複製即可單獨重跑：

```bash
python3 tools/model-routing/apply_profile.py --smoke --target claude:claude-opus-5:max
```

它是 **opt-in**（每組花一次供應商額度，`H3`），且只驗「供應商收不收這些值」——
**不驗**平台把 config 寫對了沒有，那是 `--check` 的職責。兩者互補、互不取代。

⚠️ **不要把它讀成「錯的值一定攔得下來」**：「不收」有多響**逐家不同**——codex 是伺服器回 400、
exit 非零，claude 對未知 `--effort` 卻是**警告一行、沿用預設、exit 0**（`L33`）。後者只能靠比對
會隨版本改的警告字樣抓，字樣一改就靜默失效。工具因此**逐組印出偵測強度**，讀 ✅ 時連那一行一起讀。

三件先寫在明處的事：

- **`--parent` 是必填**，工具不會替自己宣告頂層單：新開的單一律掛得到樹上（protocol
  第 1 節上位單那一條）。`--create-issue` 另外只認 CEO 與 Product Manager 的金鑰（`I1`）。
- 新單**一開出來就是 `done`**：套用與回查在開單之前就跑完了，它是紀錄不是待辦。
- **鏡像要自己補**：工具建完單會把 `adapters/github.md` 時機 1＋時機 3 的步驟印出來，
  漏做會讓 `mirror-recon` 轉紅、擋住全隊的 commit。

### 2.5 路徑 B：產生指派方案（套政策，不即興）

依 §3 的政策表算出「角色 → 供應商」對照表。方案必須同時列出：
每個角色的**現值 → 目標值**、變更理由、以及 `M4` 是否成立（實作與審查是否異廠）。

### 2.6 路徑 B：發卡（這一步不能自己決定）

換供應商屬公司層設定變更，觸發 protocol `H6`，規則本體是 `M6` 第 2 級：
**本 workflow 在這條路徑上只負責盤點、產方案、發卡、執行、驗證，不負責決定。**

卡片內容至少包含：盤點輸出、現值→目標值對照表、`M4` 成立與否、回退方式（改回原值即可，無資料遷移）。
要新增或改寫 profile 時，卡上還要有 profile 的**逐字內容**——使用者核可的是那幾行字，不是一句摘要。
發卡後依 protocol 第 4 節轉 `blocked` 等回覆——**不得先改再問**。

> 常設授權的範圍**只有路徑 A**（`M6` 第 1 級，MYL-128 登記）。本步驟這條路徑沒有常設授權，
> 每次都要發卡；要擴大授權範圍，走規範修訂改 protocol 第 8 節那張分級表，不要在本文開特例。

### 2.7 路徑 B：核可後執行並驗證

依 §4 對應平台執行指派，然後**逐項回查**（不看指令回報成功，看查詢結果）：

- 平台側該 agent 的供應商欄位＝目標值。
- 該角色下一次執行確實跑在新供應商上（看 run 記錄或 CLI 版本輸出）。
- 把核可的配置寫回 `.foundry/config.yml` 的 `model_routing`（新增或改寫 profile、必要時改 `active`）。
  **這一步的寫入者是使用者或經使用者核可的計畫**，agent 不得自行改本檔。
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
| 機械性流轉 | Product Manager | 規格明確，對供應商最不敏感 |

### 3.2 硬約束

- `M4` **實作與審查異廠**（protocol 第 8 節）：可用供應商 ≥2 且路由已啟用時，
  同一張工單的 Developer 與 Code Reviewer 不得是同一家。
  唯一的合法例外是**標了 `emergency: true` 且帶非空 `waiver_reason` 的 profile 掛 `waives_m4: true`**
  （欄位定義見 config-schema）；豁免要被看見，不是被默許——它會出現在每一次對帳輸出裡。
- **一次只換一個角色**，跑完一輪再擴大——換供應商的退步（品質下降、格式不合）
  往往要跑幾張單才看得出來，一次全換會分不清是哪一項改動造成的。

  ⚠️ **本條的射程只到路由調整（`MR-2`／`MR-3`），`MR-1` 的整批緊急切換不適用**（MYL-128 依
  MYL-125 計畫修訂 2 的 D3 寫明）。理由：本條買的是**可歸因性**——換了之後品質變差，要查得出
  是哪一項改動造成的；而額度牆下「留在原廠」根本不是選項，逐個角色慢慢換只會讓半數角色停擺，
  換不到任何可歸因性。`MR-1` 改以三件事替代：
    1. **逐角色套用**（不是一次送出整批 PATCH）——出錯時看得出停在哪一格。
    2. **逐角色回查**（看查詢回來的值，任一格不符即停、不續套）。
    3. **單一報告**：整批切換寫成一份執行單，逐角色的前後值與回查結果全列在同一頁，
       之後要歸因時讀這一頁就夠，不必去拼湊散在各處的留言。

  這三件的操作細節在 §2.3／§2.4。**「不適用」指的是本條，不是可歸因性本身**——
  可歸因性沒有被豁免，只是換了一種取得方式。
- **角色規範怎麼載入要先確認**：這一項**是軸 A 的能力**（`CAP-1` 載入角色規範），不是供應商的性質，
  規則本體已移到 `skills/foundry-ai-platform/SKILL.md` 的 `AP-3`（MYL-78）。這裡只留結論：
  **換到不會自動載入 skill 的殼時，目標專案沒有 `AGENTS.md` 就先補**——判準與證據要求以 `AP-3` 為準。

### 3.3 現況（2026-09-07 起，MYL-128 改寫）

- 盤點：`claude`、`codex` 兩家可用（實機驗證，見 §2.1 腳本輸出）。
- 路由：**已啟用**。`.foundry/config.yml` 有 `model_routing` 段，登記兩個 profile：
  `codex-emergency`（active）與 `normal-mixed`。⇒ `M4` 的兩個前提都成立。
- **active 是 `codex-emergency`，它掛著 `M4` 的明文豁免**：Developer 與 Code Reviewer
  同在 `codex`，靠 `waives_m4: true` ＋ `waiver_reason` 收容。這是使用者知情下的取捨
  （MYL-125 計畫修訂 2 的 D2 採用 (b)），**不是待修缺陷**；改回的條件寫在 `waiver_reason` 裡。
- 在這段期間送審的工單，審查那一棒要知道自己是在 waiver 底下工作，並在報告寫明。
- ⚠️ 上面講的是**規則層宣告**。它與平台實況對不對得上是另一回事——`--selfcheck` 只驗
  repo 內宣告的自洽性，掃不到平台（同 `org-sync` 的刻意界線）。**不要把自檢綠讀成平台對得上。**

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

### github／gitlab／local-md

這三個平台沒有「agent 註冊表」這種東西——供應商就是**你啟動哪一支 CLI**。所以：

- 指派結果寫在 `.foundry/config.yml` 的 `model_routing` 段，生效的那一套是 `profiles[active]`，
  那份就是唯一真相。
- 執行者（人或排程）依該表決定用哪支 CLI 跑哪個角色的工單。
- 驗證方式：跑起來後比對 CLI 版本輸出與該角色設定的供應商是否一致。

## 5. 額度耗盡怎麼辦（`MR-1`）

規則本體是 protocol `M5`，本節只講操作順序。前兩步兩條路徑都一樣：

1. **停下，不重試。** 額度牆不會因為換個說法或指數退避而消失。
2. **不自行降級模型。** 已實測無效並記入反悔錄 `R1`——`--fallback-model` 只涵蓋
   overloaded／not available，**不涵蓋額度用盡**。
3. 跑 §2.1 盤點，看還有哪幾家可用。
4. **在這裡分路**（判準見 §2）：
   - 已登記的 profile 裡有一套涵蓋得了這次、而且你不改它 → **路徑 A**：§2.3 套用 → §2.4 執行單。
     不發卡；`M6` 第 1 級的常設授權就是為這一格存在的。
   - 其餘 → **路徑 B**：§2.5 產替代方案 → §2.6 發卡（含「這是臨時改派還是永久改路由」）→ §2.7 執行並驗證。
5. 不論走哪一條，**「什麼時候改回來」都要寫下來**：路徑 A 寫在執行單的回退指令，
   路徑 B 寫在卡上（若是新增 emergency profile，還要寫進 `waiver_reason`）。
   漏了這一句，臨時值會靜悄悄變成新預設，造成規範與實況漂移。

> 為什麼要走這一整套而不是當場換一家跑完：換供應商會同時改變產出風格與規範載入方式，
> 沒有留下裁定紀錄的話，下一個 session 看到「這張單的產出和規範對不上」會查不出原因。

## 6. 檔案地圖

| 檔案 | 內容 |
| --- | --- |
| `SKILL.md`（本文） | 兩條路徑的分界與各自的步驟、路由政策、各平台落實方式 |
| `tools/model-routing/probe_providers.py` | 步驟 2.1 的盤點腳本（供應商登記表也在這裡） |
| `tools/model-routing/apply_profile.py` | 路徑 A 的工具：`--list`／`--check`／`--dry-run`／`--apply`／`--create-issue`／`--smoke`（步驟 2.1～2.4） |
| `templates/switch-execution-issue.md` | 步驟 2.4 那張切換執行單的描述模板（由 `--create-issue` 機械填寫，不手填） |
| `skills/foundry-protocol/SKILL.md` 第 8 節 | 規則本體：`M4`／`M5`／`M6` ＋供應商切換權限分級表 |
| `skills/foundry-platform/config-schema.md` | `model_routing` 段的欄位定義（profile 結構、`active`、waiver 三欄） |
| `skills/foundry-ai-platform/SKILL.md` | **軸 A**（`ai_platform`）的權威：能力對照表、降級規則。§0 第二列指向它 |
| `docs/standards/known-drift.md` | `L4`／`L5` 平台限制、`R1`／`R6` 反悔錄 |
