# 已知漂移與反悔錄

> **這份文件回答兩個問題：**
> ① 規範寫的跟現實不一樣的地方在哪（**已知漂移**）——避免照文件做卻撞牆。
> ② 什麼提案已經試過並且被否決（**反悔錄**）——避免下一個 agent 好心把修好的東西改回去。
>
> 建立於 2026-09-03（MYL-36）。屬 `W1` 永久文件（protocol 第 6 節）。
> 撞到新的坑、或使用者否決了某個方向時，**當場補進這裡**，不要只留在工單留言——
> 留言不會被下一個 session 讀到，這份會。

---

## 1. 平台限制：撞了就是撞了，重試無用

這些不是 bug，是權限邊界。遇到時依 `H6` 發卡請使用者執行，**不要換寫法重試、不要指數退避**。

| # | 動作 | 結果 | 正解 |
| --- | --- | --- | --- |
| L1 | agent 呼叫 `PATCH /api/companies/{cid}/skills/{id}/files` | 403 `skill_actor_restricted` | 見 L2——多數情況根本不需要改檔，`local_path` 參照式 skill 改 repo 即生效。⚠️ **本條原本也涵蓋 `POST …/skills/import`，該半部已於 2026-09-03（MYL-37）證實失效**：以 `{"source": "<repo 內 skill 目錄絕對路徑>"}` 匯入 `role-frontend-verifier` **成功**（HTTP 200，得到 `local/ef57ddad3d/role-frontend-verifier`），持 `skills:create` grant 即可。條目依維護規則保留供追溯 |
| L1b | 把 skill 掛到某個 agent | ✅ **可自助**（2026-09-03 MYL-37 實測） | `POST /api/agents/{id}/skills/sync`，body `{"mode":"add","desiredSkills":["<skill key>"]}`。key 從 `GET /api/companies/{cid}/skills` 取（形如 `local/<hash>/<slug>`）。**`GET /api/agents/{id}/skills` 的 `entries` 會列出全公司的 skill**，只有 `desired: true` 那幾筆才是真的掛上——別把 `entries` 長度當成掛載數 |
| L2 | 「請使用者重新匯入 skill」 | **多半是誤診** | `sourceType: local_path` 的參照式 skill 每次喚醒直接 materialize repo 檔案，**repo 一 commit 就生效**。詳見 §3 反悔錄 R3 |
| L3 | `POST /api/agents/{id}/terminate`／`DELETE /api/agents/{id}`／`POST /api/agents/{id}/pause` | 403 `Board access required` | 只有使用者能在 UI 執行。發 `resolverPolicy: human_only` 的確認卡（MYL-34 已跑通全程）。軟退役可用 `PATCH /api/agents/{id}` 改 `metadata`＋`runtimeConfig.heartbeat.enabled: false`＋budget 0 |
| L4 | `PATCH /api/agents/{id}` body 帶任一 `instructions*` 欄位 | 403，**整包被拒** | 只送要改的欄位。該 endpoint 的 `adapterConfig` 是**合併語意**不是覆寫，只送 `model`／`effort` 不會清掉 `paperclipSkillSync` |
| L5 | `GET /api/llms/agent-configuration/{adapterType}.txt` | 403 `Missing permission to read agent configuration reflection` | **agent 讀不到各 adapter 的設定 schema**（2026-09-03 MYL-36 實測）。要換 adapter 時，schema 需由使用者查或從 adapter 套件原始碼推定。⇒ 換到沒用過的 adapter 時第一次寫 `adapterConfig` 是**試驗**不是照抄：失敗就原樣回報並發卡，不要換寫法連續重試（`foundry-model-routing` §4 已載明） |
| L6 | `GET /api/agents`（列表） | `API route not found` | 此路徑不存在。agent 層只有 `/api/agents/me` 與 `/api/agents/{id}`；列編制用 `GET /api/companies/{cid}/agents` |
| L7 | 工具閘道 API：`tools/mcp/import-json`、`tools/gallery`、`tool-profiles`、`trust-rules`、`policies` | 403 `Board access required` | 全部 board-only（2026-09-03 MYL-37 實測）。**但它不是取得 MCP 能力的必要條件**——`.mcp.json` ＋ settings 那條路 agent 可自助，閘道只多給 per-agent 綁定與審計。要平台級治理才需要請使用者在 UI 操作 |
| L8 | 工作區未信任時的 `.claude/settings.json` 的 `permissions.allow` | **整份被忽略**，harness 印 `Ignoring N permissions.allow entries ... this workspace has not been trusted` | 設計如此，不讓 clone 來的 repo 自己開權限。`~/.claude.json` 的 `projects[<路徑>].hasTrustDialogAccepted` 為 true 才生效；`.claude/settings.local.json` **不受此限**。Paperclip materialize 的 workspace 從沒被互動式開啟過，**預設一律未信任**。⇒ 版控那份要能用得靠使用者設信任旗標（`H6`，agent 不得自行改 `~/.claude.json`），要立刻能用就複製一份到 local。偵測：`make browser` 回報 `allowed_but_untrusted` |

