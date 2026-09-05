# adapter：github

`platform: github` 時的動詞對照。介面語意見 `../SKILL.md`，本文只翻譯成具體指令。

## 前置條件

- `gh` CLI 已安裝且 `gh auth status` 通過（scopes 需含 `repo`、`project`）。
- 在目標 repo 的工作目錄內執行（`gh` 自動解析 `owner/repo`）。
- `jq` 可用（`list_issues` 與 ID 查詢會用到）。
- 佔位符慣例：`<N>`＝issue 編號、`<PROJECT>`＝project 編號、`<OWNER>`＝project 擁有者（個人用 `@me`）。project 編號的查法見附錄 A。

## 動詞對照

### init_structure

1. 建標準 label（`--force` 使其冪等——已存在則更新而非報錯）：

   ```sh
   for l in "type:brd" "type:prd" "type:hld" "type:lld" "type:impl" "type:review" "type:test" "type:docs"; do
     gh label create "$l" --color 5319E7 --description "Foundry 工單類型" --force; done
   for l in "role:product-analyst" "role:scrum-master" "role:tech-lead" "role:developer" "role:code-reviewer" "role:qa"; do
     gh label create "$l" --color 0E8A16 --description "Foundry 角色" --force; done
   for l in "size:small" "size:medium" "size:large"; do
     gh label create "$l" --color FBCA04 --description "Foundry 工單規模" --force; done
   ```

2. 建 milestone（重跑前先用 `gh api repos/{owner}/{repo}/milestones --jq '.[].title'` 查重，已存在則跳過）：

   ```sh
   gh api repos/{owner}/{repo}/milestones -f title="<里程碑名>" -f description="<說明>" -f due_on="2026-12-31T23:59:59Z"
   ```

3. 建 project（先 `gh project list --owner <OWNER>` 查重，已有同名則跳過）：

   ```sh
   gh project create --owner <OWNER> --title "Foundry"
   ```

4. 補齊 Status 欄位選項。新 project 預設只有 `Todo`／`In Progress`／`Done`，需補 `In Review`、`Blocked`、`Cancelled` 三個選項——GitHub 網頁：Project → Settings → Status 欄位 → 新增選項。（GraphQL 的 `updateProjectV2SingleSelectField` 也可做到，但選項全量覆蓋易出錯，建議走網頁。）
5. 建三個 view。**GitHub API 目前不支援建立 ProjectV2 view，此步驟人工在網頁完成**（各一分鐘）：
   - `Board`：Layout 選 Board，Column by 選 Status。
   - `Table`：Layout 選 Table，顯示 Title／Status／Labels／Milestone／Assignees 欄。
   - `Roadmap`：Layout 選 Roadmap，Date/iteration 依 milestone due date。
6. 裝 CI 閘門（MYL-36 增訂）：把 `.github/workflows/foundry-lint.yml` 放進 `<TARGET>`（由 `foundry-init` 步驟 2.5 複製）。

   ```sh
   # 首次 push 後確認 workflow 有被 GitHub 認得
   gh workflow list --all | grep foundry-lint
   ```

   **這是 github 模式相對其他平台的實質優勢**：Foundry 的關卡在多數平台上靠 agent 自覺遵守，
   在 GitHub 上規範可以有**機械執行力**——PR 沒過就是沒過。跑的內容與本機 `make check` 相同，
   所以 CI 紅燈一定能在本機重現。
   要讓它真的擋得住合併，還需在網頁把 `foundry-lint / check` 設為 **required status check**
   （Settings → Branches → branch protection rule）——這是**改動 repo 保護設定**，
   屬使用者權限範圍，agent 不得代設；列入 init 報告待辦請使用者處理。
- **查證**：`gh label list | grep -c '^type:'` 得 8；三個 view 在網頁可開；重跑步驟 1–3 無報錯、無重複；
  `gh workflow list --all` 列得到 `foundry-lint`。

### create_issue

```sh
gh issue create --title "<標題>" --body-file <body.md> \
  --label "<type_label>" [--label "<其他label>"] \
  [--milestone "<里程碑名>"] [--assignee "<帳號>"]
```

