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

這些不是 bug，是**權限邊界或平台能力邊界**——後者常見的形狀是「API 根本沒有那個設定點，只有 UI 有」。
遇到時依 `H6` 發卡請使用者執行，**不要換寫法重試、不要指數退避**。

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
| L11 | 用 `createProjectV2View` 建 Projects v2 的 view，期望它帶入專案的自訂欄位 | view 建得出來，但 `visibleFieldIds` **一律是 GitHub 出廠預設**（`Title, Assignees, Status, Linked pull requests, Sub-issues progress`）；自訂欄位即使有值也不會出現在畫面上 | 建完再呼叫一次 `updateProjectV2View` 補 `visibleFieldIds`，這是兩步不是一步。另外 **view 只能走 GraphQL**：`gh project` 的子命令只到 project／field／item／link 層級，沒有任何 view 子命令（2026-09-05 覆核）。（2026-09-04 MYL-43 實測） |
| L12 | 把 `L11` 的補救套到 Roadmap view 上：對 ROADMAP_LAYOUT 呼叫 `updateProjectV2View` 補 `visibleFieldIds` | `UNPROCESSABLE: "Roadmap views do not support visible fields."` | Roadmap 沒有「欄位可見性」這個概念，別在這裡重試。Roadmap 畫不出東西的真正原因見 `L13`——**不是**欄位沒顯示。（2026-09-04 MYL-43 實測） |
| L13 | 純用 API 建出 Roadmap view，然後去看畫面 | **時間軸必定空白**：格線與月份標尺正常、左側列得出項目，但時間軸區域不畫任何條狀區間或里程碑點 | **兩個獨立成因，各自都足以造成空白，只修一個畫面照樣是空的**——這是本條最容易被寫漏的部分。**成因 A（UI 專屬，API 無設定點）**：view 的 Start／Target date 指向「無」。全 schema 掃過：ProjectV2 相關 mutation 共 32 個，動 view 的只有 `updateProjectV2View`，其 `ProjectV2ViewConfigurationInput` **只有 `visibleFieldIds` 一個欄位**，讀取型別 `ProjectV2ViewConfiguration` 也只有 `visibleFields`；設定入口只在 UI 的 `Roadmap` → `Date fields`，依 `H6` 發卡請使用者按。**成因 B（可自動化）**：項目的日期欄位根本沒有值——`updateProjectV2ItemFieldValue` 寫得進去。MYL-43 撤回後 39 張手抄 draft card 換成真 issue，原本帶的目標日沒有人補回來，於是 GraphQL 查 `fieldValues` 只回 `Status`，一筆 `ProjectV2ItemFieldDateValue` 都沒有。⚠️ **診斷時不要相信 `Date fields` 按鈕上那句提示**「*Your project needs at least one date or iteration field to get started.*」——它與事實不符：GraphQL 查得該專案 `目標日` 的 `dataType` 就是 `DATE`（`PVTF_lAHOAVyI0c4BiTdozhhU4zo`），研判是登出訪客沒按過 `Got it!` 的新手引導殘留。⇒ 本條是本 repo 目前**「機械驗證會騙人」最乾淨的樣板**：欄位在、值在、view 在、layout 正確，所有 `gh api` 斷言全綠，畫面就是空的。**視覺驗證不可被 API 斷言取代**，要舉例時舉這一條。（成因 A 與 schema 掃描：2026-09-04 MYL-43；成因 B、提示文字與畫面現況：2026-09-05 MYL-48 登出實測，附截圖） |
| L14 | 從「repo 是 public」推論「掛在它上面的 Projects v2 看板也是 public」 | **推論不成立**。Projects v2 是帳號層物件，可見性與 repo 各自獨立；MYL-48 兩次「以為開了窗口」都栽在這裡 | 判定可見性**只能用登出瀏覽器實跑**，不要看設定畫面、也不要從 repo 可見性推。登出態的自我證明手法：頁首出現 `Sign in`／`Sign up`（`ref_loc=header+logged+out`）即排除「其實還登著」的假陽性；看板為 private 時同一網址回 404，該 404 同時證明 private 與登出兩件事。同一個根源還有另一個表現：**v2 看板只屬於帳號、不屬於 repo**，建好不會自動掛上去，要另外 `gh project link`；要確認掛上了沒有，查 GraphQL 的 `repository.projectsV2` 而不是 REST 的 `has_projects`（MYL-57 實測）。（2026-09-05 MYL-48 實測） |
| L15 | `has_wiki: true` 之後直接 clone／push `<repo>.wiki.git`，期望 wiki repo 已經存在 | 兩邊都 `Repository not found`（clone 與 push 皆是）。**啟用 wiki 只是開開關，wiki 的 git repo 要等第一頁建立才成形**，而建第一頁**只有 UI 有入口**：REST 的 `repos/{o}/{r}/wiki` 是 404，GraphQL 沒有 wiki mutation，push 也不會把它生出來 | 依 `H6` 發卡請使用者在 `https://github.com/<o>/<r>/wiki/_new` 建任意一頁（內容隨意，下次投影會覆蓋），之後腳本才跑得動。⚠️ **不要把這個 `Repository not found` 讀成權限問題**：同一把 ssh 金鑰對主 repo `ls-remote` 正常，那個對照組就是「不是認證問題」的證明——沒跑對照組的話，這裡很容易被誤診成 token scope 不足而去換認證方式重試。（2026-09-05 MYL-52 實測：`has_wiki` 由 false 改 true 之後立即測，clone／push／REST 三條路全試過） |
| L16 | 以為手冊裡的頁內錨點（`[主開發流程鏈](#1)`）投影到 wiki 之後照樣能跳，於是把投影的錨點改寫當成多餘的一步簡化掉 | **兩邊的 slug 演算法不同，而且失敗是無聲的**。手冊原文的 `#1`／`#3-hitl` 是寫給 mkdocs（Python-Markdown）的：它的 slugify 走 NFKD → ASCII，**中文整段被吃掉**，於是 `## 1. 主開發流程鏈` 的 id 就只剩 `1`。GitHub（wiki 與 repo blob 兩邊）**保留中文**，同一個標題算出來是 `1-主開發流程鏈`。錨點對不上時頁面照常渲染、連結照常可按，**只是按了不會跳**——沒有 404、沒有紅字、沒有任何一支 lint 會叫 | 投影**必須**依目標面的演算法重算錨點（`project_docs.github_slug()`／`github_anchors()` 就是幹這件事的），不能原樣搬。⚠️ **本機驗不了這件事**（見 `X4` 沒有渲染器），唯一算數的證據是抓實站渲染出來的 `id="user-content-…"` 來比對。2026-09-05 MYL-52 實測全綠：9 頁全取得、44 條內部連結目標頁存在、**9 個錨點全部在實站 id 集合裡找得到**，證明 `github_slug()` 與 GitHub 真實演算法一致（含 `## 3. HITL 發卡` → `3-hitl-發卡` 這種中英混排）。⇒ 改動投影的連結改寫邏輯後，**要重跑一次實站比對才算驗過**，本機測試全綠不構成證據 |
| L17 | 對一個還沒有 `gh-pages` 分支的 repo，先去 Settings → Pages 想把來源設成 `gh-pages` | **選單裡沒有那個分支**。Pages 的來源分支下拉只列得出已存在的分支，而 `gh-pages` 要等第一次 `mike deploy`／`gh-deploy` 推上去才存在 | 順序反過來：**先讓 CI 跑一次**（打 `handbook-v*` tag；此時站台仍 404，那是正常的）→ 分支建出來 → **再開 Pages 選 `gh-pages` / root**。⚠️ 這與 wiki 的 `L15` 是**同一種形狀的不同方向**：`L15` 是「開了開關但 repo 還沒成形」，本條是「東西還沒成形所以開關選不到」。兩條共通的教訓是**「開通對外面」往往是兩步，發卡時要一次講完**，只問第一步會讓使用者以為按完就結束。（2026-09-05 MYL-55：`repos/AugustusHsu/agent-foundry/pages` 實測 404、repo 只有 `main` 一條分支） |
| L18 | 封存（archive）一個有 Pages 的 repo，以為它的公開站會跟著關掉 | **站台照樣活著**。`PATCH repos/{o}/{r}` 帶 `archived=true` 之後 `has_pages` 仍是 true，實測 `https://augustushsu.github.io/foundry-handbook/` 與其子頁封存前後都回 200——封存只把 **repo** 變唯讀，已部署的 Pages 內容不受影響 | 要真的讓舊網址斷，得**另外**呼叫 `DELETE repos/{o}/{r}/pages`，而且**必須趕在封存之前**（封存後 repo 唯讀，這支 API 大機率 403）。⇒ 「封存舊 repo」與「關掉舊站」是**兩件事、兩個授權、有先後順序**——發卡問「要不要封存」時如果沒同時問「要不要關站」，使用者會以為按完就斷了，實際上舊內容仍在公開索引裡跟新站打對台。與 `L15`／`L17` 同屬「對外面的開關是兩步」這一族。**最乾淨的收法其實是把整個 repo 刪掉**（Pages 跟著消失），但那條路另有權限牆，見 `L20`。（2026-09-05 MYL-55 實測：封存後兩條舊網址各再測一次，仍 200） |
| L19 | 用 `curl` 抓 mkdocs-material 站台的 HTML，`grep` 不到 `md-version` 就判定「版本選擇器沒生效」 | **誤判**。版本選擇器是**瀏覽器端 JS 渲染**的：靜態 HTML 只帶 `<script id="__config">` 裡的 `"version": {"provider": "mike"}`，`.md-version` 元素由 bundle 於執行期 fetch 站根 `versions.json` 之後才插進 DOM。`curl` 永遠看不到它 | 判定方式分兩層：**設定層**看 `__config` JSON 有沒有 `version.provider`＋站根 `versions.json` 回不回得了 200；**畫面層**只能用真瀏覽器（本 repo 走 `foundry-browser` 的 playwright MCP）查 `.md-version__current` 的文字與 `.md-version__link` 清單。2026-09-05 MYL-55 實測：curl 抓不到任何 `md-version`，瀏覽器查到 `hasVersionSelector: true`、`currentLabel: "v1"`。⇒ 這是 `L13`「機械驗證會騙人」的**反向版本**——L13 是 API 全綠但畫面空的，本條是文字比對全空但畫面其實是對的。**兩個方向都要提防**。附帶一提：站台 console 會有一筆 `api.github.com/repos/{o}/{r}/releases/latest` 404，那是 material 的 repo 資訊卡在抓最新 release，repo 沒發過 release 就會 404，**與版本選擇器無關**，不要順手去「修」它 |
| L20 | 看到 `repos/{o}/{r}` 回 `"permissions": {"admin": true}`，就以為手上這把 token 刪得掉這個 repo | `DELETE repos/{o}/{r}` → **403 `Must have admin rights to Repository.`**。**這句訊息會把人帶錯方向**：admin 明明就是 true，真正缺的是 **`delete_repo` scope**（本 repo 的 `gh` token 實測為 `gist, project, read:org, repo`）。只有 `gh` 自己多印的那行 `This API operation needs the "delete_repo" scope` 講出了實情，直接打 REST 是看不到的 | 刪 repo 屬**帳號層授權**，不是 repo 層權限，兩者不可互推。補 scope 要走 `gh auth refresh -h github.com -s delete_repo`——**互動式裝置流程，agent 跑不動**，而且那是在改使用者的全域憑證（`H6`）。⇒ 把「刪 repo」當成**使用者專屬動作**，發卡時直接附 UI 路徑（`Settings` → 頁尾 `Danger Zone` → `Delete this repository`），不要先承諾代做。⚠️ 別把 `Must have admin rights` 讀成「權限不夠、去要 admin 或換認證方式」而繞路重試——對照組是同一把 token 對同一個 repo `PATCH archived=true` **成功過**，那就證明不是 repo 權限問題。與 `L15` 那條「不要把 `Repository not found` 誤診成 token 問題」是同一種反向誤診。（2026-09-05 MYL-55 實測） |
| L21 | 用 `updateProjectV2Field` 幫 Projects v2 的單選欄位（如 `Status`）**補**幾個缺的選項，把既有選項照抄一份、只在後面加新的 | **`singleSelectOptions` 是整份取代，不是增量**——而且**即使名稱、顏色、描述一字不差，既有選項也會被重新配發 option id**，連帶**看板上所有項目的該欄位值全部被清成 `null`**。實測：三個選項補成六個，`Todo` 的 id 由 `f75ad846` 變成 `507fee68`，三張 item 的 Status 同時歸零 | **動手前先把每張 item 的現值抓下來**（`gh project item-list <N> --owner <O> --format json --jq '.items[] \| {num:.content.number, status}'`），改完拿新的 option id 逐張 `gh project item-edit` 寫回。`ProjectV2SingleSelectFieldOptionInput` 沒有 `id` 欄位，**沒有任何辦法保住原 id**，所以「先備份再重寫」是唯一安全序。⚠️ 這件事**不會報錯**：mutation 回 200、回傳的六個選項看起來完全正確，要另外去查 item 才發現值沒了——與 `L13` 同屬「機械斷言全綠但畫面是空的」。（2026-09-05 MYL-55 實測，三張 item 已即時還原） |
| L22 | 把 SuperOD `T3`（GitLab protected tag、`Allowed to create = Maintainers`）原樣搬到 GitHub：為 `handbook-v*` 設一條 tag ruleset「限制建立者」，好讓 `V1` 的「使用者專屬」有機械後盾 | **以 actor 為單位的限制在本 repo 結構上無解**。GitLab 那招成立的前提是 Developer 與 Maintainer 是**兩個角色、對到兩個身分**；本 repo 是**個人帳號底下的 repo**（`owner.type: User`），使用者與所有 agent **共用同一個 GitHub 身分**，而個人 repo 的 bypass list 只有 Repository admin／Deploy key／GitHub App 三種 actor，**沒有第二個角色階**。於是「限制建立者」只塌得成兩種極端：bypass 放 Repository admin ⇒ agent 也是 admin，**一條都擋不住**；bypass 留空 ⇒ **連使用者自己也推不了 tag**。⚠️ 而且 agent 這把 token **改得動 ruleset 本身**，所以「agent 自己把 guard 關掉」不是假設性風險 | 別當成 `T3` 的等價移植。bypass 留空仍有兩項實益，但要講清楚是哪兩項：**擋掉 `git push --tags`／`--follow-tags` 的誤推**，以及把違規路徑從「一行 push、零痕跡」變成「得先去關掉一條看得見的 guard」。那是**防呆＋留痕**，不是**限制身分**——規則文字照這個寫，否則等於拿一個假的 `【機械】` 換掉誠實的 `【自律】`，比原狀更糟。與 §3 `R5` 同根：單一 git 身分封死的不只是「審查」這個維度，而是**任何以 actor 為單位的授權設計**，日後再看到「用平台角色權限擋住 agent」的提案，先回來讀這條。⚠️ 與 `L20` 剛好反向對照：那邊 `permissions.admin: true` 卻因缺帳號層 scope 而 403，本條則是 repo 層 admin ＋ `repo` scope 就寫得動 ruleset ⇒ **「能不能」要逐個 endpoint 探，兩個方向都不可由 admin 旗標推定**。（2026-09-05 MYL-62 實測：`rulesets` 為空＝從零建立；`POST …/rulesets` 帶無效 enum 回 **422 而非 403**，即授權通過、只是驗證擋下，證明 token（scope `gist, project, read:org, repo`）寫得動 ruleset；`rulesets/rule-suites` 回 200 `[]`＝稽核面可用）**裁定與落地（2026-09-05 MYL-62，使用者選 A）**：`handbook-version-tags`（id `22327706`、target `tag`、`active`、bypass `[]`、只放 `creation`、include `refs/tags/handbook-v*`）已建。**驗證方式刻意繞開 `handbook-v*`**——先把 include 設成 `refs/tags/ruleset-probe-*`（不命中 CI 的 `on: push: tags` glob）推 probe tag，遠端以 `remote: GH013 … Cannot create ref due to creations being restricted.` 拒收、遠端未留下殘骸，再改回正式 glob；直接拿 `handbook-v0-probe` 去撞的話，萬一 guard 沒生效就會觸發 CI、在精裝站多出一個假版本。另有兩則 API 形狀：**更新 ruleset 是 `PUT …/rulesets/{id}` 帶完整 body，`PATCH` 不支援、回 404**（404 讀起來像「沒這個 ruleset」，實際是「沒這個方法」，很容易誤判成建失敗）；`creation` 規則**不含**移動與刪除，`push --force` 移動既有 tag 與刪 tag 都放行。 |
| L23 | 看到 `GET /api/agents/me` 回 `access.canAssignTasks: false`，就以為這個 agent 動不了工單的指派與依賴鏈 | **推論不成立，而且是兩層都不成立。**（a）**排依賴鏈根本不歸這個旗標管**：以 Tech Lead（`canAssignTasks: false`、`taskAssignSource: "none"`、`grants: []`）對一張 `done` 單 `PATCH /api/issues/{id}` 送 `{"blockedByIssueIds":[…]}`，**HTTP 200 且實際寫入**。（b）**連指派本身都沒有被擋**：同一個 agent 用同一支 endpoint 送 `{"assigneeAgentId":"<CEO 的 id>"}`，把該單的 assignee 從自己改成別人，**照樣 200 且實際生效**。⇒ `access.canAssignTasks` 在 `PATCH /api/issues/{id}` 這條路徑上**不是強制閘門**，它比較像面板／派工來源的宣告 | 兩件事分開記。**規範側**：「派工歸誰」是規則層的授權邊界，標記只能是 `【自律】`——寫成「平台會擋住別人」是拿一個假的 `【機械】` 換掉誠實的 `【自律】`，與 `L22` 同一種錯。**執行側**：要判斷某個動作做不做得到，**只能逐個 endpoint 探，不可由權限旗標推定**（`L20`／`L22` 已是同一族的兩則）；反過來，看到某個角色「不該做」的事在 API 上做得到，不代表可以做——那是規則問題不是能力問題。⚠️ 探測時**不要拿在途工單試**：本次刻意選 `done` 單（`done` 不會起 run），且每一步都先讀原值、測完立即還原（MYL-72 的 `blockedBy` 與 assignee 均已復原、`executionState` 全程 null）。⚠️ 另有一個未排除的變因：本 repo 的 agent `adapterConfig` 帶 `dangerouslySkipPermissions: true`，那是 harness 的工具許可旗標、理論上與平台 API 授權無關，但沒有對照組可驗——換公司或換設定時本條要重測。（2026-09-05 MYL-73 AC0 實測；對照組：送不存在的 agent id 回 **404 `Agent not found`** 而非 403，即授權未攔在前面） |
| L24 | 想授予或收回 `access.grants[]` 裡的 `agents:configure` | **沒有寫入路徑**——不是 403，是根本沒有那個設定點。`PATCH /api/agents/{id}/permissions` 的 body 有**五**個欄位——三個布林（`canCreateAgents`／`canCreateSkills`／`canAssignTasks`）＋ `trustPreset`（string enum，`standard`／`low_trust_review`）＋ `authorizationPolicy`（巢狀物件：`assignmentPolicy`／`protectedAgent`／`reviewPreset`／`trustBoundary`／`trustPreset`）——**沒有任何一個**對應得到 `agents:configure`，後兩者是 trust／review preset，碰不到 grant。⚠️ 順帶記形狀：`required` 只有 `canCreateAgents`／`canAssignTasks` 兩個，`canCreateSkills` **不是**必填。CEO 身上那條（grant `185a982d`）`grantedByUserId: null` ＝建 agent 時自帶、從來沒有人逐條授過 | 這一格**只讀得到**。`.foundry/org.yml` 的 `configure_agents` 因此永遠只能是「登記現況」而不是「應然」——宣告了也沒有辦法照著設定，值域表已標明（`skills/foundry-platform/config-schema.md` 的 `permissions` 值域）。⇒ 別為了「讓宣告與平台一致」去找寫入端點，那支不存在；能改 membership grant 的 `PATCH …/members/{id}/role-and-grants` 是 board-only（＝使用者專屬）。（2026-09-06 MYL-79 實測） |
| L25 | 建 agent 時只帶部分 `runtimeConfig`，以為存進去的就是送出去的那份 | **兩支端點行為相反，而且都不報錯。** `POST /api/companies/{cid}/agents` 會**自動補鍵**：送 `{"heartbeat":{"maxConcurrentRuns":20}}`，存進去的是 `{"heartbeat":{"enabled":false,"maxConcurrentRuns":20},"modelProfiles":{"cheap":{"enabled":false}}}`——平台補上了 `enabled: false`。而 `PATCH /api/agents/{id}` 的 `runtimeConfig` 是**取代**語意：送同一份上去，`enabled` 與 `modelProfiles` 就整個消失了。⚠️ 這與 `adapterConfig` 的**合併**語意（`L4`）**正好相反**——同一支 PATCH 的兩個欄位，兩種語意 | 建完**一定要另打 GET 覆驗 `runtimeConfig`**，不能拿送出去的 payload 當結果。這個補鍵不是無害的：`heartbeat.enabled: false` 而**沒有** `wakeOnDemand: true` 的組合，形狀上與全隊任何一名都不同（CEO／FV 是 `false`＋`wakeOnDemand`，6 名幹活的則根本沒有 `enabled` 鍵），MYL-79 建 PM 時就落進這一格，靠再打一次 PATCH 送完整目標形狀才拉回與 6 名一致。⇒ 要哪個形狀就用 PATCH **整份**送，別靠建立端點的預設。（2026-09-06 MYL-79 實測） |
| L26 | 由 `L23`（FV 那次收回落在 `simple_default`）推論「授予 `tasks:assign` 也拿不到真正的 grant」 | **推論不成立——落點取決於該鍵的起始狀態。** 對一個**從未設過**這個鍵的 agent（`taskAssignSource: "none"`、`grants: []`）送 `{"canAssignTasks": true}`，得到的是 `taskAssignSource: "explicit_grant"` ＋ `access.grants[]` 裡一條真正的 `tasks:assign`。`L23` 那個回不去的 `simple_default` 只發生在**開過又關**的方向 | 單向門只卡「關」那一邊，「開」是正常的。⇒ 寫 AC 或預告證據形狀時，**先問對方的起始狀態是 `none` 還是 `simple_default`**，別把一次觀察到的落點當成這支 endpoint 的通則——MYL-79 就先在留言預告了錯的形狀（預告 `simple_default`＋空 grants，實跑是 `explicit_grant`＋真 grant），實跑才推翻。（2026-09-06 MYL-79 實測） |
| L27 | 沿用 `L22` 的授權推論技法（「帶無效 body 回驗證錯誤而非 403 ＝ 授權通過」）去探一支沒探過的端點，探針隨手湊一個殘缺 body | **殘缺 body 會給假陽性，而且結論方向是反的。** 實測 `PATCH /api/companies/{cid}/members/{mid}/role-and-grants`：送 `{"__invalid__":1}` 回 **400 `Validation error`／`membershipRole or status is required`**；送 `{"grants":[]}` 回 **400、同一句訊息**——照 `L22` 讀會得出「授權通過、這支不是 board-only」，正好推翻 MYL-79 寫對的那句。但送**完整合法** body `{"membershipRole":"viewer","grants":[]}` 就回 **403 `Permission denied`**。這支端點的 **body 驗證跑在授權檢查之前**，殘缺 body 根本走不到授權那一關 | 技法本身沒錯，錯在探針。**只有送得出完整合法 body 的那一發，回應碼才反映授權結果**；在那之前收到的每一個 4xx 都只證明「驗證器擋下了」，不證明任何授權事實。⇒ 探陌生端點前先從 OpenAPI 撈出它的 `required` 欄位把 body 湊齊，再看回什麼。⚠️ 兩個容易誤讀的細節：(a) `L22` 那次 `POST …/rulesets` 之所以成立，是因為它送的是**合法形狀、只有 enum 值無效**，已經穿過驗證層——不是因為「隨便送就行」，兩者不是同一種探針；(b) 本次刻意用**不存在的 member id**（`00000000-0000-4000-8000-000000000000`）配完整合法 body，仍回 **403 而非 404** ⇒ 授權檢查也跑在資源查找之前，**用假 id 探不會誤傷真資料**，是安全探法（與 `L23` 那組「送不存在的 agent id 回 404」相反，順序逐支端點都不同，同樣不可互推）。與 `L20`／`L22`／`L23` 同族：能不能做只能逐個 endpoint 探，而本條再加一層——**探法本身也要驗**。（2026-09-06 MYL-95 複審時發現，MYL-103 以不存在的 member id 重跑三發覆驗，三個回應碼與原觀測一致） |
| L28 | 想「取消某些 agent 的開單權」，讓開單白名單（protocol `I1`）有平台後盾 | **做不到：21 個 `permissionKey` 裡沒有任何 `issues:*`。** 開單不是受權限鍵管的動作，所以「只讓使用者／CEO／Product Manager 開單」在平台上沒有開關可切；同源的第二件事是**開單者欄位（`createdByAgentId`）沒有任何更新路徑**——`PATCH /api/issues/{id}` 的欄位清單裡沒有它，已經開出來的單改不了作者。⚠️ **它的失敗方式是 200 no-op 而不是 4xx**：把 `createdByAgentId` 送進 `PATCH` 會回 **200**，回頭 `GET` 那一格沒變、`statusVersion` 也沒跳（2026-09-06 MYL-116 CR 實測）——想「修作者」的人會以為改成功了 | 降級成「規則層明文 ＋ 事後機械檢查」（使用者於 MYL-96 卡 `85c67d39` q2 裁定，＝裁定 #5）：條文是 protocol 第 1 節 `I1`，檢查是 `foundry-lint --selfcheck` 的 `issue-authors`。⚠️ **條文與 lint 訊息都不得寫成「擋得住」**——把事後檢查說成閘門，讀的人會以為違規開不出來，於是不再去看那一項的輸出。另有一類天生收不進白名單的單：**平台自己開的**（生產力審查單，兩個開單者欄皆為 null，實例 MYL-113／114），`I1` 明文收容。⚠️ **「作者改不了」還逼出一條非有不可的收斂路徑**：檢查認的是一格永遠不變的欄位，而 `--selfcheck` 跑在 pre-commit 的 `always_run` 上 ⇒ 沒有出口的話，一張違規單會擋住**所有 agent 的所有 commit**，且永遠修不掉（2026-09-06 MYL-116 CR 把起算點暫設成 `MYL-122` 連線重現：exit 1、3 條改不掉的紅字）。出口是**覆核完成標記**（條文 `I1` 第 2 點、留言形狀見 `paperclip.md`），體例同 `Mirror-skipped:` |
| L29 | 想在開單當下就把「本單擋住誰」填好，讓 `I2` 的五欄齊備；並以為「子單不得把母單當 blocker」平台上有現成的設定可切 | **兩件事都做不到，而且失敗的方式不一樣。**（a）**下游欄根本沒有寫入路徑**：依賴在資料層只有 `blocks` **一種**關係型別、一條實體邊，`blockedBy` 與 `blocks` 是同一張表的兩個讀取方向；全 API 唯一可寫的是**下游那張單自己的 `blockedByIssueIds`**（建單 schema 也沒有 `blocks`／`blockingIssueIds`）。⇒ 要一張單的下游欄非空，只有「後來有人開單、把它填進自己的上游欄」這一條路，開單者當下填不了。（b）**「母單不得同時是 blocker」沒有守衛**：寫入路徑上只有三道檢查——不得自我阻擋、必須同公司、`blocks` 圖不得成環——**父子關係完全不在其中**（環的偵測只走 `blocks` 邊，不看 `parentId`）。所以 `blockedBy` 填自己的母單會**照收 200**，做出一張醒不來的單：blocker 只有停在 `done` 才算解除，而母單多半要等子單做完才結 | （a）從 `I2` 的必備欄位拿掉，改成條文裡的【自律】句「開單當下已知的下游工作要一併建出來」（使用者於 MYL-116 卡 `117b822a` q2 裁定）；多張一起建時走批次建子單路徑，鏈由伺服器串。（b）同樣降級成規則層攔：`I2` 多一格反向判準，由 `--selfcheck` 的 `pm-issue-fields` 事後報。⚠️ 兩件都**不是「暫時還沒做」**——(a) 是資料模型使然，(b) 是守衛清單使然，別回頭去找那個開關。實查全 124 張單，`blockedBy` 含 `parentId` 的目前是 0 張，這一格是預防不是止血。（2026-09-07 MYL-116 讀伺服器原始碼＋逐張單筆端點實查） |
| L30 | 貼完留言後照 `paperclip.md` 早先寫的 `GET /api/issues/<ID>/comments \| jq '.[-1].body'` 回讀，確認內容未截斷 | **讀到的是最舊那一則**，不是剛貼的那一則——這份陣列是**新到舊**，`index 0` 才是最新（2026-09-07 MYL-131 對 MYL-129 的 6 則留言實測，`createdAt` 由 `14:31` 遞減到 `12:46`）。失敗方式視情境分兩種：單上原本有留言 ⇒ 比對到別人的內容、**誤報截斷**；單上原本沒有留言 ⇒ `.[-1]` 恰好就是剛貼的那一則、**驗證假綠**，而那正是「第一次貼」的情形 | 不要依賴排序：`POST …/comments` 回的就是那則留言本身（含 `id`），拿它打 `GET /api/issues/<ID>/comments/<commentId>` 單筆回讀。只能走清單時用 `.[0]`。`adapters/paperclip.md` 的 `comment` 查證那一行已隨本條訂正 |
| L31 | 想知道 `effort`／`model_reasoning_effort` 有哪些合法值，於是去讀本地那份 adapter CLI 的說明，或拿 `codex debug models` 的 catalog 當白名單，照它填 `MODEL_TARGETS` | **值域不歸我方所有，本地每一份自述都是過時散文，而且沒有任何一份是完整的。**（a）**權威在供應商伺服器，且隨 model 而異**：`gpt-5.6-sol`／`gpt-5.6-terra` 吃 `max`，`gpt-5.5` **只到 `xhigh`**——同一個值換一個 model 就非法，值域不能離開 model 單獨談，「這個 effort 合不合法」永遠是 model×effort 的配對問題。（b）**兩端 adapter CLI 自述的值域都已過時，不得當權威**：`codex-local/src/index.ts:27`（`0.3.1` 樹；平台實跑的是 `@paperclipai/adapter-codex-local` `2026.831.1`，對應 `dist/index.js:84`，兩棵樹同文）寫 `minimal\|low\|medium\|high\|xhigh`，**漏了 `none` 與 `max`**；`claude-local/src/index.ts:20`（`0.3.1` 樹；`2026.831.1` 對應 `dist/index.js:37`）寫 `low\|medium\|high` 同樣過時——claude 側 UI 是自由字串、server 不驗，而平台此刻正以 `effort: max` 跑 high 層三名且運作正常。兩端 CLI 對 effort 皆**零驗證**，把關的是伺服器。（c）**`codex debug models` 的 catalog 與伺服器 400 回的 enum 是兩個不完全重疊的集合**：catalog 有 **`ultra`**、enum 沒有；enum 有 `none`／`minimal`、catalog 沒有（2026-09-08 實測 `gpt-5.6-sol` catalog ＝ `low, medium, high, xhigh, max, ultra`；400 enum ＝ `'none', 'minimal', 'low', 'medium', 'high', 'xhigh', and 'max'`）。⇒ 拿其中一份去對另一份會得到「少了兩個值」的假警訊，任取一份當白名單也都會漏 | **只問伺服器，而且要連 model 一起問**：`codex exec --skip-git-repo-check -c model="<model>" -c model_reasoning_effort="<值>" "reply with exactly: OK"`——接受時 session header 回報 `reasoning effort: <值>` 且 rc 0；不接受時伺服器回 **400 `[ReasoningEffortParam] [reasoning.effort] [invalid_enum_value]`＋rc 1**，訊息自帶該 model 的完整合法值域。**會炸、不會靜默降級**，所以這件事不需要本地攔截。⚠️ 取 rc **不要經過管線**：`… \| tail` 的 rc 是管線最後一段的、恆為 0，會讓「拒收」看起來像「接受」，rc=0 那一半的證據就失去鑑別力（MYL-133 CR 實際踩過）。⇒ 本 repo **刻意不對值域做機械驗證**：任何本地白名單都必然重蹈上面兩份散文的覆轍，而失敗是響的、代價只有「時間差落在被改動 agent 的下次喚醒」。`tools/model-routing/apply_profile.py` 的 `MODEL_TARGETS` 旁只留「high 層用 `max`，不要改成 `xhigh`」**那條決定**，查證與理由一律回到本條——決定貼著它拘束的那張表，事實只有這裡一份。（2026-09-08 MYL-133 交付＋CR 獨立重跑三項證據，MYL-135 收容；同時銷掉 CR 建議 1 的版本註與建議 2 的 `ultra` 分岔點） |
| L32 | 一個 run 內接連動很多張**別人的**單——補留言、PATCH 敘述／狀態、回應互動卡——當它跟動自己那張單一樣沒有上限；或撞到 429／403 就換個寫法、退避重打 | **每個 run 的跨單寫入有 20 筆硬上限，撞到之後同一個 run 內怎麼重試都沒用。**（以下行號皆為平台**實跑**的 `paperclipai` **`2026.831.1`** 那棵樹的 `@paperclipai/server/dist`；⚠️ **取證前先驗明正身**：`ss -lptn 'sport = :3100'` 找出佔住 API 埠的 process → `ps -eo pid,args` 讀它的指令列 ⇒ `~/.paperclip/cli/current/…/paperclipai/dist/index.js`，而 `cli/current` 解析到 `installs/npm/2026.831.1`。npx 快取目錄底下另有一份 md5 完全相同的同名檔，**別拿它當權威**——本檔已有「讀到的不是正在跑的那棵樹」的同型誤判前例）。（a）上限常數 `CROSS_ISSUE_INFLUENCE_LIMIT = 20`（`services/cross-issue-influence-limit.js:6`），**2026-08-11T00:00:00Z 起才真的 `enforce`**、之前是 `log_only`＝一律放行只記帳（同檔 `:7`／`:28`／`:31`）⇒ **現在已在強制期**。（b）**只算「跨單」**：目標單＝本 run 的來源單（`contextSnapshot.issueId`／`taskId`）時提早 return、不計數（同檔 `:69`–`:75`）⇒ 動自己那張單幾次都不扣。（c）**一個 run 內累計、途中不重置**：計數基準是 `activity_log` 裡該 `runId` 的 `issue.cross_issue_influence_observed` 筆數（同檔 `:76`–`:80`）。（d）🔴 **觀測寫在路由變更之前**，原始碼註解明講就是為了不讓失敗被拿來探邊界（同檔 `:38`–`:45`／`:82`）⇒ **一次後來因別的原因失敗的寫入，額度照樣扣一筆**；`routes/issues.js` 的 PATCH 就有現成例子——計數在 `:7749`–`:7754`，緊接著 `:7757` 那個 400（`interrupt` 沒帶留言）已經是扣過之後才回的。被上限擋下的那一次改記成 `…_cap_rejected`、**不計入** observed（同檔 `:89`–`:91`）⇒ 撞牆本身不再多吃額度，但**已經用掉的 20 筆救不回來**。（e）🔴 **一次 PATCH 可能扣兩筆**：`:7750` 的 `update` 與 `:7753` 的 `comment` 是**兩道各自獨立、互不排斥**的檢查，同一個 PATCH 既帶欄位又帶 `comment` 時兩道都會走 ⇒ 扣 2。（f）只拘束 `req.actor.type === "agent"`，**使用者不受限**（`routes/issues.js:1982`）；受管的三種 `kind` 全檔僅 **5 個呼叫點**：`interaction_resolution`（`:3154`，互動卡的**回應**）、`update`（`:5271` 在 `POST /issues/:id/recovery-actions/resolve`、`:7750` 在 `PATCH /issues/:id`）、`comment`（`:7753` 同在該 PATCH、`:10105` 在 `POST /issues/:id/comments`）。**不在射程內**：建新單（`:6783`）、`POST …/interactions`（**掛**卡，`:9220`）、文件 `PUT`——全 server dist 只有 `routes/issues.js` 參照那個 wrapper | **把跨單寫入當預算來排，不要當可重試的失敗。** 一輪要動很多張單時：同一張單的多則留言**先合併成一則**、能不 PATCH 就不 PATCH、真的不夠就**拆到下一個 run**（原始碼自述這是 **rate backstop 不是權限判定**，處置就是下一個 run，同檔 `:129`–`:131`）。⚠️ **429 與 403 是兩回事，別混在一起退避重打**：超限回 **429** `cross_issue_influence_cap_exceeded`、body 帶 `cap`／`count`／`mode`／`enforceAt`（同檔 `:129`–`:147`，狀態碼在 `routes/issues.js:2003`）——**改寫法無用，只能等下一個 run**；而缺 `runId`／`agentId`、`runId` 不是 UUID、或 run 列對不上 company／agent 是 **403** `cross_issue_influence_run_context_required`（同檔 `:10`–`:15`／`:46`–`:71`），那是**形狀問題**、把 `X-Paperclip-Run-Id` 補對就過，而且**不吃額度**。⚠️ **不要為了取證去真的撞 429**：撞下去會把那個 run 剩餘的跨單寫入全部打死，而上面每一項讀原始碼就拿得到。（2026-09-08 MYL-137 收容，承接 MYL-117 CR 第 1 輪次要建議 4；⚠️ 行號隨版本會漂，覆核時先照上面的取證法確認版本仍是 `2026.831.1`） |

