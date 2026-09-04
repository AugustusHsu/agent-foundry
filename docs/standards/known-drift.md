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
| L8 | 工作區未信任時的 `.claude/settings.json` 的 `permissions.allow` | **整份被忽略**，harness 印 `Ignoring N permissions.allow entries ... this workspace has not been trusted` | 設計如此，不讓 clone 來的 repo 自己開權限。`~/.claude.json` 的 `projects[<路徑>].hasTrustDialogAccepted` 為 true 才生效；`.claude/settings.local.json` **不受此限**。Paperclip materialize 的 workspace 從沒被互動式開啟過，**預設一律未信任**。⇒ 版控那份要能用得靠使用者設信任旗標（`H6`，agent 不得自行改 `~/.claude.json`），要立刻能用就複製一份到 local。偵測：`make browser` 回報 `allowed_but_untrusted`。**本 repo 的 workspace 已於 2026-09-04（MYL-37 卡 `myl37:handover:v1` 選 `set_trust` 並授權代設）設為 true**——但**信任是綁「絕對路徑」的**，換 project／換機器／Paperclip 換一條 materialize 路徑，新路徑一律從未信任重來 |
| L9 | 把任何 Paperclip 管理的 MCP 連線授權給某 agent | 該 agent 的**專案 `.mcp.json` 整份失效**，瀏覽器工具無聲消失 | claude_local adapter 在「該 agent 拿得到 ≥1 個平台 MCP server」時才加 `--mcp-config <run 檔> --strict-mcp-config`（`adapter-claude-local/dist/server/execute.js:663`），而 `--strict-mcp-config` 的語意是 CLI 明載的「**只用 --mcp-config 的 server，忽略其他所有 MCP 設定**」。⇒ 閘道不是「額外加上去」，是**換掉整個 MCP 來源**。作用範圍是 per-agent（`getEffectiveProfilesForAgent`），但 gallery 連線的 finish 步驟預設 `access: "all_agents"`，等於全員生效。**日後掛 GitHub／Slack／Linear 之類遠端 app 前，先想這件事** |
| L10 | 想用工具閘道把 stdio 型 MCP（`npx chrome-devtools-mcp`／`@playwright/mcp`）綁給單一 agent | **送不進 agent session** | 只有 `transport === "mcp_remote"` 的連線會被組成 runtime MCP server 交給 adapter（`server/dist/services/heartbeat.js:2313` 的 filter），`local_stdio` 直接被濾掉。stdio server 只會在 Paperclip 的 runtime slot 跑起來、供**外部** MCP client 經 gateway URL 取用。另外 gallery 只有 7 個可連的 app（zapier／github／slack／notion／linear／google-sheets／context7，`shared/dist/app-definitions.js:2`），**沒有任何瀏覽器 app**。⇒ 見 `GAP-5`：閘道關不掉那個缺口 |

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

### R5 — 引入 GitHub PR 作為合併閘門：否決（MYL-23 §1.2），2026-09-04 重啟評估後**維持否決**

- 審查職能已由 Code Reviewer 工單鏈承擔（交接包、Verdict、回寫留言）；PR 只是同一審查的第二份表單，會製造兩份真相。
- **2026-09-04（MYL-53）依 MYL-39 計畫 v5 §4 重啟評估，結論維持否決**，但理由與原本不同。
  完整證據與三題答覆見 [`R5-pr-gate-evaluation.md`](../features/cross-platform/R5-pr-gate-evaluation.md)，重點：
  - **審查維度是零增量，而且封死。** 本 repo 只有一個 git 身分（89/89 顆 commit 同一人），
    而 GitHub 明文禁止 PR 作者核可自己的 PR。要求核可＝永久死鎖；不要求核可＝PR 只是狀態檢查的載體，
    「第二份表單」的原始批評原封不動成立。且 owner 本來就能在無核可下合併——強制力對唯一的人類是可繞過的。
  - **「機械部分早就就位」要修正。** `on: pull_request` 只是宣告，**從未觸發過一次**（12 次 run 全是
    push-on-main）；且沒有分支保護也沒有 ruleset，**PR 檢查紅燈擋不住合併**。要有機械執行力得由使用者
    去開必要狀態檢查（`H6`／`P3`），不是「補一句規則」而已。
  - **與 `R4`／`GAP-3` 正交。** PR 不會關掉 `GAP-3`（那是驗證器缺口——沒有任何程式讀 `.foundry/config.yml`），
    只會把它從**被記載**變成**被掩蓋**。**以「順便讓設定檔說真話」為由重提 PR，前提是錯的。**
  - **併發已經發生，但不是 PR 治得到的那種。** `X1`／`X2` 發生在共用工作目錄的 checkout 時刻與發佈推送時刻，
    都在合併之外（本次評估自己又撞了一次 `X1`）。**「本 repo 已經有併發了」不構成採用 PR 的理由。**
