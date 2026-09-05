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

## 2. API 形狀陷阱：會回 4xx 但錯誤訊息不會告訴你原因

| # | 陷阱 | 正確寫法 |
| --- | --- | --- |
| S1 | 互動卡內容放頂層 `body` → 422 | 必須包在 `payload` 物件：`{kind, idempotencyKey, continuationPolicy, title, payload: {version: 1, ...}}`。`ask_user_questions` 的問題欄位叫 **`prompt`**（不是 `question`），`version` 與 `selectionMode` 都必填 |
| S2 | `PUT /api/issues/{id}/documents/{key}` 放 `content` → 400；沒帶 `baseRevisionId` → 409 | 必填 `format: "markdown"`＋`body`＋`baseRevisionId`（現行 revision id） |
| S3 | `POST /api/issues` 開單 → 404 | 開單走 `POST /api/companies/{companyId}/issues`。該 endpoint 在 `openapi.json` 的 requestBody schema 是**空的**，欄位名以 GET 單一 issue 的回傳形狀為準 |
| S4 | 開單時直接設 `status: in_progress` → 被別的 heartbeat 搶走 checkout，隨後自己發卡回 409 `Issue run ownership conflict` | 先建成 `todo`／`backlog`，**發完卡再轉狀態** |
| S5 | `PATCH /api/issues/{id}` 的 `unblockDescriptor.owner` 填別的 agentId → 整個 PATCH 靜默不生效（`status`、`blockedByIssueIds` 一併沒寫入） | `owner` 只能填自己。要別的 agent 解鎖就用一級 blocker 掛該 agent 的工單。⚠️ **2026-09-05（MYL-52）補測：填自己的 agentId（且自己就是 `assigneeAgentId`）也一樣整包靜默不生效**——`{"unblockDescriptor":{"owner":"<自己>","action":"…"}}` 送出去回 200、欄位全 null、`status` 沒變；把 `unblockDescriptor` 拿掉只送 `{"status":"blocked"}` 就成功。`openapi.json` 對這個欄位**沒有任何 schema**（同 `S3` 的空 requestBody），所以正確形狀無從查證。⇒ **要轉 `blocked` 就只送 `status`，解除路徑寫在工單留言**，不要為了填這個欄位反覆試——試錯會讓 `status` 一起寫不進去，看起來像「狀態改不動」 |
| S6 | agent 把工單 PATCH 成 `in_review` → `invalid_issue_disposition` | 需先存在真實審查路徑（pending 的互動卡）。順序：**先發卡、再改狀態** |
| S7 | 想把自己開的子單推進 `in_progress` → `in_progress issues require an assignee`；補上 `assigneeAgentId` 之後**再也 PATCH 不動那張單**，回 409 `Issue run ownership conflict` | **指派＝喚醒**，即使指派給「正在跑的自己」也一樣：Paperclip 會為那張子單另開一個併行 run，該 run 一 checkout 就成為單的擁有者，父 run 從此不能改它的狀態、也不能 `release`。而 `POST /api/heartbeat-runs/{id}/cancel` 是 **board-only（403）**，父 run 收不回來。⇒ 子單只要會被推進 `in_progress`，就**當成會生出一個併行 run 來設計**：先把它的描述與留言寫到足以讓那個 run 獨立完成，並明確寫出它**不該**碰什麼（尤其 git——共用 workspace 見 §5 `X1`）。不需要它跑起來就別指派，把單留在 `todo`。（2026-09-05 MYL-54 實測） |

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

## 4. 已知缺口：使用者知情下保留，不要當成待辦自行修掉