開單後掛進 project 並設 Status＝`Todo`（欄位操作見附錄 B）：

```sh
gh project item-add <PROJECT> --owner <OWNER> --url <上一步輸出的 issue URL>
```

- **查證**：`gh issue view <N>` 欄位正確。

### update_status

Status 以 project 的 Status 欄位為準（附錄 B 查 ID 後執行）：

```sh
gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> \
  --field-id <STATUS_FIELD_ID> --single-select-option-id <OPTION_ID>
```

六態 → Status 選項名對照：`todo`→`Todo`、`in_progress`→`In Progress`、`in_review`→`In Review`、`blocked`→`Blocked`、`done`→`Done`、`cancelled`→`Cancelled`。

同步 issue 開關狀態：

```sh
gh issue close <N> --reason completed        # 進 done 時
gh issue close <N> --reason "not planned"    # 進 cancelled 時
gh issue reopen <N>                          # 自 done/cancelled 離開時
```

- **查證**：`gh project item-list <PROJECT> --owner <OWNER> --format json | jq '.items[] | select(.content.number==<N>) | .status'`。

### comment

```sh
gh issue comment <N> --body-file <comment.md>
```

- **查證**：`gh issue view <N> --comments` 末筆為剛發的留言。

### set_labels

```sh
gh issue edit <N> --add-label "<label1>,<label2>" --remove-label "<label3>"
```

（只影響列出的 label，符合介面「不得整批覆蓋」要求。）

- **查證**：`gh issue view <N> --json labels --jq '.labels[].name'`。

### set_milestone

```sh
gh issue edit <N> --milestone "<里程碑名>"   # 設定
gh issue edit <N> --remove-milestone         # 移除（milestone=none）
```

指定名稱不存在時 gh 會報錯——符合介面「不自動建立」要求，直接回報。

- **查證**：`gh issue view <N> --json milestone --jq '.milestone.title'`。

### list_issues

label／milestone／assignee 過濾用 issue list；`--state all` 讓 done/cancelled 也可查：

```sh
gh issue list --state all [--label "<label>"] [--milestone "<里程碑名>"] \
  [--assignee "<帳號>"] --json number,title,labels,milestone,assignees --limit 200
```

status 過濾走 project item-list（Status 欄位不在 issue API 裡）：

```sh
gh project item-list <PROJECT> --owner <OWNER> --format json --limit 200 \
  | jq '[.items[] | select(.status=="<Status選項名>") | {number: .content.number, title: .title, status}]'
```

兩種條件都要時，先跑後者再以 `jq` 交集 number 清單。

### link_issues

- `parent`（把 `<N>` 掛為 `<P>` 的子單）——用 GitHub sub-issue API（node ID 查法見附錄 C）：

  ```sh
  gh api graphql -H "GraphQL-Features: sub_issues" -f query='
    mutation($parent: ID!, $child: ID!) {
      addSubIssue(input: {issueId: $parent, subIssueId: $child}) {
        issue { number } } }' -f parent=<P的nodeID> -f child=<N的nodeID>
  ```

  重複掛同一子單 API 回錯誤訊息但不改資料，視為冪等成功。若該 repo 尚未開放 sub-issues，退而求其次：在父單 body 的任務清單加一行 `- [ ] #<N>`（`gh issue edit <P> --body-file` 全文改寫）。

- `blocked_by`（標記 `<N>` 被 `<B>` 阻塞）——GitHub 無跨版本穩定的 CLI 支援，採機器可解析的固定慣例，兩步皆必做：
  1. `gh issue edit <N> --add-label "blocked"`（`init_structure` 之外唯一允許臨時建立的 label，首次用 `gh label create blocked --color B60205 --force` 補建）。
  2. 在 `<N>` 留言一行、格式固定：`Blocked-by: #<B>`（一個 blocker 一行；解除時再留言 `Unblocked-by: #<B>`）。

- **查證**：parent → `gh issue view <P>` 網頁版 sub-issues 區塊（或 GraphQL 查 `subIssues`）；blocked_by → `gh issue view <N> --comments | grep 'Blocked-by:'`。

## 鏡像模式（`mirror_platform: github`）