## 2. API 形狀陷阱：會回 4xx 但錯誤訊息不會告訴你原因

| # | 陷阱 | 正確寫法 |
| --- | --- | --- |
| S1 | 互動卡內容放頂層 `body` → 422 | 必須包在 `payload` 物件：`{kind, idempotencyKey, continuationPolicy, title, payload: {version: 1, ...}}`。`ask_user_questions` 的問題欄位叫 **`prompt`**（不是 `question`），`version` 與 `selectionMode` 都必填 |
| S2 | `PUT /api/issues/{id}/documents/{key}` 放 `content` → 400；沒帶 `baseRevisionId` → 409 | 必填 `format: "markdown"`＋`body`＋`baseRevisionId`（現行 revision id） |
| S3 | `POST /api/issues` 開單 → 404 | 開單走 `POST /api/companies/{companyId}/issues`。該 endpoint 在 `openapi.json` 的 requestBody schema 是**空的**，欄位名以 GET 單一 issue 的回傳形狀為準 |
| S4 | 開單時直接設 `status: in_progress` → 被別的 heartbeat 搶走 checkout，隨後自己發卡回 409 `Issue run ownership conflict` | 先建成 `todo`／`backlog`，**發完卡再轉狀態** |
| S5 | `PATCH /api/issues/{id}` 的 `unblockDescriptor.owner` **三種形狀三種結果**，原記載（MYL-52）只碰到其中一種、判成「寫不進去」。另有一個會**先**撞到的前提：這個欄位**只在 `blocked` 狀態下收** | ⚠️ **前提先看狀態**：issue 不是 `blocked` 時，整個 `unblockDescriptor` 在 owner 檢查**之前**就被擋掉，回 **422 `unblockDescriptor requires blocked status`**——走不到下面三種形狀那一層（2026-09-06 MYL-95 覆驗；該路徑是**原子**的，同批送的 `priority` 也沒寫進去）。**狀態是 `blocked` 之後，三種形狀分開看**：(a) `owner` 填**別的** agentId → **403 `Agents may only name themselves as an unblock owner`**，整包不生效（原子性是**單次觀測**：2026-09-06 MYL-100 開發者以「403 之後回頭 `GET` 確認 `status`／`unblockDescriptor` 都沒被寫入」第一次正面驗到；MYL-106 CR 想覆驗時該單已被調和回 `in_progress`，撞到下面那個前置 422，**未能取得第二次**）——**不是靜默**，訊息講得很清楚；(b) `owner` 填**裸字串 id**（不論是不是自己）→ **400 `Validation error`**，`path: ["unblockDescriptor","owner"]`；(c) `owner` 填 **`{"agentId":"<自己>"}`** → **200 且確實寫入**。⇒ MYL-52 判定「填自己也不生效」的真正原因是 (b) 的**形狀錯**，不是權限。`owner` 是 union：`{"agentId":"<uuid>"}`／`{"userId":"<id>"}`／字面 `"board"` 三選一。`openapi.json` **現在查得到完整 schema**（`oneOf` 三型、`required: [owner, action]`、`additionalProperties: false`），原記載「沒有任何 schema、形狀無從查證」已不成立。⇒ 要表達「這張單在等別人」：**owner 只能填自己**，等誰用 `blockedByIssueIds` 掛一級 blocker 表達（`blockerAttention` 會算出 `terminalBlockerIssueId` 與 `sampleBlockerIdentifier`），`unblockDescriptor.action` 寫**自己**在對方完成後要接手做什麼。⚠️ 400 與 403 要分開讀：前者是形狀錯（改形狀就好），後者是權限邊界（改不了，換表達方式）——原記載把兩者混成一句「靜默不生效」，於是給出「不要填這個欄位」這個現在已經錯誤的處置。⚠️ 轉 `blocked` 時另外要顧的是 **`unresolvedBlockerCount` 不能是 0**（⚠️ 這個欄位在 `GET /api/issues/{id}` 的 **`blockerAttention` 物件底下，不在頂層**——照字面在頂層找會找不到，2026-09-06 MYL-79 合併前實查回應的頂層鍵無此名）：`blocked` ＋ 零未解 blocker 會在 run 結束時被調和回 `in_progress` 並立刻排下一個 run（MYL-79 第 4 輪實測，41ms），那是零延遲無界迴圈、每圈都讓鏡像不同步。⚠️ **另一個方向的 422，兩邊合起來是雞生蛋**：反過來，對一張沒有未解 blocker、也沒帶 descriptor 的單直接送 `{"status":"blocked"}` → **422 `Entering blocked requires unresolved blockers, a pending interaction/approval, or unblockDescriptor`**。訊息列舉的**三種合法理由**：①有未解的一級 blocker（`blockedByIssueIds`）、②有 pending 的互動卡或核可、③同批帶 `unblockDescriptor`。第 ③ 種正是本欄開頭那個 422 的另一端——**descriptor 要 `blocked` 才收，`blocked` 又要 descriptor（或另兩種理由）才進得去**，拆成兩次 PATCH 則兩次都吃 422，先送哪一邊都一樣。⇒ **正解是同一包 PATCH 一起送**：`{"status":"blocked","unblockDescriptor":{"owner":{"agentId":"<自己>"},"action":"<解鎖後自己要接手做什麼>"}}` → **200，兩個欄位都寫入**（2026-09-06 MYL-110 實測）。同一輪另外觀察到：**離開 `blocked` 時 descriptor 會被一併清掉**——只送 `{"status":"in_progress"}`，回頭 `GET` 的 `unblockDescriptor` 已是 `null`，不必也不能靠它留痕。**這兩個 422 的觀測人次要分清楚**：「進 `blocked` 需要理由」在 MYL-100（開發者）、MYL-106（CR）、MYL-110（開發者，含 422 後回頭 `GET` 確認 `status` 仍是 `in_progress`）三張單上各實測一次，回應碼與訊息逐字相同，但三次中有兩次出自**同一個 agent**（`023c9a75`），不是三人獨立觀測；「非 `blocked` 單送 descriptor」則在 MYL-95、MYL-106、MYL-110 三張單上以完整合法 body 覆驗過，一致。條目依維護規則保留供追溯 |
| S6 | agent 把工單 PATCH 成 `in_review` → `invalid_issue_disposition` | 需先存在真實審查路徑（pending 的互動卡）。順序：**先發卡、再改狀態** |
| S7 | 想把自己開的子單推進 `in_progress` → `in_progress issues require an assignee`；補上 `assigneeAgentId` 之後**再也 PATCH 不動那張單**，回 409 `Issue run ownership conflict` | **指派＝喚醒**，即使指派給「正在跑的自己」也一樣：Paperclip 會為那張子單另開一個併行 run，該 run 一 checkout 就成為單的擁有者，父 run 從此不能改它的狀態、也不能 `release`。而 `POST /api/heartbeat-runs/{id}/cancel` 是 **board-only（403）**，父 run 收不回來。⇒ 子單只要會被推進 `in_progress`，就**當成會生出一個併行 run 來設計**：先把它的描述與留言寫到足以讓那個 run 獨立完成，並明確寫出它**不該**碰什麼（尤其 git——共用 workspace 見 §5 `X1`）。不需要它跑起來就別指派，把單留在 `todo`。（2026-09-05 MYL-54 實測） |
| S8 | 把腳本貼進留言 → **貼上去的那份跑不起來**，回報者照抄會撞 `SyntaxError: unterminated string literal`。原文正確、`json.dumps` 也正確，看起來完全沒問題 | `POST /api/issues/{id}/comments` 會把 body 裡的**反斜線-n 還原成真換行**。實測：送出去的是 `re.findall(r"…markdown\\n(.*?)…")`（json 裡是 `\\\\n`），撈回來變成字串中間真的斷行。行內的 `"…\n…"` 於是變成未終結字串。⇒ **貼給人照抄的腳本裡一個 `\n` 字面都不要有**：Python 用 `NL = chr(10)` 再 `NL.join([...])`／字串相接；其他語言同理。貼完**撈回來 diff 原檔**再說「可執行」。已栽三次（MYL-87 兩份、MYL-91 一份）（2026-09-06 MYL-91 實測） |

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