## 2. API 形狀陷阱：會回 4xx 但錯誤訊息不會告訴你原因

| # | 陷阱 | 正確寫法 |
| --- | --- | --- |
| S1 | 互動卡內容放頂層 `body` → 422 | 必須包在 `payload` 物件：`{kind, idempotencyKey, continuationPolicy, title, payload: {version: 1, ...}}`。`ask_user_questions` 的問題欄位叫 **`prompt`**（不是 `question`），`version` 與 `selectionMode` 都必填 |
| S2 | `PUT /api/issues/{id}/documents/{key}` 放 `content` → 400；沒帶 `baseRevisionId` → 409 | 必填 `format: "markdown"`＋`body`＋`baseRevisionId`（現行 revision id） |
| S3 | `POST /api/issues` 開單 → 404 | 開單走 `POST /api/companies/{companyId}/issues`。該 endpoint 在 `openapi.json` 的 requestBody schema 是**空的**，欄位名以 GET 單一 issue 的回傳形狀為準 |
| S4 | 開單時直接設 `status: in_progress` → 被別的 heartbeat 搶走 checkout，隨後自己發卡回 409 `Issue run ownership conflict` | 先建成 `todo`／`backlog`，**發完卡再轉狀態** |
| S5 | `PATCH /api/issues/{id}` 的 `unblockDescriptor.owner` 填別的 agentId → 整個 PATCH 靜默不生效（`status`、`blockedByIssueIds` 一併沒寫入） | `owner` 只能填自己。要別的 agent 解鎖就用一級 blocker 掛該 agent 的工單 |
| S6 | agent 把工單 PATCH 成 `in_review` → `invalid_issue_disposition` | 需先存在真實審查路徑（pending 的互動卡）。順序：**先發卡、再改狀態** |

## 3. 反悔錄：試過、放棄、不要改回去

每一條都是**已經花過成本驗證**的結論。重新提案前，先讀「當初為什麼放棄」——如果理由還成立，就不要再提。

### R1 — 模型額度用盡時「自動降級」：做不到，不要再寫進提案

- **試過**：`claude -p --model claude-fable-5 --fallback-model claude-opus-5`。
- **結果**：仍吐 Fable limit、EXIT=1。CLI 的 `--fallback-model` **只涵蓋 overloaded／not available，不涵蓋額度用盡**；`claude_local` adapter 本身沒有 fallback 模型欄位（套件裡出現的 "fallback" 全是 ACP→CLI 引擎降級，不是模型降級）。
- **正解**：工單層 `assigneeAdapterOverrides`（接受 `adapterConfig` 或 `modelProfile`），不動 agent 預設 → 不製造新的文件漂移。
- ⚠️ 這條專治一個具體錯誤：在**沒實測**的情況下把「加個 fallback 旗標就能兜底」當可選項寫進使用者的裁定卡（MYL-33 v1 卡就是這樣，被使用者反問後才發現不可行）。