（MYL-39 計畫 v5 §3 定案；欄位規格見 `../config-schema.md` 的 `mirror_platform` 段。）

`platform: github` 時，上面的動詞對照就是全部——真相在這裡。**鏡像模式是另一回事**：真相在別的平台
（本 repo 是 Paperclip），GitHub 只承載**可見面**。差別具體在三點：

- **鏡像 issue 唯讀。** 在這裡留言、改 Status、close，都不會回到來源端，而且會在下一次同步被覆蓋。
- **鏡像端不承載指派。** GitHub 的 assignee 喚不動任何 agent，設了只會讓人以為在這裡能派工。
- **同步是【自律】的。** 沒有任何東西會在你漏同步的當下擋住你；兜底的是下面的對帳，而對帳只在
  `make check`／CI 跑——也就是**下一次有人 commit** 才會發現。知道這件事之後再決定要不要偷懶。

**授權定位**：鏡像是對外動作（`H4`／`G-C`）。使用者已核可**管道本身**（MYL-39 計畫 v5，含「issue 公開、
標題與內文都對外可見」這項知情事項），因此每張單的鏡像**不逐張發卡**；逐張還要判斷的只剩「這張單的內容
適不適合公開」，見時機 1。**這個授權綁本 repo 的那一次核可，不隨 `foundry-init`／`foundry-adopt` 傳染**——
別的專案要開鏡像，由該專案的使用者自己核可一次。

### 對應標記（唯一權威）

鏡像 issue 的 body **第一行**固定為（其後空一行才是正文）：

```
Foundry-Source: paperclip/MYL-123
```

格式 `Foundry-Source: <來源平台>/<issue_ref>`，解析用 `^Foundry-Source: ([a-z-]+)/(\S+)$`。

- **放 body 首行、不放 label**：label 值域是 `init_structure` 建的固定集合，一單一值的動態 label 會把
  label 空間撐爆；body 首行則 `gh issue list --json body` 一次撈得回來，**不依賴 GitHub 的搜尋索引**
  （`--search` 有建索引延遲，剛建的單查不到，對帳會誤報漏建）。
- 建單後在**來源工單**留一行 `Mirrored-to: github#<N>`（用抽象動詞 `comment`）。這只是反查快取；
  **兩邊衝突時以 body 首行標記為準**，否則對應關係本身就有兩份真相。
- 經網頁編輯過的 body 行尾可能是 CRLF，解析首行前先剝掉尾端 `\r`。

### 時機 1：建單

在來源端 `create_issue` **成功之後**（順序不能反：單號的發源地是來源端）：

1. 組 body：首行標記 → 空行 → 來源描述全文 → 末行附一句唯讀聲明
   （`> 真相與指派在 <來源平台>；本 issue 是唯讀鏡像，在此留言不會觸發任何 agent。`）。
2. 建單，label 用 `init_structure` 建的同一套，不另建：

   ```sh
   gh issue create --title "<來源標題>" --body-file <mirror-body.md> \
     --label "<type_label>" [--label "role:<角色>"] [--label "size:<規模>"]
   ```

3. `gh project item-add <PROJECT> --owner <OWNER> --url <上一步輸出的 issue URL>`，Status 設 `Todo`（附錄 B）。
4. **不設 assignee**；負責角色以 `role:*` label 表達。
5. 回來源工單留言 `Mirrored-to: github#<N>`。

**不鏡像的情況**：工單內容不宜公開時（鏡像 repo 是 public，標題與內文全部對外可見）**不要建**，改在
來源工單留一行 `Mirror-skipped: <理由>`——對帳看到這行就不算漏建。拿不準算不算「不宜公開」時不要鏡像：
沒鏡像可以事後補，送出去的收不回來。

- **查證**：`gh issue view <N> --json body --jq '.body' | head -1` 等於標記行；
  `gh issue view <N> --json assignees --jq '.assignees'` 為空陣列。

### 時機 2：改狀態

來源端狀態變更成功之後，對鏡像 issue 跑本文 `update_status` **全套**（project 的 Status 欄位 ＋ issue 開關），
六態對照沿用同一張表，不另立一套。