### ~~R6 — 把 agent 實際換到別的供應商：使用者裁定「先不改」（MYL-36）~~ 前半已由使用者自己取代（MYL-125，2026-09-07）

**⚠️ 這一條的「先不改」已經失效，不要再拿它擋切換。** 條目保留供追溯，並保留仍然成立的那一半。

- **原裁定**：2026-09-03 裁定卡 `ask:MYL-36:platform-routing:v1`，pilot 題選 **`none`**。原文：
  「我認為目前 paperclip 內的先不用跑」「目前 paperclip 先不實際改任何 agent 設定，**提供這樣的功能即可**」。
  當時的意思是**能力就位、開關不開**：盤點腳本、路由規則（`M4`～`M6`）、`foundry-model-routing`
  workflow、`.foundry/config.yml` 的 `model_routing` 段全部落地，但不動任何 agent 的 `adapterType`。
- **取代它的事實（2026-09-07）**：使用者已實際把 Developer 與 Code Reviewer 切到 `codex_local`，
  並在 MYL-125 核可「工具化」的執行計畫。⇒ 開關已經開了，而且是使用者自己開的。
  MYL-128 據此寫入 `.foundry/config.yml` 的 `model_routing` 段（`codex-emergency` 為 active），
  並把 `M6` 改成兩級常設授權。**「7 個 agent 全在 `claude_local`」這句已不成立**，
  引用它去論證任何事之前先自己查一次平台實況。
