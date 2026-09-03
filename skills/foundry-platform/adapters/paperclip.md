# adapter：paperclip

`platform: paperclip` 時的動詞對照。介面語意見 `../SKILL.md`，本文只翻譯成具體指令。

Paperclip 是**執行層平台**（工單／狀態／看板），不是 git 平台——程式碼與規則層 .md 仍在各自的 git repo，本 adapter 只負責執行層。與 `github`／`local-md` 的差異全部吸收在本文，流程規範（foundry-protocol）不因平台而改寫。

## 前置條件

- 執行環境有下列環境變數（Paperclip runtime 自動注入）：`PAPERCLIP_API_URL`、`PAPERCLIP_API_KEY`、`PAPERCLIP_COMPANY_ID`、`PAPERCLIP_TASK_ID`（當前工單）、`PAPERCLIP_RUN_ID`。
- `curl` 與 `jq` 可用。
- **base URL 正規化**（`PAPERCLIP_API_URL` 可能帶或不帶結尾 `/api`，直接串接會變成 `/api/api/...`）：

  ```sh
  PAPERCLIP_API_BASE="${PAPERCLIP_API_URL%/}"; PAPERCLIP_API_BASE="${PAPERCLIP_API_BASE%/api}"
  AUTH=(-H "Authorization: Bearer $PAPERCLIP_API_KEY" -H "Content-Type: application/json")
  ```

  下文所有指令假設已執行上面兩行。

- 佔位符慣例：`<CID>`＝`$PAPERCLIP_COMPANY_ID`、`<PID>`＝專案 UUID、`<ID>`＝工單 UUID、`<REF>`＝人類可讀的 issue_ref（如 `MYL-12`）。**API 一律吃 UUID，不吃 `<REF>`**——查法見附錄 A。

## 共通語意對照

| 介面概念（`../SKILL.md` §2） | Paperclip 對應 | 注意 |
| --- | --- | --- |
| issue_ref | `identifier`（`MYL-12`） | API 參數用 `id`（UUID）；兩者對照見附錄 A |
| status 六態 | `status` 欄位 | Paperclip 實際有 **7 態**（多一個 `backlog`），見下方 |
| 標準 label 集 | company labels ＋ 工單 `labelIds` | label 是**公司層**資源，跨專案共用 |
| milestone | goal（`goalId`） | Paperclip 無 milestone 概念，以 goal 承載 |
| relation `parent` | `parentId` | |
| relation `blocked_by` | `blockedByIssueIds` | 一級 blocker，平台會據此擋狀態流轉 |

### 七態 vs 六態

Paperclip 的 `status` 枚舉是 `backlog｜todo｜in_progress｜in_review｜done｜blocked｜cancelled`。介面只認六態：

- **寫入**：`update_status` 永不寫 `backlog`——超出介面的值不得由 Foundry 流程產生。
- **讀取**：讀到 `backlog` 時在 `list_issues` 輸出中映射為 `todo`，並在結果標註原值，供人工判斷是否需要正規化。
- 平台無「開／關」概念，`done`／`cancelled` 不需額外的關閉動作（與 github adapter 不同）。

### 全量替換欄位（本 adapter 最容易出錯的地方）

`labelIds` 與 `blockedByIssueIds` 在 `PATCH /api/issues/<ID>` 是**整批覆蓋**語意：送什麼就變成什麼，沒送的會被清空。介面要求 `set_labels` 不得整批覆蓋、`link_issues` 重複建立要冪等，因此這兩個動詞一律**先讀、算集合、再寫**（read-modify-write），絕不直接送一個憑空組出來的陣列。

## 動詞對照

### init_structure

Paperclip 的看板、三種檢視（board／table／roadmap 對應清單、表格、時間軸）是**平台內建功能，無需也無法用 API 建立**——這一步在本 adapter 退化為「建 label 集＋建 milestone 容器」。

1. 建標準 label 集（先查重再建；`name` 上限 48 字元、`color` 必須是 `#RRGGBB`）：

   ```sh
   EXIST=$(curl -s "${AUTH[@]}" "$PAPERCLIP_API_BASE/api/companies/<CID>/labels" | jq -r '.[].name')
   add_label() {  # $1=名稱 $2=色碼
     printf '%s\n' "$EXIST" | grep -qx "$1" && return 0
     curl -s -X POST "${AUTH[@]}" -d "$(jq -n --arg n "$1" --arg c "$2" '{name:$n,color:$c}')" \
       "$PAPERCLIP_API_BASE/api/companies/<CID>/labels" >/dev/null
   }
   for l in type:brd type:prd type:hld type:lld type:impl type:review type:test type:docs; do add_label "$l" "#5319E7"; done
   for l in role:product-analyst role:scrum-master role:tech-lead role:developer role:code-reviewer role:qa; do add_label "$l" "#0E8A16"; done
   for l in size:small size:medium size:large; do add_label "$l" "#FBCA04"; done
   ```