- **否決的範圍**：否決「把 PR 定為合併的必經路徑」。個案開 PR 仍可，`on: pull_request` 觸發器**維持原狀不必移除**。
- **重啟條件（2026-09-04 取代原本不可判定的「多人／多 agent 真併發寫 code」）**，滿足任一即重開評估：
  - `R5-a`：`git log --since=90.days --format=%ae main | sort -u | wc -l` ≥ 2（main 近 90 天有 ≥2 個作者身分）。
  - `R5-b`：`gh api repos/AugustusHsu/agent-foundry/collaborators --jq '[.[] | select(.permissions.push)] | length'` ≥ 2。
  - `R5-c`：CI 可信之後，main 仍在 30 天內出現 ≥3 次 `push` 事件的 CI 紅燈。
- 三條都不成立時，重提需提出評估報告未涵蓋的新論據，**不得只援引「別人都這樣做」**。

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
| GAP-5 | **瀏覽器工具綁的是「情境」不是「人」。** `.mcp.json` 放在共用 repo 裡，該 repo 的**所有** agent 都拿得到瀏覽器工具，不只 Frontend Verifier。要真正做到 per-agent 綁定得靠平台 tool-profile（`L7`，board-only） | MYL-37 卡 `myl37:frontend-verifier:plan:f7cf0b84` 的 `gateway: gateway_now`——使用者選擇由自己在 UI 補上閘道，能力層不等它。**2026-09-04 更正：這條缺口用閘道關不掉**——stdio 型 MCP 送不進 agent session（`L10`），硬掛遠端連線反而會把 `.mcp.json` 整份廢掉（`L9`）。維持 `.mcp.json`、以「不把遠端 app 授權給 Frontend Verifier」為代償規則 |

## 5. 併發與競態：多個 run 共用同一個 workspace

本 repo 的 workspace 是**共用**的，heartbeat run 可能併行；`X3` 起也一併收「mkdocs 渲染出來的東西跟來源字面不一樣」這一類踩點。以下每一條都真的發生過。

- `X1` **commit 落到別人的分支。** 兩個 run 併行時 checkout 會互相干擾（MYL-23 的 commit 曾落到 MYL-27 的分支）。
  → **commit 前先驗 `git symbolic-ref --short HEAD`**，不要假設分支還是你切的那條。
- `X2` **發佈互蓋。** MYL-25 收尾 run 以較舊的來源樹在 MYL-32 之後 push，蓋掉了 02／03 章的新內容。
  → **發佈後要驗遠端實際內容，不能只看腳本回報成功**；發現被蓋掉就以最新 main 重跑。
- `X3` **手冊錨點與 mkdocs slug 不符。** 中文標題的錨點不是中文字面，是 mkdocs 產生的 slug（`#1`、`#3-hitl`…）。手寫中文錨點會變成點了不跳轉的死連結（MYL-25 踩過）。
  → 已納入 `foundry-lint --selfcheck` 的機械檢查。
- `X4` **兩塊連續的 blockquote 會被 mkdocs 併成同一塊，空行擋不住。** Python-Markdown 的 blockquote 處理器看的是「前一個兄弟節點是不是 blockquote」，是就往裡面接。所以「`>` 戳記 → 空行 → `>` 章引言」渲染出來是**單一 `<blockquote>` 內含兩個 `<p>`**，視覺上一條左側豎線同時包住戳記與引言。MYL-49 在公開站實測 `04`／`06`／`07` 三章皆如此；`03-workflow` 沒事只是因為它戳記後面接的是一般段落，不是錨點挑得比較好。
  → **MYL-44 判定不修**（2026-09-04）：戳記的功能目的（讀者看得到最後對照的 protocol sha）已達成，`handbook-stamp` 要驗的東西全部成立，嚴重度純視覺。改戳記形式（例如換成斜體段落）會連動 `STAMP_RE`、pre-commit 觸發器、protocol 第 7 節條文、四章來源檔，還要再走一次發佈循環與一次視覺覆驗——為一條豎線不值得。**下一個看到的人請不要順手「修好」它**，要動先在工單裡把上面這串連動成本重新算一次。
  → 連帶的環境事實：**agent 在本機驗不了渲染。** 這個 workspace 的 `python3` 沒有 `markdown`、沒有 `mkdocs`，也沒有 `pip`（CLAUDE.md 第 6 節列的 `mkdocs serve` 是給使用者的，不是 agent 跑得動的）。⇒ 任何「這樣寫渲染出來會長怎樣」的假設，都只能靠公開站實測驗證，而那得先發佈——順序是反的。動手改渲染相關的東西前先認清這件事：你手上沒有便宜的驗證手段。