- **仍然成立的那一半**：使用者陳述的目的是**觀點互補**（「不同服務商提供的模型會有不同觀點，可以補足」），
  不是省額度、不是吞吐。這一句沒有被取代——之後若有人以「省額度」為由重提任何路由改動，
  那是另一個提案，判準不同，**不能援引 MYL-36 或 MYL-125 當背書**。
  （`codex-emergency` 這個 profile 看起來像「為了省額度」，實際上是額度耗盡下的收容，
  兩者的差別寫在它的 `waiver_reason` 裡：它有結束條件，省額度型的改動沒有。）

### R7 — 舊手冊網址的轉址頁：寫好了，使用者裁定不要（MYL-55）

- **背景**：手冊精裝站從 `foundry-handbook` 搬回 `agent-foundry` 之後，舊網址
  <https://augustushsu.github.io/foundry-handbook/> 會失效。MYL-55 已把轉址方案寫成
  `scripts/redirect-old-mirror.sh`（九頁一對一、先驗新站 200 才動手）。
- **裁定**：2026-09-05 互動卡 `dc818205` 第 3 題選 **`break`（直接斷）**——不轉址，
  使用者直接封存 `foundry-handbook`，舊網址變 404。腳本**已隨本裁定刪除**。
- ⚠️ **裁定的前提有一半沒成立**：2026-09-05 執行封存後實測，舊站**仍回 200**——
  封存只讓 repo 唯讀，不會關掉已部署的 Pages（`L18`）。所以「不轉址」這半做到了，
  「變 404」那半沒有。