| # | 缺口 | 出處與裁定 |
| --- | --- | --- |
| ~~GAP-1~~ | ~~**額度用盡沒有成文處置。**~~ **已關閉（2026-09-03，MYL-36）**：使用者在 `ask:MYL-36:platform-routing:v1` 要求「額度耗盡……可以透過這個 workflow 自動指派」，已成文為 protocol 第 8 節 `M5` ＋ `foundry-model-routing` §5。條目保留供追溯：MYL-33 當時的 `no_clause` 裁定已被本次裁定取代 | MYL-33 v3 卡 `no_clause` → MYL-36 卡取代 |
| GAP-2 | **高層無梯可升。** `M1` 寫 `low→medium→high`，但高層預設已站在 `max`；高層 agent 連續失敗兩次時 `M1` 無法適用，需臨場改走 `M3` 轉 `blocked` | MYL-33 v3 卡裁定 `ladder_no_change` |
| GAP-3 | **`.foundry/config.yml` 的 `push` 段表達不了本 repo 現況。** MYL-23 P1「合併回 main 後 push origin 由執行者自行」寫不進 schema，權威來源是 protocol 第 7、9 節的分級表文字 | MYL-35 G7 選項 A，見 R4 |
| GAP-4 | **`claude_local` adapter 內建說明字串的 `effort` 只寫到 `(low\|medium\|high)`，已過時。** 實際支援 `low/medium/high/xhigh/max`；adapter 對 `effort` 原樣傳給 CLI 不做驗證 | 實測 `claude-opus-5`＋`max` EXIT=0。protocol 第 8 節附註已載明 |
| GAP-5 | **瀏覽器工具綁的是「情境」不是「人」。** `.mcp.json` 放在共用 repo 裡，該 repo 的**所有** agent 都拿得到瀏覽器工具，不只 Frontend Verifier。要真正做到 per-agent 綁定得靠平台 tool-profile（`L7`，board-only） | MYL-37 卡 `myl37:frontend-verifier:plan:f7cf0b84` 的 `gateway: gateway_now`——使用者選擇由自己在 UI 補上閘道，能力層不等它。**2026-09-04 更正：這條缺口用閘道關不掉**——stdio 型 MCP 送不進 agent session（`L10`），硬掛遠端連線反而會把 `.mcp.json` 整份廢掉（`L9`）。維持 `.mcp.json`、以「不把遠端 app 授權給 Frontend Verifier」為代償規則 |

## 5. 併發與競態：多個 run 共用同一個 workspace

本 repo 的 workspace 是**共用**的，heartbeat run 可能併行；`X3` 起也一併收**「工具跑出來的結果跟來源字面不一樣」**這一類踩點——`X3`／`X4` 是 mkdocs 的渲染，`X5`／`X6` 是 CI 的 checkout 形狀與 git hook 的環境變數。共通的形狀是：**來源沒錯，錯的是它被放進了哪個環境**，所以錯誤訊息往往指向錯的地方。以下每一條都真的發生過。

- `X1` **commit 落到別人的分支。** 兩個 run 併行時 checkout 會互相干擾（MYL-23 的 commit 曾落到 MYL-27 的分支）。
  → **commit 前先驗 `git symbolic-ref --short HEAD`**，不要假設分支還是你切的那條。
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

- `X5` **git 呼叫 hook 時會設 `GIT_DIR`，而它勝過 `git -C <路徑>`。** 於是「在臨時目錄造一個 repo 來測」這種測試，在 pre-commit 底下跑會被拉回**外層 repo**：臨時 repo 根本沒建起來，接著的 commit 觸發外層 hook、在臨時目錄找不到 `.pre-commit-config.yaml` 而整組紅。
  症狀極難認：**單獨跑 `make test` 全過，`git commit` 觸發同一組測試時全敗**，而且 `foundry-tests` 這個 hook 只在 staged 檔案含 `tools/` 時才觸發，所以它平常隱形，只在動到 `tools/` 的那次 commit 現形（MYL-52 撞上，當時 22 項全紅）。
  → 已修：`test_foundry_lint.py` 與 `tools/publish-docs/test_publish_gate.py` 在**模組載入時**就把 `os.environ` 裡的 `GIT_*` 清光，並各留一項回歸守衛。**要在程序層清，不是逐一傳 `env=`**——受測程式碼自己也會 shell out（`foundry_lint.git_run`），逐一傳只擋得住測試自己下的那幾道指令。日後新增「造臨時 repo」的測試，照抄這段。
- `X6` **併行的 run 會改到共用 repo 的 `.git/config`，把整個工作區弄壞。** 2026-09-04 深夜實際發生：另一個 run（MYL-44 的 hook 驗證）在共用 repo 上設了 `core.bare = true`＋`user.name = 測試`／`user.email = test@example.com`，於是本 run 的 `git status`／`git add` 全部回 `fatal: 該動作必須在一個工作區中執行`——而 `git symbolic-ref` 之類不需要工作區的指令照常成功，看起來像 repo 還好好的。
  → **不要去改回別人的設定**（他們可能正靠那個設定跑），也不要卡住等。兩條路：
    1. 唯讀查看用 `git --git-dir=.git --work-tree=. <指令>`，這條不改任何東西就能繞過 `core.bare`。
    2. 要 commit 就**開自己的 linked worktree**：`git --git-dir=<repo>/.git worktree add "$PAPERCLIP_RUN_SCRATCH_DIR/wt-<單號>" <分支>`，把工作區檔案複製過去，在那裡跑 `make check` 與 commit。分支與 ref 是共用的，commit 一樣進得了本 repo。
  → commit 時**顯式帶身分**（`git -c user.name=… -c user.email=… commit`），否則會用到別人留在 repo config 裡的測試身分。這一條與 `X1` 是同一類問題的兩種形態：`X1` 是 HEAD 被換掉，`X6` 是 config 被換掉。

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