- **查證**：同 `update_status`。

### 時機 3：結案

進 `done`／`cancelled` 時，除了 `update_status` 的 close 之外，**追加一則結案留言**：一行結論
（審查 verdict、撤回理由或取代它的單號）＋來源工單的最終狀態。理由是可見面的價值在於外部看得到**結果**——
只有一個 closed 狀態，讀者分不出這單是做完了、不做了、還是被別的單取代了。

來源端日後離開 `done`／`cancelled` 時照時機 2 走（`gh issue reopen` ＋ Status 改回）。

- **查證**：`gh issue view <N> --json state,stateReason,comments`。

### 對帳

**實作**：`foundry-lint --selfcheck` 的 `mirror-recon` 一項（MYL-54），跑在 `make check`／pre-commit／CI。
`mirror_platform` 整段缺席時本項無事可做、直接通過。

**分工與它的實際能力**——下面兩條是規則文字，不是註解：

- **同步本身 `【自律】`**：建單、改狀態、結案時 agent 自己要做。沒有任何東西會在你漏做的當下擋住你。
- **對帳 `【機械】`**：兜底，但**是延遲偵測、不是即時防護**。它只在有人跑 `make check`／commit 時才動，
  而工單狀態改變不一定伴隨 commit——漏同步會等到**下一次有人 commit** 才被抓到。
  更要緊的是：**在 CI 上它一定是跳過的**，因為 CI 沒有來源端憑證。真正跑得到完整對帳的，
  只有同時握有 `gh` 登入與 `PAPERCLIP_API_KEY` 的本機 `make check`。

**跳過不等於通過**：拿不到任一端（`gh` 沒登入、缺 `PAPERCLIP_API_KEY`、設了 `FOUNDRY_LINT_OFFLINE`）時，
本項印 `⏭` 並在總結行報「N 項跳過未檢查」，**不印 `✅`**。看到 `⏭` 就是「這次沒對過帳」，
不是「對過了沒問題」。跳過刻意不擋 commit——CI 拿不到憑證是常態，讓它紅只會訓練所有人忽略紅字，
真的漂移時也一起忽略掉。

**範圍**：只對帳 `platform_options.github.mirror_since` 起算的單（含本身）。舊單回填屬批次對外動作、
要另外核可，不歸對帳管；界線的語意見 `../config-schema.md`。

比對三個欄位，任一不合即紅燈：

| 欄位 | 來源端 | 鏡像端 | 判定 |
| --- | --- | --- | --- |
| 單號對應 | `issue_ref` | body 首行標記 | 每張來源工單恰好對到一個鏡像 issue |
| 狀態 | 六態 | project 的 Status 選項名 | 依 `update_status` 的六態對照表換算後相同 |
| 開關狀態 | `done`／`cancelled` 為關，其餘為開 | issue 的 `state` | 兩邊一致 |

一次撈完鏡像端（直接解析首行，不用 `--search`）：

```sh
gh issue list --state all --limit 500 --json number,state,body \
  | jq -r '.[] | (((.body // "") | split("\n") | .[0] // "") | sub("\r$";"")) as $h
           | select($h | startswith("Foundry-Source: "))
           | [($h | ltrimstr("Foundry-Source: ")), .number, .state] | @tsv'
```

（`// ""` 兩層都要：空 body 的 issue 在 API 回的是 `null`，而 `"" | split("\n")` 回的是空陣列——
少一層，整個對帳會被一張沒有內文的 issue 中斷，而錯誤訊息不會告訴你是哪一張。）

三種紅燈，**都只回報、不自動修**：

- **漏建**：來源端有、鏡像端找不到對應標記，且來源端沒有 `Mirror-skipped:` 留言。
- **孤兒**：鏡像端的標記指到來源端不存在的單。**沒有標記的 issue 不算孤兒**——那是人手開的，不歸鏡像管，
  別把它當殘骸清掉。
- **一對多**：同一個 `issue_ref` 對到兩個以上 issue。修法是關掉多餘的那個，而關／刪對外資源屬 `G-C`，
  要使用者核可；對帳自己不動手。