- **最終處置（2026-09-05，卡 `0a46a84a`）**：使用者以自由文字回覆「**可以直接刪除那個舊站的
  repo**」——這推翻了工單原本「**不刪除**，只封存」的範圍限制，以使用者這次的裁定為準。
  agent 代刪失敗（`DELETE repos/AugustusHsu/foundry-handbook` → 403，缺 `delete_repo`
  scope，見 `L20`），依卡片的但書交回使用者手動執行。⇒ **舊 repo 與舊站的最終狀態是「刪除」**，
  不是「封存保留」；下一個 session 若在文件裡讀到「封存保留」的舊敘述，那是本次之前的版本。
- **為什麼記在這裡**：那支腳本的 header 把「必須在封存前跑」寫得很像待辦事項，
  下一個 session 從 git 歷史翻到它、或看到 README 提及舊網址，很容易判斷成
  「這件事漏做了」而重寫一份。**它不是漏做，是被否決。**
- 重提的前提：舊網址真的有外部流量或引用需要接（目前唯一的內部引用
  `skills/foundry-init/SKILL.md` 已改指新站）。**repo 刪掉之後轉址就徹底不可能了**
  ——連解封存再推這條退路都沒有，只剩「重建一個同名 repo」這種明顯不成比例的成本。

### R8 — 訂正過期宣稱時只 grep「症狀」或只 grep「宣稱本身」：兩者都不夠，要連下游一起抓