### R2 — 開多帳號分流＋監控 agent 看額度：否決

- **原因**：Paperclip **沒有可讀的剩餘配額介面**（costs API 只有用量與換算成本），唯一訊號是撞牆的錯誤訊息——監控 agent 無事可監控。
- 且多訂閱屬 `H3`（涉費用）＋ `P3`，另有服務條款風險。
- 技術上 `adapterConfig.env` 可設 `CLAUDE_CONFIG_DIR` 分流（adapter 明寫 operator 值優先），**能做不代表該做**。

### R3 — 「請使用者重新匯入 skill」：多數情況是誤診

- **試過**：MYL-23 期間連發兩張「請重新匯入」的卡，使用者回報匯入對話框**無法勾選**。
- **真相**：`foundry-protocol` 是 `sourceType: local_path` 參照式安裝，同路徑禁止重複匯入所以勾選框停用；而 runtime materialize 每次喚醒直接讀 repo 最新檔——**commit 即生效，本來就不用匯入**。
- **驗證 skill 是否生效的正確方法**：比對 acp-engine `agents/*/runtime-skills/**/SKILL.md` 最新 materialized 副本與 repo 檔案的 **md5**。
  **不要看**平台 skill 記錄的 `updatedAt` 或 versions API——那只反映 Studio 編輯或重匯入，會誤判成「未生效」而白發一張卡。

### R4 — 放寬 `push.main_push` 硬約束：使用者已裁定不放寬（MYL-35 G7 選項 A）

- 2026-09-03 確認卡 `cc915d68`：schema 維持只允許 `user`，**不為了讓設定檔能表達本 repo 的 P1 授權而改 schema**。
- 代價是留下 §4 的 GAP-3（設定檔表達不了本 repo 現況），**使用者知情並接受**。
- 本 repo 的例外**不隨 `foundry-init`／`foundry-adopt` 傳染**：導入的其他專案一律照字面執行，agent 不得援引本 repo 前例放行。

### R5 — 引入 GitHub PR 作為合併閘門：否決（MYL-23 §1.2）

- 審查職能已由 Code Reviewer 工單鏈承擔（交接包、Verdict、回寫留言）；PR 只是同一審查的第二份表單，會製造兩份真相。
- **重啟條件**：出現多人／多 agent 同時寫 code 的真併發需求時再開單評估。

### R6 — 把 agent 實際換到別的供應商：使用者裁定「先不改」（MYL-36）

- 2026-09-03 裁定卡 `ask:MYL-36:platform-routing:v1`，pilot 題選 **`none`**。原文：
  「我認為目前 paperclip 內的先不用跑」「目前 paperclip 先不實際改任何 agent 設定，**提供這樣的功能即可**」。
- **這不等於「P10 不做」。** 使用者要的是**能力就位、開關不開**：
  盤點腳本、路由規則（`M4`～`M6`）、`foundry-model-routing` workflow、`.foundry/config.yml`
  的 `model_routing` 段全部落地，但**不動任何 agent 的 `adapterType`**。
- 因此：7 個 agent 目前全在 `claude_local` 是**裁定的結果**，不是待同步的漂移。
  下一個 session 看到「規則寫了異廠審查、實際卻全同一家」時，**不要自行發起同步**——
  要啟用時由使用者說，或依 `M6` 發卡問，不要當成缺陷修掉。
- 使用者陳述的目的是**觀點互補**（「不同服務商提供的模型會有不同觀點，可以補足」），
  不是省額度、不是吞吐。之後若有人以「省額度」為由重提路由，那是另一個提案，
  判準不同，不能援引本次裁定當背書。

## 4. 已知缺口：使用者知情下保留，不要當成待辦自行修掉