`--limit` 要蓋得住鏡像端的實際單數，超過時分頁撈完，**不得靜默截斷**——截斷過的對帳會把漏建報成「全過」，
比不對帳更危險。`mirror-recon` 的做法是撈到剛好等於上限就直接報紅，而不是自己猜還有沒有下一頁。
**兩份清單都要看**：`gh issue list` 決定有哪些鏡像單，`gh project item-list` 決定它們的 Status；
只看前者的話，後者被截斷時查不到的 Status 會變成空字串，於是每一張都報成「狀態不同步」——
方向是安全的（紅燈不是綠燈），但理由是錯的，讀者會去追一個不存在的漂移。

⚠️ **`gh project item-list` 不給 `--limit` 時預設只回 30 筆**，而且不會有任何截斷提示。
人手查證單一 issue 的 Status 時很容易踩到：看板上排在 30 名之後的項目查起來就像「沒掛進去」。
（2026-09-05 實測，當時看板有 39 張手抄 draft card 排在前面。）

**來源端狀態不在六態表上時報紅，不要自己補對照。** 已知案例：Paperclip 除了六態還有 `backlog`
（2026-09-04 實測，當時 56 張單裡有 1 張）。「`backlog` 大概等於 `Todo`」聽起來很合理，但那個對照
沒有人核可過，而一旦寫進程式就再也不會有人回頭問它對不對。要補表就改本節的六態對照並經核可；
在那之前，撞到就是紅燈，由人決定。

### 這一節刻意不做的事

| 不做 | 為什麼 |
| --- | --- |
| 對帳標題與內文 | 對帳要抓的是「漏同步」，單號／狀態／開關三者已足以判定。全文比對的成本與價值不成比例，真的踩到再開單。 |
| 鏡像來源端的每一則留言 | 那會讓 GitHub 變成第二個討論場，也就是第二份真相。只有結案摘要例外——那是結果，不是過程。 |
| 接受鏡像端的任何寫入 | 見本節開頭：唯讀。要改回來源端改。 |
| 鏡像父子／`blocked_by` 關係 | 掛關係要求兩邊都已存在鏡像，牽涉建單順序與重試語意，本規格不定；先讓三個時機穩定。 |

## publish_docs（文檔投影目標面）

本檔除了是執行層 adapter，也承載 `publish_docs`（SKILL.md §3.9）的兩個目標面。
**這一節與上面的執行層動詞互相獨立**：`docs` 段選這裡，`platform` 選上面，
一個專案可以只用其中一邊（MYL-52 裁定，理由見 SKILL.md §5）。
本節在「宿主平台是 github」時適用——宿主的判定同 `../config-schema.md` 的 `docs` 合法性規則：
`mirror_platform` 有值取它、否則取 `platform`。本 repo 屬後者之外的情況（`platform: paperclip`
而文檔面在 github），所以要靠 `mirror_platform: github` 或在工單裡明講，別靠讀者猜。

| 設定 | 指令 | 定位 | 觸發時機 |
| --- | --- | --- | --- |
| `docs.primary: wiki` | `bash scripts/publish-wiki.sh` | **主閱讀面**：合併 main 即同步 | `merge` |
| `docs.mirror_site` | `bash scripts/publish-handbook.sh` | 精裝面：公開鏡像 repo ＋ Pages | `manual`（`tag` 觸發屬 MYL-39 N5，尚未做） |

兩者共用同一道前置閘門 `scripts/lib/publish-gate.sh`（MYL-24 審查證據 ＋ MYL-44 戳記旁路）。
閘門可單獨執行以排查：`bash scripts/lib/publish-gate.sh <repo 根>`——只判斷，不 clone 不 push。

### `primary: wiki` 的轉換規則

wiki 是**另一個 git repo**（`<repo>.wiki.git`），頁面是平的、沒有目錄層級。
轉換由 `tools/publish-docs/project_docs.py` 執行，四條規則全部是載體差異逼出來的：