- **試過**（同一失效模式連續發生兩次，第二次是在已經知道第一次的情況下）：
  - **MYL-77 複審**：只 grep「症狀」（被那句宣稱推導出來的錯誤結論），沒 grep 宣稱本身
    ⇒ 漏掉 `foundry-init`／`foundry-adopt` 四處，事後另開 MYL-90 才清掉。
  - **MYL-90 第 1 輪**：這次 grep 了宣稱本身、四處都改對了，但沒 grep 它們的**下游**
    ⇒ `foundry-init` §5 報告待辦、`foundry-init`／`foundry-adopt` 兩處 §6 驗收自查仍寫舊講法
    （「人工建」「待人工建立」的 agent），同一份檔案自己說反話，被 Code Reviewer 退件。
- **結果**：**關鍵詞會漂**——同一件事在宣稱處與下游用詞不同（上游是「沒有動詞」「不會把 agent
  建出來」，下游是「人工建」「待人工建立」），同一組 grep 抓不到。
  而且**只改上游比全不改更危險**：驗收自查是這類檔案最強的指令形態（「缺一項就不算跑完」），
  下游沒跟上時，讀者為了把那一項打勾，會把舊講法原樣**寫回**報告。
- **正解**：訂正一句宣稱時，除了改掉它本身，還要問「**這句話還被誰引用／複述**」——
  報告待辦項、驗收自查清單、跨檔的同型敘述——逐一 grep 確認沒有說反話。
  grep 詞要**從下游的用語再找一輪**，不能只拿上游的特徵句掃一次就算數。
  這兩份檔的固定下游是：`foundry-init` §5 **初始化報告**列的待辦、`foundry-adopt` 散在 §1／§3 的
  **「報告記一筆」**，以及兩份各自的 §6 **驗收自查**——動它們的正文，一律回頭看這幾處。
- **為什麼不做成 `--selfcheck`**：本條記載的失效模式本身就是「同一件事上下游用詞不同」，
  機械檢查要靠一份關鍵詞清單，而**那份清單會跟著漂**、注定掃不全；
  一項掃不全的檢查只會給人虛假安全感，比沒有更糟。
  （Code Reviewer 於 MYL-90 留言 `739030d1` 論證，MYL-93 裁定採納：**立案記在這裡，不寫進 protocol**。）
- **來源**：MYL-77（第一次失手）／MYL-90（第二次失手＋CR 退件）／MYL-93（裁定立案）。

## 4. 已知缺口：使用者知情下保留，不要當成待辦自行修掉

| # | 缺口 | 出處與裁定 |
| --- | --- | --- |
| ~~GAP-1~~ | ~~**額度用盡沒有成文處置。**~~ **已關閉（2026-09-03，MYL-36）**：使用者在 `ask:MYL-36:platform-routing:v1` 要求「額度耗盡……可以透過這個 workflow 自動指派」，已成文為 protocol 第 8 節 `M5` ＋ `foundry-model-routing` §5。條目保留供追溯：MYL-33 當時的 `no_clause` 裁定已被本次裁定取代 | MYL-33 v3 卡 `no_clause` → MYL-36 卡取代 |
| GAP-2 | **高層無梯可升。** `M1` 寫 `low→medium→high`，但高層預設已站在 `max`；高層 agent 連續失敗兩次時 `M1` 無法適用，需臨場改走 `M3` 轉 `blocked` | MYL-33 v3 卡裁定 `ladder_no_change` |
| GAP-3 | **`.foundry/config.yml` 的 `push` 段表達不了本 repo 現況。** MYL-23 P1「合併回 main 後 push origin 由執行者自行」寫不進 schema，權威來源是 protocol 第 7、9 節的分級表文字 | MYL-35 G7 選項 A，見 R4 |
| GAP-4 | **`claude_local` adapter 內建說明字串的 `effort` 只寫到 `(low\|medium\|high)`，已過時。** 實際支援 `low/medium/high/xhigh/max`；adapter 對 `effort` 原樣傳給 CLI 不做驗證 | 實測 `claude-opus-5`＋`max` EXIT=0。protocol 第 8 節附註已載明 |
| GAP-5 | **瀏覽器工具綁的是「情境」不是「人」。** `.mcp.json` 放在共用 repo 裡，該 repo 的**所有** agent 都拿得到瀏覽器工具，不只 Frontend Verifier。要真正做到 per-agent 綁定得靠平台 tool-profile（`L7`，board-only） | MYL-37 卡 `myl37:frontend-verifier:plan:f7cf0b84` 的 `gateway: gateway_now`——使用者選擇由自己在 UI 補上閘道，能力層不等它。**2026-09-04 更正：這條缺口用閘道關不掉**——stdio 型 MCP 送不進 agent session（`L10`），硬掛遠端連線反而會把 `.mcp.json` 整份廢掉（`L9`）。維持 `.mcp.json`、以「不把遠端 app 授權給 Frontend Verifier」為代償規則 |
| GAP-6 | **`handbook-stamp` 只驗「有動到手冊任一檔」，不驗「動到對應章」。** `unsynced_protocol_commits()` 看的是 `diff-tree ... -- docs/handbook` 有沒有輸出，所以「改 protocol 第 3 節、手冊只動 `06` 章、`03` 章戳記仍停在舊 sha」四章照樣全綠（MYL-73 的 `0a0b461` 就是這個形狀）。**刻意不做**：protocol 的節與手冊的章不是一對一，硬做對應表等於新增第二份要人工維護的映射，而那正是本 repo 反覆記錄的漂移來源——這道閘門要擋的是「完全沒看手冊」，「哪一章要改」的判斷本來就在層 2 的 agent 身上 | MYL-76 AC10 判定（工單授權「先判斷值不值得做」，由 Developer 判；非使用者裁定）。判準與這條缺口一併寫在 `check_handbook_stamp()` 的 docstring，避免下一個人重新發現一次 |
| GAP-7 | **來源工單上陳舊的 `Mirrored-to:` 登記沒有任何機械偵測。** 對帳只讀鏡像 issue 的 body 首行（那是唯一權威），所以來源端那則反查快取指到一張**已經脫鉤的 issue** 時，`mirror-recon` 照樣全綠。MYL-104 上的 `Mirrored-to: github#38` 就是這個形狀——`#38` 已於 05:07:03 移除標記，登記留言仍在。**刻意不做**：要驗它得對每張來源單撈留言（本 repo 現況 51 張＝每次多 51 次 API 呼叫），而 `fetch_source_issues()` 現在只對「看起來漏建」的那幾張撈，正是為了避開這個成本 | MYL-108 判定不修。代償是**人手更正**：發現作廢的登記時在來源工單補一則更正留言把它標明（平台不提供刪留言），並在 adapter「收斂重複鏡像的手法」列為必做的第三步 |

