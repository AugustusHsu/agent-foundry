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