| # | 規則 | 為什麼 |
| --- | --- | --- |
| 1 | `index.md` → `Home.md`，其餘章節同名平移 | wiki 的首頁頁名固定是 `Home` |
| 2 | 章間連結去掉 `.md`（`04-x.md` → `04-x`） | wiki 頁面 URL 是 `.../wiki/<頁名>`，沒有副檔名。去掉之後是**單純的相對 URL 解析**，不倚賴 wiki 專屬的連結改寫魔法——這點重要，因為本機驗不了 wiki 渲染（`X4`） |
| 3 | 錨點由 mkdocs slug 換算成 GitHub slug | Python-Markdown 預設 slugify 丟掉非 ASCII（`## 3. HITL 發卡` → `#3-hitl`），GitHub 保留 CJK（`#3-hitl-發卡`）。**照抄過去必然全斷** |
| 4 | 指向 repo 內部路徑（`skills/`、`templates/`、`docs/pilot/`）的相對連結依 `docs.link_policy` 改寫 | 相對路徑在 wiki 一定失效。`absolute`＝改寫成 `https://github.com/<repo>/blob/main/<路徑>`；`plain`＝比照公開鏡像拆成純文字 |

側欄 `_Sidebar.md` **由私有 `mkdocs.yml` 的 nav 轉寫**，不另手寫一份——
手寫就會變成 known-drift 記的「兩份 nav」再加一份。頁尾 `_Footer.md` 放「請勿直接編輯」與來源 commit。

### `primary: wiki` 的防手改偵測

投影 commit 的訊息帶兩行 trailer：

```
Foundry-Projection: <來源手冊 commit sha>
Foundry-Projection-Digest: <投影內容的 sha256>
```

同步前的判定，兩層都要過：

1. wiki 的 HEAD 訊息**必須帶 trailer**。UI 上的編輯留下的是 GitHub 自己的訊息（`Updated Home (markdown)`），trailer 當場消失。
2. wiki 現況重算出來的摘要**必須等於** trailer 記的那個。光抄 trailer 沒有用——內容對不上一樣擋下。

任一層不過就**拒絕覆蓋並報錯**，印出三條處置（搬回源頭／在 wiki 還原／`--bootstrap` 顯式放棄）。
`--bootstrap` 是唯一的旁路，且必須由人在指令列打出來：放棄別人的編輯是人的決定，不是腳本的預設行為。

### 查證（動詞的成功判準）

`scripts/publish-wiki.sh` 推送前會跑 `tools/publish-docs/compare_projection.py`，逐章比對
標題文字／章節數／內部連結目標／MYL-44 戳記行，輸出對照表；**任一格紅就 exit 1、不推送**。
把該表貼進工單即為證據。腳本自己回報成功不算查證（`X2` 踩過：發佈互蓋時腳本也說成功）。

⚠️ 對照表證得了「投影自我一致」，**證不了** GitHub 實際算出來的錨點字串等於我們算的那個。
那件事本機沒有渲染器可驗（`X4`），只能在 wiki 實站點一遍。表格因此把錨點另列一欄標「待實站驗」。

### 開通目標面不在本節授權內

啟用 wiki（`has_wiki: true`）、新建公開鏡像 repo、開 Pages——都是**新開對外資源**，
屬關卡 C（`gates.external_actions: user`，不可調降），發卡請使用者執行。
本節的兩支腳本只負責**已開通管道**的例行同步（P2）。

## 附錄 A：查 project 編號

```sh
gh project list --owner <OWNER> --format json | jq '.projects[] | select(.title=="Foundry") | .number'
```

## 附錄 B：Status 欄位操作所需的三個 ID

```sh
gh project view <PROJECT> --owner <OWNER> --format json | jq .id            # PROJECT_ID
gh project field-list <PROJECT> --owner <OWNER> --format json \
  | jq '.fields[] | select(.name=="Status") | {id, options}'                # STATUS_FIELD_ID 與各 OPTION_ID
gh project item-list <PROJECT> --owner <OWNER> --format json \
  | jq '.items[] | select(.content.number==<N>) | .id'                      # ITEM_ID
```

ID 在 project 存續期間不變，可在首次查得後記錄於工單留言或腳本變數重複使用。

## 附錄 C：查 issue node ID（sub-issue 用）

```sh
gh issue view <N> --json id --jq .id
```