## 5. 併發與競態：多個 run 共用同一個 workspace

本 repo 的 workspace 是**共用**的，heartbeat run 可能併行；`X3` 起也一併收**「工具跑出來的結果跟來源字面不一樣」**這一類踩點——`X3`／`X4` 是 mkdocs 的渲染，`X5`／`X6` 是 CI 的 checkout 形狀與 git hook 的環境變數。共通的形狀是：**來源沒錯，錯的是它被放進了哪個環境**，所以錯誤訊息往往指向錯的地方。以下每一條都真的發生過。

> ⚠️ 編號訂正（2026-09-06，MYL-76 收尾）：本節原本有**兩組重複的 `X5`／`X6`**，後加的那組已改編為 `X7`／`X8`。
> 兩條的**內容一字未動**——本檔「只增不改」約束的是條目內容，不是讓重複的鍵留著；同一個 ID 指到兩件事，引用它的人分不出是哪一件。訂正前無任何檔案在本檔之外引用 `X5`／`X6`（已 grep 全 repo 確認）。

- `X1` **commit 落到別人的分支。** 兩個 run 併行時 checkout 會互相干擾（MYL-23 的 commit 曾落到 MYL-27 的分支）。
  → **commit 前先驗 `git symbolic-ref --short HEAD`**，不要假設分支還是你切的那條。
  → **但驗過不等於安全：驗完到 commit 落地之間還有一段時間窗，HEAD 一樣會被搶走。** 2026-09-05 MYL-86 實測——commit 前驗到的是 `feat/MYL-86-init-copy-list`，commit 落地時 HEAD 已被併行的 MYL-77 run 換成 `feat/MYL-77-provision-team`，commit 就落在對方分支上。**上一條止血擋不住這一格**：它只證明「按下 enter 的前一刻」是對的，不保證落地那一刻還是。
  → **落錯之後的復原：三步全是純 ref 操作，不碰任何人的工作區檔案。**（`<本單分支>`／`<基底>` 換成當時的值；MYL-86 當時分別是 `feat/MYL-86-init-copy-list` 與 `d6781de`）
    1. `git branch -f <本單分支> <落錯的 commit>` — 把 commit 收回自己的分支；
    2. `git reset --soft <基底>` — HEAD 留在對方分支上，只把**對方的** branch ref 退回基底；index 不動；
    3. `git checkout <基底> -- <本單改到的檔案>` — **逐檔列出**自己改的那幾個，只還原它們。
    ⚠️ **絕不用 `git reset --hard`。** 共用 workspace 的工作區裡有別人**尚未 commit** 的修改，`--hard` 會連同吃掉，而那些改動沒有任何副本、救不回來。第 3 步要逐檔列出是同一個理由：不要用會波及整個工作區的寫法。
  → **迴避法（已驗證，優先於事後復原）：`git clone --shared` 開隔離 clone，在裡面改／測／commit，再 `git push origin <非 HEAD 分支>` 送回。** 隔離 clone 有自己的 HEAD，併行 run 換不動它，**連 commit 這一步都不必冒 `X1`**；物件庫共用，push 回來不必複製歷史。推的分支不能是共用 repo 當下的 HEAD（非 bare repo 會拒收）——而那正好是安全的那一邊，你要推的本來就是自己的分支。**同一張 MYL-86 兩種做法都試過**：實作那一輪沒用隔離 clone，就是上面撞上時間窗的那一輪；改用之後從第一輪覆審到合併連續六輪（三輪覆審／兩輪修正／一次合併）全走這條，期間共用 workspace 一直被 MYL-77 佔著，再沒撞上 `X1`。
  → 這一招同時解掉**「共用 workspace 被別人佔住時要怎麼動手」**：不必等、也不必搶 HEAD。（`X8` 的 linked worktree 是另一條路，差別是 worktree 會換掉 hook 的環境，見 `X6`。）
  → ⚠️ **在隔離 clone 裡，`origin` 是共用 workspace，不是 GitHub。** MYL-86 的 CR 報告寫「已推 origin」，被讀成推上了 GitHub，實際對 GitHub `git ls-remote` 查是空的——該分支從來只存在於共用 workspace。**寫報告時要指名推去哪個 origin**，否則 `P1` 的「刪已合併的遠端分支」會被誤判成有對象。
  → 連帶的環境差異：隔離 clone 預設**沒有 GitHub remote**，`mirror-recon` 在裡面是 ⏭ 不是 ✅。那是環境所致、不是缺陷，但也代表**在隔離 clone 跑 `make check` 驗不到鏡像對帳**——要驗那一項得另外把真的 GitHub remote 接上去。
- `X2` **發佈互蓋。** MYL-25 收尾 run 以較舊的來源樹在 MYL-32 之後 push，蓋掉了 02／03 章的新內容。
  → **發佈後要驗遠端實際內容，不能只看腳本回報成功**；發現被蓋掉就以最新 main 重跑。
- `X3` **手冊錨點與 mkdocs slug 不符。** 中文標題的錨點不是中文字面，是 mkdocs 產生的 slug（`#1`、`#3-hitl`…）。手寫中文錨點會變成點了不跳轉的死連結（MYL-25 踩過）。
  → 已納入 `foundry-lint --selfcheck` 的機械檢查。
- `X4` **兩塊連續的 blockquote 會被 mkdocs 併成同一塊，空行擋不住。** Python-Markdown 的 blockquote 處理器看的是「前一個兄弟節點是不是 blockquote」，是就往裡面接。所以「`>` 戳記 → 空行 → `>` 章引言」渲染出來是**單一 `<blockquote>` 內含兩個 `<p>`**，視覺上一條左側豎線同時包住戳記與引言。MYL-49 在公開站實測 `04`／`06`／`07` 三章皆如此；`03-workflow` 沒事只是因為它戳記後面接的是一般段落，不是錨點挑得比較好。
  → **MYL-44 判定不修**（2026-09-04）：戳記的功能目的（讀者看得到最後對照的 protocol sha）已達成，`handbook-stamp` 要驗的東西全部成立，嚴重度純視覺。改戳記形式（例如換成斜體段落）會連動 `STAMP_RE`、pre-commit 觸發器、protocol 第 7 節條文、四章來源檔，還要再走一次發佈循環與一次視覺覆驗——為一條豎線不值得。**下一個看到的人請不要順手「修好」它**，要動先在工單裡把上面這串連動成本重新算一次。
  → 連帶的環境事實：**agent 在本機驗不了渲染。** 這個 workspace 的 `python3` 沒有 `markdown`、沒有 `mkdocs`，也沒有 `pip`（CLAUDE.md 第 6 節列的 `mkdocs serve` 是給使用者的，不是 agent 跑得動的）。⇒ 任何「這樣寫渲染出來會長怎樣」的假設，都只能靠公開站實測驗證，而那得先發佈——順序是反的。動手改渲染相關的東西前先認清這件事：你手上沒有便宜的驗證手段。