| # | 缺口 | 出處與裁定 |
| --- | --- | --- |
| ~~GAP-1~~ | ~~**額度用盡沒有成文處置。**~~ **已關閉（2026-09-03，MYL-36）**：使用者在 `ask:MYL-36:platform-routing:v1` 要求「額度耗盡……可以透過這個 workflow 自動指派」，已成文為 protocol 第 8 節 `M5` ＋ `foundry-model-routing` §5。條目保留供追溯：MYL-33 當時的 `no_clause` 裁定已被本次裁定取代 | MYL-33 v3 卡 `no_clause` → MYL-36 卡取代 |
| GAP-2 | **高層無梯可升。** `M1` 寫 `low→medium→high`，但高層預設已站在 `max`；高層 agent 連續失敗兩次時 `M1` 無法適用，需臨場改走 `M3` 轉 `blocked` | MYL-33 v3 卡裁定 `ladder_no_change` |
| GAP-3 | **`.foundry/config.yml` 的 `push` 段表達不了本 repo 現況。** MYL-23 P1「合併回 main 後 push origin 由執行者自行」寫不進 schema，權威來源是 protocol 第 7、9 節的分級表文字 | MYL-35 G7 選項 A，見 R4 |
| GAP-4 | **`claude_local` adapter 內建說明字串的 `effort` 只寫到 `(low\|medium\|high)`，已過時。** 實際支援 `low/medium/high/xhigh/max`；adapter 對 `effort` 原樣傳給 CLI 不做驗證 | 實測 `claude-opus-5`＋`max` EXIT=0。protocol 第 8 節附註已載明 |
| GAP-5 | **瀏覽器工具綁的是「情境」不是「人」。** `.mcp.json` 放在共用 repo 裡，該 repo 的**所有** agent 都拿得到瀏覽器工具，不只 Frontend Verifier。要真正做到 per-agent 綁定得靠平台 tool-profile（`L7`，board-only） | MYL-37 卡 `myl37:frontend-verifier:plan:f7cf0b84` 的 `gateway: gateway_now`——使用者選擇由自己在 UI 補上閘道，能力層不等它 |

## 5. 併發與競態：多個 run 共用同一個 workspace

本 repo 的 workspace 是**共用**的，heartbeat run 可能併行。以下三件事都真的發生過。

- `X1` **commit 落到別人的分支。** 兩個 run 併行時 checkout 會互相干擾（MYL-23 的 commit 曾落到 MYL-27 的分支）。
  → **commit 前先驗 `git symbolic-ref --short HEAD`**，不要假設分支還是你切的那條。
- `X2` **發佈互蓋。** MYL-25 收尾 run 以較舊的來源樹在 MYL-32 之後 push，蓋掉了 02／03 章的新內容。
  → **發佈後要驗遠端實際內容，不能只看腳本回報成功**；發現被蓋掉就以最新 main 重跑。
- `X3` **手冊錨點與 mkdocs slug 不符。** 中文標題的錨點不是中文字面，是 mkdocs 產生的 slug（`#1`、`#3-hitl`…）。手寫中文錨點會變成點了不跳轉的死連結（MYL-25 踩過）。
  → 已納入 `foundry-lint --selfcheck` 的機械檢查。

### 兩份 nav 的結構性漂移

`mkdocs.yml`（私有站）與 `scripts/publish-handbook.sh` 內嵌的 heredoc `mkdocs.yml`（公開鏡像）是**兩份各自維護的 nav**。新增手冊章節時只改一份，公開站就會漏章——MYL-31 踩過這一類。

短期以 `foundry-lint --selfcheck` 機械比對三者（磁碟章節數／私有 nav／腳本內嵌 nav）擋住；
根治要讓腳本改為轉寫私有 `mkdocs.yml` 而非另寫一份，屬獨立工單範疇。

---

## 維護規則

- 本檔屬 `W1` 永久文件，改動走一般 commit；**不需要**發佈到公開手冊站（內容含內部 API 與平台細節）。
- 新增條目時給穩定編號（`L*`／`S*`／`R*`／`GAP-*`／`X*`），**只增不改、不回收**（同 protocol 第 11 節規則）。
- 條目失效時（例如平台放開了某個權限）**保留條目並註明失效日期與證據**，不要直接刪——刪掉之後，下一個人會重新踩一次來確認它真的失效了。