2. 建 milestone 容器（goal；重跑先查重，已存在則跳過）：

   ```sh
   curl -s -X POST "${AUTH[@]}" \
     -d '{"title":"<里程碑名>","description":"<說明>","level":"team","status":"active"}' \
     "$PAPERCLIP_API_BASE/api/companies/<CID>/goals"
   ```

3. 看板與三個 view：平台內建，**不執行任何動作**；報告註明「由平台提供」，不列為待辦。
- **冪等**：兩步都先查重再建；重跑不新增、不覆蓋。
- **查證**：`curl -s "${AUTH[@]}" "$PAPERCLIP_API_BASE/api/companies/<CID>/labels" | jq '[.[].name|select(startswith("type:"))]|length'` 得 8；goal 查得到；重跑一次數量不變。

### create_issue

```sh
curl -s -X POST "${AUTH[@]}" -d "$(jq -n \
  --arg t "<標題>" --arg b "$(cat body.md)" --arg p "<PID>" \
  '{projectId:$p, title:$t, description:$b, status:"todo", priority:"medium", workMode:"standard"}')" \
  "$PAPERCLIP_API_BASE/api/companies/<CID>/issues" | jq '{id,identifier,status}'
```

- `description` 放 foundry-protocol 第 1 節四段骨架（adapter 不代為把關格式）。
- `type_label` 與其他 label 於開單後用 `set_labels` 掛上（開單 API 不吃 label 名稱，只吃 `labelIds`）。
- `milestone`／`assignee` 有給時，開單後分別用 `set_milestone` 與 `PATCH … {"assigneeAgentId":"<agent UUID>"}` 設定。
- 子單另有捷徑：`POST /api/issues/<父單ID>/children` 開單即帶 `parentId`，省一次 `link_issues`。
- **查證**：回傳的 `identifier` 即新 issue_ref；`list_issues` 查得到。

### update_status

```sh
curl -s -X PATCH "${AUTH[@]}" -d '{"status":"<六態之一>"}' "$PAPERCLIP_API_BASE/api/issues/<ID>" | jq .status
```

- 從 `done`／`cancelled` 退回時加 `"reopen": true`（Paperclip 對已結案工單的一般寫入預設為惰性）。
- 轉 `blocked` 時一併依 foundry-protocol 第 2 節留言寫解除路徑；`unblockDescriptor` 的限制見下方「平台限制」。
- **查證**：重讀 `GET /api/issues/<ID>` 的 `status` 為指定值。

### comment

```sh
curl -s -X POST "${AUTH[@]}" -H "X-Paperclip-Run-Id: $PAPERCLIP_RUN_ID" \
  -d "$(jq -n --arg b "$(cat comment.md)" '{body:$b}')" \
  "$PAPERCLIP_API_BASE/api/issues/<ID>/comments"
```

- `X-Paperclip-Run-Id` 讓留言歸屬到當次 run，交接包／審查結論一律帶上。
- 對**已結案**工單留言要生效（重啟後續工作）時，body 之外加 `"resume": true`；否則一般留言為惰性。
- **查證**：`GET /api/issues/<ID>/comments | jq '.[-1].body'` 為剛發的內容，未截斷。

### set_labels

`labelIds` 是全量替換，因此三步固定：

```sh
# 1. 取 label 名稱 → UUID 對照
MAP=$(curl -s "${AUTH[@]}" "$PAPERCLIP_API_BASE/api/companies/<CID>/labels")
# 2. 讀現有 labelIds，加上 add、去掉 remove
CUR=$(curl -s "${AUTH[@]}" "$PAPERCLIP_API_BASE/api/issues/<ID>" | jq -c '.labelIds')
NEW=$(jq -n --argjson cur "$CUR" --argjson map "$MAP" \
  --argjson add '["<要加的label名>"]' --argjson rm '["<要移除的label名>"]' '
  ($map|map({(.name):.id})|add) as $byName
  | ($add|map($byName[.])) as $addIds
  | ($rm|map($byName[.])) as $rmIds
  | (($cur + $addIds) | unique | map(select(. as $i | $rmIds | index($i) | not)))')
# 3. 寫回
curl -s -X PATCH "${AUTH[@]}" -d "$(jq -n --argjson l "$NEW" '{labelIds:$l}')" \
  "$PAPERCLIP_API_BASE/api/issues/<ID>"
```

- `add` 中的 label 名稱查不到 UUID → 報錯停止，**不自動建立 label**（建立走 `init_structure`）。
- **查證**：`GET /api/issues/<ID> | jq '[.labels[].name]'`，add 全在、remove 全不在、其餘原樣保留。

### set_milestone

```sh
GID=$(curl -s "${AUTH[@]}" "$PAPERCLIP_API_BASE/api/companies/<CID>/goals" \
  | jq -r --arg t "<里程碑名>" '.[]|select(.title==$t)|.id')
[ -n "$GID" ] || { echo "goal 不存在：<里程碑名>" >&2; exit 1; }   # 不自動建立
curl -s -X PATCH "${AUTH[@]}" -d "$(jq -n --arg g "$GID" '{goalId:$g}')" "$PAPERCLIP_API_BASE/api/issues/<ID>"
```