- `X5` **淺 clone 讓 `handbook-stamp` 必然失敗，而且訊息指向錯的地方。** CI 的 checkout 停在 `fetch-depth: 1` 時，戳記指到的歷史 commit 在淺 clone 裡不存在，四章一起報「戳記 sha 不是本 repo 的 commit」——看起來像手冊寫錯，實際要改的是 workflow。main 為此連四顆 commit 全紅（MYL-53 發現，`D1` 退回 MYL-44）。
  → 已修：`fetch-depth: 0`，並在 `check_handbook_stamp` 加淺 clone 偵測，改報一則直指 `fetch-depth` 的訊息。**擋下而不是略過**——略過等於閘門在淺 clone 下無聲失效。
  → 更一般的教訓：**「CI 跑的內容與本機 `make check` 相同」不等於「CI 與本機等價」**。相同的是指令，不同的是 checkout 形狀。新增吃 git 歷史的自檢時要一併看 `fetch-depth`。
- `X6` **從 worktree 裡 commit，會讓所有「開臨時 git repo」的測試改去操作外層真正的 repo。** git 跑 hook 時匯出 `GIT_DIR` 與 `GIT_INDEX_FILE`，而它們的優先序高於 `-C`。從**一般 checkout** commit 時兩者是相對路徑（`GIT_INDEX_FILE=.git/index`、沒有 `GIT_DIR`），`-C` 照常生效；從 **worktree** commit 時兩者都是絕對路徑，於是 `git -C <臨時目錄>` 被悄悄導回外層 repo。症狀是 `HandbookStampTest` 24 個測試一起倒在 `setUp`，錯誤訊息卻是「No .pre-commit-config.yaml file was found」，看不出跟 git 有關（MYL-44 `D1` 修復時踩到）。
  → 已修：`git_run()` 與測試的 `git()` 共用 `foundry_lint.git_env()`，把 `GIT_LOCATION_ENV` 那幾個變數清掉，讓 `-C` 說了算。
  → **用 worktree 迴避 `X1` 是對的**（HEAD 不會被併行 run 移走），但要知道它會換掉 hook 的環境。任何「shell out 去跑 git」的新程式碼都要走 `git_env()`。

- `X7` **git 呼叫 hook 時會設 `GIT_DIR`，而它勝過 `git -C <路徑>`。** 於是「在臨時目錄造一個 repo 來測」這種測試，在 pre-commit 底下跑會被拉回**外層 repo**：臨時 repo 根本沒建起來，接著的 commit 觸發外層 hook、在臨時目錄找不到 `.pre-commit-config.yaml` 而整組紅。
  症狀極難認：**單獨跑 `make test` 全過，`git commit` 觸發同一組測試時全敗**，而且 `foundry-tests` 這個 hook 只在 staged 檔案含 `tools/` 時才觸發，所以它平常隱形，只在動到 `tools/` 的那次 commit 現形（MYL-52 撞上，當時 22 項全紅）。
  → 已修：`test_foundry_lint.py` 與 `tools/publish-docs/test_publish_gate.py` 在**模組載入時**就把 `os.environ` 裡的 `GIT_*` 清光，並各留一項回歸守衛。**要在程序層清，不是逐一傳 `env=`**——受測程式碼自己也會 shell out（`foundry_lint.git_run`），逐一傳只擋得住測試自己下的那幾道指令。日後新增「造臨時 repo」的測試，照抄這段。
- `X8` **併行的 run 會改到共用 repo 的 `.git/config`，把整個工作區弄壞。** 2026-09-04 深夜實際發生：另一個 run（MYL-44 的 hook 驗證）在共用 repo 上設了 `core.bare = true`＋`user.name = 測試`／`user.email = test@example.com`，於是本 run 的 `git status`／`git add` 全部回 `fatal: 該動作必須在一個工作區中執行`——而 `git symbolic-ref` 之類不需要工作區的指令照常成功，看起來像 repo 還好好的。
  → **不要去改回別人的設定**（他們可能正靠那個設定跑），也不要卡住等。兩條路：
    1. 唯讀查看用 `git --git-dir=.git --work-tree=. <指令>`，這條不改任何東西就能繞過 `core.bare`。
    2. 要 commit 就**開自己的 linked worktree**：`git --git-dir=<repo>/.git worktree add "$PAPERCLIP_RUN_SCRATCH_DIR/wt-<單號>" <分支>`，把工作區檔案複製過去，在那裡跑 `make check` 與 commit。分支與 ref 是共用的，commit 一樣進得了本 repo。
  → commit 時**顯式帶身分**（`git -c user.name=… -c user.email=… commit`），否則會用到別人留在 repo config 裡的測試身分。這一條與 `X1` 是同一類問題的兩種形態：`X1` 是 HEAD 被換掉，`X8` 是 config 被換掉。
- `X9` **`mirror-recon` 的紅燈是延遲偵測，於是同一片紅燈會被併行的 run 各自看到，「順手補」就補成一對多。** 2026-09-06 完整走過一遍：同一次作業連續建了八張來源單、只鏡像六張（時機 1 是 `【自律】`，漏了當下沒有任何東西擋你），紅燈要等**下一個人 commit** 才浮出來——而那時已經有好幾個 run 醒著。MYL-104 因此在 **27 秒內被兩個不同的 run 各建了一張鏡像**（`#37` Developer 05:04:40、`#38` QA 05:05:07）。**公開 issue 送出去就收不回來**，這條紅燈的處置成本是不對稱的。
  → **紅燈訊息會過期，而且兩個方向都會過期。** 同一串留言裡出現過兩則**互相矛盾**的通報，兩則都是過期讀取、兩則照著動手都會出錯：05:08 的報告寫「MYL-104／MYL-105 漏建」（那一輪的 `gh issue list` 落在 05:04:30，三張鏡像都還沒建出來）——照它動手會建出第三、第四張重複鏡像；05:10 的跨單通報寫「一對多紅燈：`#37`／`#38`」（`#38` 已於 05:07:03 脫鉤）——照它動手會去關一張早就關掉的 issue。⇒ **動手前一律重查，不要拿手上那份輸出當現況**；而重查**只能走 REST**（`gh api repos/{o}/{r}/issues`），因為 `gh issue list` 走 GraphQL，正好在同一種故障下讀不到東西。
  → **處置規則已成文**：`skills/foundry-platform/adapters/github.md` 的「一次建多張（批次建單）」與「看到紅燈時誰動手（認領規則）」兩節。四個要點——**一張一鏡像**（建單迴圈裡不得有「稍後統一鏡像」階段）、**批次收尾前自查**（不要把偵測留給下一個 commit 的人）、**只補自己建的那張**（別人的單只回報，除非工單明文授權代建）、**動手前重查**。
  → **收斂重複鏡像的手法（可逆，優先於刪除）**：移除多餘那張的 `Foundry-Source:` 首行 ＋ `close not planned` ＋ 回來源工單補一則更正登記留言。移除首行之後對帳就看不到它了，不必刪 issue。`#38` 即以此收斂（05:07:03），事後查證：body 首行已非標記、`state_reason: not_planned`、`mirror-recon` 不再報一對多。
  → 與 `X1`／`X8` 同族但機制不同：那兩條是併行 run 搶**同一份本機狀態**，本條是併行 run 對**同一片外部紅燈**各自反應。防法也不同——前者靠隔離工作區，後者靠認領規則。（MYL-108）

### 兩份 nav 的結構性漂移 — **已收斂（2026-09-05，MYL-55）**

**歷史**：`mkdocs.yml`（私有站）與 `scripts/publish-handbook.sh` 內嵌的 heredoc `mkdocs.yml`
（公開鏡像）曾是**兩份各自維護的 nav**。新增手冊章節時只改一份，公開站就會漏章——MYL-31 踩過這一類。
當時以 `foundry-lint --selfcheck` 機械比對三者（磁碟章節數／私有 nav／腳本內嵌 nav）擋住，
並記下「根治要讓腳本轉寫私有 `mkdocs.yml` 而非另寫一份」。

**收斂經過**：MYL-52 讓 wiki 側欄（`_Sidebar.md`）由 `tools/publish-docs/project_docs.py`
轉寫私有 nav 產生（第三個閱讀面沒有再加一份手寫 nav）；MYL-55 把精裝站搬回本 repo，
`publish-handbook.sh` 連同它的 heredoc 一起刪除，站台的 `mkdocs.yml` 改由
`tools/publish-docs/site_docs.py` 轉寫。**現況是一份手寫 ＋ 兩份轉寫。**

**條目保留的理由不是懷舊，是那道機械閘門換了形狀**：`check_nav_sync` 不再比對「兩份要一致」
（沒有第二份可比了），改成守 **「不准再出現第二份」**——掃 `scripts/` 與 `.github/workflows/`，
同時出現 `nav:` 與手冊章節檔名就擋下。理由是漂移是從「有人另寫一份」開始的，
不是從「兩份對不上」開始的；只比對一致性的話，這項檢查會隨第二份消失而退化成恆真。
⇒ **要投影出新的閱讀面時，nav 一律轉寫 `mkdocs.yml`**，不要手寫。

---

## 維護規則

- 本檔屬 `W1` 永久文件，改動走一般 commit；**不需要**發佈到公開手冊站（內容含內部 API 與平台細節）。
- 新增條目時給穩定編號（`L*`／`S*`／`R*`／`GAP-*`／`X*`），**只增不改、不回收**（同 protocol 第 11 節規則）。
- 條目失效時（例如平台放開了某個權限）**保留條目並註明失效日期與證據**，不要直接刪——刪掉之後，下一個人會重新踩一次來確認它真的失效了。