- `X5` **git 呼叫 hook 時會設 `GIT_DIR`，而它勝過 `git -C <路徑>`。** 於是「在臨時目錄造一個 repo 來測」這種測試，在 pre-commit 底下跑會被拉回**外層 repo**：臨時 repo 根本沒建起來，接著的 commit 觸發外層 hook、在臨時目錄找不到 `.pre-commit-config.yaml` 而整組紅。
  症狀極難認：**單獨跑 `make test` 全過，`git commit` 觸發同一組測試時全敗**，而且 `foundry-tests` 這個 hook 只在 staged 檔案含 `tools/` 時才觸發，所以它平常隱形，只在動到 `tools/` 的那次 commit 現形（MYL-52 撞上，當時 22 項全紅）。
  → 已修：`test_foundry_lint.py` 與 `tools/publish-docs/test_publish_gate.py` 在**模組載入時**就把 `os.environ` 裡的 `GIT_*` 清光，並各留一項回歸守衛。**要在程序層清，不是逐一傳 `env=`**——受測程式碼自己也會 shell out（`foundry_lint.git_run`），逐一傳只擋得住測試自己下的那幾道指令。日後新增「造臨時 repo」的測試，照抄這段。
- `X6` **併行的 run 會改到共用 repo 的 `.git/config`，把整個工作區弄壞。** 2026-09-04 深夜實際發生：另一個 run（MYL-44 的 hook 驗證）在共用 repo 上設了 `core.bare = true`＋`user.name = 測試`／`user.email = test@example.com`，於是本 run 的 `git status`／`git add` 全部回 `fatal: 該動作必須在一個工作區中執行`——而 `git symbolic-ref` 之類不需要工作區的指令照常成功，看起來像 repo 還好好的。
  → **不要去改回別人的設定**（他們可能正靠那個設定跑），也不要卡住等。兩條路：
    1. 唯讀查看用 `git --git-dir=.git --work-tree=. <指令>`，這條不改任何東西就能繞過 `core.bare`。
    2. 要 commit 就**開自己的 linked worktree**：`git --git-dir=<repo>/.git worktree add "$PAPERCLIP_RUN_SCRATCH_DIR/wt-<單號>" <分支>`，把工作區檔案複製過去，在那裡跑 `make check` 與 commit。分支與 ref 是共用的，commit 一樣進得了本 repo。
  → commit 時**顯式帶身分**（`git -c user.name=… -c user.email=… commit`），否則會用到別人留在 repo config 裡的測試身分。這一條與 `X1` 是同一類問題的兩種形態：`X1` 是 HEAD 被換掉，`X6` 是 config 被換掉。

### 兩份 nav 的結構性漂移

`mkdocs.yml`（私有站）與 `scripts/publish-handbook.sh` 內嵌的 heredoc `mkdocs.yml`（公開鏡像）是**兩份各自維護的 nav**。新增手冊章節時只改一份，公開站就會漏章——MYL-31 踩過這一類。

短期以 `foundry-lint --selfcheck` 機械比對三者（磁碟章節數／私有 nav／腳本內嵌 nav）擋住；
根治要讓腳本改為轉寫私有 `mkdocs.yml` 而非另寫一份，屬獨立工單範疇。

**2026-09-05（MYL-52）補充：新增的第三個閱讀面沒有再加一份 nav。** wiki 的側欄
（`_Sidebar.md`）由 `tools/publish-docs/project_docs.py` **轉寫私有 `mkdocs.yml` 的 nav**
產生，正是上面那句「根治」的做法。`publish-handbook.sh` 的內嵌 heredoc **維持原樣未動**
——改它會連動 `check_nav_sync` 綁定的區塊標記，不在該單範圍。所以現況是：
**兩份手寫 nav ＋ 一份轉寫的**，漂移面沒有擴大，但也還沒收斂。

---

## 維護規則

- 本檔屬 `W1` 永久文件，改動走一般 commit；**不需要**發佈到公開手冊站（內容含內部 API 與平台細節）。
- 新增條目時給穩定編號（`L*`／`S*`／`R*`／`GAP-*`／`X*`），**只增不改、不回收**（同 protocol 第 11 節規則）。
- 條目失效時（例如平台放開了某個權限）**保留條目並註明失效日期與證據**，不要直接刪——刪掉之後，下一個人會重新踩一次來確認它真的失效了。