- 移除（`milestone=none`）：送 `{"goalId": null}`。
- **查證**：`GET /api/issues/<ID> | jq '.goalId'`。

### list_issues

```sh
curl -s "${AUTH[@]}" "$PAPERCLIP_API_BASE/api/companies/<CID>/issues?view=compact" \
  | jq '[.[] | select(.status=="<status>")            # 各條件皆選填、AND 組合
              | select([.labels[].name] | index("<label>"))
              | {ref:.identifier, id, title, status, labels:[.labels[].name],
                 milestone:.goalId, assignee:.assigneeAgentId}]'
```

- **平台端只支援 `companyId` 與 `view` 兩個查詢參數**，status／labels／milestone／assignee 全部在 `jq` 端過濾。
- 只要當前專案時加 `select(.projectId=="<PID>")`。
- 唯讀，不改任何資料；空結果回傳 `[]`，不報錯。
- 讀到 `status=="backlog"` 依「七態 vs 六態」映射為 `todo` 並標註原值。

### link_issues

```sh
# parent：把 <ID> 掛為 <P> 的子單
curl -s -X PATCH "${AUTH[@]}" -d '{"parentId":"<P>"}' "$PAPERCLIP_API_BASE/api/issues/<ID>"

# blocked_by：標記 <ID> 被 <B> 阻塞（全量替換 → 先讀後寫）
CUR=$(curl -s "${AUTH[@]}" "$PAPERCLIP_API_BASE/api/issues/<ID>" | jq -c '[.blockedBy[].id]')
curl -s -X PATCH "${AUTH[@]}" -d "$(jq -n --argjson c "$CUR" --arg b "<B>" \
  '{blockedByIssueIds: ($c + [$b] | unique)}')" "$PAPERCLIP_API_BASE/api/issues/<ID>"
```

- 重複掛同一 blocker 因 `unique` 而冪等；`<P>`／`<B>` 不存在時 API 報錯，原樣回報、不代開新單。
- **查證**：`GET /api/issues/<ID> | jq '{parent:.parentId, blockers:[.blockedBy[].identifier]}'`。

## 平台限制（本 adapter 專屬，不上升為流程規則）

下列限制是 Paperclip 的實作特性。遇到時照本節處理，**不要把它們寫進 foundry-protocol**——換平台時這些限制不成立。

| 限制 | 處理方式 |
| --- | --- |
| `unblockDescriptor.owner` 只能填 agent 自己（填別人整筆 PATCH 都不生效） | 指望其他 agent 解鎖時，把對方工單掛進 `blockedByIssueIds` 作一級 blocker，`owner` 仍填自己、收尾動作寫在 `action`，「解除者是誰」寫在留言（Pilot 卡點 #4） |
| 公司層 skill 的匯入／更新，agent 呼叫一律 403 `skill_actor_restricted` | 屬 protocol 第 4 節 HITL 閘門第 6 條：發卡請使用者執行，不空轉重試（Pilot 卡點 #5） |
| agent 的 `terminate`／`delete`／`pause` 為 board-only（403） | 同上，發卡請使用者執行 |
| `labelIds`／`blockedByIssueIds` 為全量替換 | 一律 read-modify-write（見上方「全量替換欄位」） |
| 已結案工單的一般留言／PATCH 為惰性 | 需要重啟後續工作時帶 `"resume": true`；狀態退回帶 `"reopen": true` |
| 互動卡（`ask_user_questions`／`suggest_tasks`／`request_confirmation`）非本介面 8 動詞 | 屬 protocol 第 4 節關卡與閘門的執行手段，走 `POST /api/issues/<ID>/interactions`；本 adapter 不重複定義 |

## 附錄 A：issue_ref（`MYL-12`）→ UUID

```sh
curl -s "${AUTH[@]}" "$PAPERCLIP_API_BASE/api/companies/<CID>/issues?view=compact" \
  | jq -r --arg r "<REF>" '.[]|select(.identifier==$r)|.id'
```

當前工單的 UUID 可直接用環境變數 `$PAPERCLIP_TASK_ID`，不必查。

## 附錄 B：本文指令的查證狀態

| 類別 | 狀態 |
| --- | --- |
| 所有 `GET`（issues／comments／documents／labels／goals／openapi.json） | 2026-09-03 於本公司實機執行驗證 |
| `PATCH /api/issues/<ID>` 的欄位集合、`POST …/labels`、`POST …/goals`、`POST …/comments` 的 body schema | 依平台 `GET /api/openapi.json` 的 schema 定義 |
| `POST /api/companies/<CID>/issues` 的 body | OpenAPI 未展開該 schema；欄位取自 issue 物件實際回傳欄位與既有開單實務 |

首次在新專案套用本 adapter 時，先用一張測試工單走一遍 `create_issue → set_labels → update_status → comment → list_issues`，確認無誤再正式使用。
