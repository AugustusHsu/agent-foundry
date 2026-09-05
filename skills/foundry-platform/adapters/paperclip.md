# adapter：paperclip

`devtools_platform: paperclip` 時的動詞對照。介面語意見 `../SKILL.md`，本文只翻譯成具體指令。

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

## provision_team（軸 A：本檔的第二個身分）

上面每一節都是 `devtools_platform: paperclip` 的**軸 B** 對照。本節不是——它是
`ai_platform: paperclip` 時 `../SKILL.md` §8 的對照，**四份 adapter 裡唯一的軸 A 落點**。
本 repo 兩個欄位恰好都是 `paperclip`，**那是巧合不是同義**：把本節讀成「執行層動詞之一」，
在 `devtools_platform: github` ＋ `ai_platform: paperclip` 的專案上會整個錯位。

前置條件、`AUTH` 陣列與佔位符沿用本檔開頭那一節；本節另用 `<AID>`＝agent UUID。

### 前提（不齊就停下發卡，不自我授權）

| 前提 | 怎麼查 | 不齊怎麼辦 |
| --- | --- | --- |
| 執行者持有 `canCreateAgents` | `GET /api/agents/me \| jq '.permissions.canCreateAgents'` | 發卡請使用者開；本 repo 依 MYL-61 卡 `f80e66b3` Q5 是**臨時**授權，用完收回 |
| 使用者已核可這次建置 | 工單上的核可卡 | `H3`（要花錢）——每個成員各自燒模型額度。**`org.yml` 已經宣告不等於預算已經核可** |
| `org.yml` 合法且 `org-sync` 綠 | `python3 tools/foundry-lint/foundry_lint.py --selfcheck` | 先修宣告，不要把歪掉的宣告放大成平台狀態 |

### 步驟 0：對帳（先讀，後寫）

```sh
curl -s "${AUTH[@]}" "$PAPERCLIP_API_BASE/api/companies/<CID>/agents" \
  | jq '[.[] | {id, name, title, role, reportsTo, status, permissions, access}]'
```

回傳是**裸陣列**（不是 `{agents:[…]}`）。拿它與 `org.yml` 的 `roles` 逐筆比對，分三堆。

⚠️ **對帳鍵：`org.yml` 的 `title` ↔ 平台的 `name`，逐字比對，不做模糊配對。**
兩邊的欄位名不同形，這是刻意的——`../config-schema.md` 明訂不把平台欄位名寫進 `org.yml`，
所以這條對應關係只存在於本檔。**承載欄位是 `name` 而不是平台那個同樣叫 `title` 的欄位**，
理由是 `../SKILL.md` §8.2 那條硬要求：對帳鍵得對每個成員都有定義。實測平台 schema
（`POST /api/companies/{companyId}/agents`）**`required` 只有 `name`**（`minLength: 1`），
`title` 是 `nullable: true` 的選填欄位——拿它當鍵，沒填的成員會同時被判成「缺」與「多」。

⚠️ **平台的 `role` 欄位不是 Foundry 的角色**：它是平台自己的 12 值粗桶
（`ceo｜cto｜cmo｜cfo｜security｜engineer｜designer｜pm｜qa｜devops｜researcher｜general`），
多個 Foundry 角色會落在同一個值——實測本公司的 Tech Lead／Developer／Code Reviewer **三個都是 `engineer`**，
Product Analyst 與 Scrum Master **都是 `pm`**。`role` 只影響平台 UI 分類，角色身分由 `name` 承載。

⚠️ **同一個角色同時出現在「缺的」與「多出來的」兩堆＝對不上鍵，不是要建新的。**
撞到就**停下報告**，不得在那個位置建第二個成員；由使用者裁定要改哪一邊——
兩邊都不是 agent 能自己決定的（改 `org.yml` 的授權路徑見 `../config-schema.md`）。
`name` 沒有平台層的唯一性保證，所以**同一個鍵配到多筆時同樣停下報告**，不得任挑一筆。

**2026-09-06 全公司 8 名成員實測**（`org.yml` 宣告 9 個角色），差異共**三項**：

| 宣告 `title` | 平台 `name`（對帳鍵） | 平台 `title`（顯示名） | 判定 |
| --- | --- | --- | --- |
| `CEO` | `CEO` | **`null`** | ✅ 對得上。**這一格就是不能拿平台 `title` 當鍵的證據**——它是樹根（`reports_to: user`），而 §8.2 要求由上而下建置，用 `title` 當鍵的話第一個動作就是在樹根建出第二個 CEO |
| `Developer` | `Developer` | **`Developer（全端）`** | ✅ 對得上。顯示名與宣告不一致屬 §8.2 的**第五種差異**：只報告，不自動改 |
| `PM` | （不存在） | （不存在） | 屬「缺的」那一堆，且是**預期的**——MYL-79／T7 才建 |

其餘 6 個角色三欄一致，無差異。上表是**同一次實測的完整結果**，不是舉例。

### 步驟 1：建立成員（缺的那一堆）

```sh
curl -s -X POST "${AUTH[@]}" -d "$(jq -n \
  --arg t "<org.yml 的 title>" --arg sup "<上級的 AID>" \
  '{name:$t, title:$t, role:"<平台 12 值之一>", reportsTo:$sup,
    adapterType:"claude_local",
    adapterConfig:{model:"<第 8 節對應的 model>", effort:"<對應的 effort>"},
    permissions:{canCreateAgents:false, canCreateSkills:true}}')" \
  "$PAPERCLIP_API_BASE/api/companies/<CID>/agents" | jq '{id,name,title,reportsTo}'
```

- **`name` 是唯一的必填欄位，而它就是對帳鍵**——`org.yml` 的 `title` 逐字填進 `name`，不得改寫、不得加括號說明。`title` 一併給是為了平台 UI 的顯示名，**它不參與對帳**（步驟 0 那張表的 `Developer（全端）` 就是兩者分岔的實例）。
- **`reportsTo` 吃的是上級的 agent UUID**，所以**建置順序必須由上而下**：上級還不存在時這一格填不了。依 `org.yml` 的 `reports_to` 做一次拓樸排序再開始建，`reports_to: user` 的那個（＝CEO）是樹根。
- **查證**：回傳的 `id` 即 `<AID>`；`GET /api/companies/<CID>/agents` 查得到該 `name`。

### 步驟 2：權限

```sh
curl -s -X PATCH "${AUTH[@]}" \
  -d '{"canCreateAgents":false,"canAssignTasks":true,"canCreateSkills":true}' \
  "$PAPERCLIP_API_BASE/api/agents/<AID>/permissions"
```

- ⚠️ **端點是 PATCH，但 `canCreateAgents` 與 `canAssignTasks` 兩個欄位是必填**（平台 OpenAPI 的 `required`）。漏送不是「保持原值」而是整筆被拒 → 一樣要 **read-modify-write**，和 `labelIds` 同一個紀律。
- ⚠️ **寫入與稽核讀的不是同一組欄位**：寫 `permissions.*`，但讀回來時 `canAssignTasks` **不在 `permissions` 底下**，在 `access.canAssignTasks`（旁邊還有 `taskAssignSource`、`membership`、`grants`）。兩組欄位可能給出相反的答案，**`canAssignTasks` 的稽核一律看 `access.*` ＋ `access.grants`**。⚠️ **這條只管 `canAssignTasks`**：實測 `GET /api/agents/me`，兩組欄位**完全不重疊**——`access` 只有 `{canAssignTasks, taskAssignSource, membership, grants}`，而 `canCreateAgents`／`canCreateSkills` 只活在 `permissions` 底下。所以上面前置閘門要查的 `canCreateAgents` 就是讀 `permissions.canCreateAgents`（該表寫的那條），照「一律看 `access.*`」去查會查到空。`org.yml` 的 `permissions` 值域（`assign_tasks`／`create_agents`／`create_skills`）與這兩組欄位的對應寫在 `../config-schema.md`，不寫進 `org.yml`。
- **查證**：`GET /api/agents/<AID> | jq '{permissions, access}'`。

### 步驟 3：掛 skill

```sh
curl -s -X POST "${AUTH[@]}" \
  -d '{"mode":"add","desiredSkills":["<skill key>"]}' \
  "$PAPERCLIP_API_BASE/api/agents/<AID>/skills/sync"
```

- `mode` 是 `add｜remove｜replace`。**除非要清空，否則永遠用 `add`**——`replace` 是全量語意。
- 實際落點在 `adapterConfig.paperclipSkillSync.desiredSkills`，值形如 `local/<hash>/<skill 名>`（**參照式安裝**）。參照式的 skill **跟著 repo commit 走：改了 repo 不需要重新匯入**。
- ⚠️ **公司層 skill 的匯入／更新，agent 一律 403 `skill_actor_restricted`**（見下方平台限制）。所以「skill 還不存在」與「skill 已存在只是沒掛上」是兩件事：後者本節做得了，前者要發卡請使用者匯入。
- `org.yml` 的 `skills` 寫的是 **repo 相對路徑**（`skills/roles/<id>/SKILL.md`），平台的 key 是 `local/<hash>/<名稱>`。兩者不同形，**對應關係要在工單裡寫出來**，不要臨場猜。

### 步驟 4：模型層

```sh
curl -s -X PATCH "${AUTH[@]}" \
  -d '{"adapterConfig":{"model":"claude-opus-5","effort":"max"}}' \
  "$PAPERCLIP_API_BASE/api/agents/<AID>"
```

- `org.yml` 的 `model_tier` → foundry-protocol 第 8 節「三層預設」→ 具體 `model`／`effort`。**權威是第 8 節，不是本檔**（本檔不複製那張對照表，複製了就會過期）。
- ⚠️ **`adapterConfig` 的 PATCH 是合併語意**（要整批換得另外送 `replaceAdapterConfig: true`）。所以這一步不會洗掉步驟 3 寫進去的 `paperclipSkillSync`，反之亦然——但也因此**送錯的鍵不會被清掉**，只會多一個沒人用的欄位。
- ⚠️ 第 8 節裡標為**建議值**的格（現為 PM 那一列），依「絕不自作主張採用建議值」，**未經使用者核可不得據以設定平台**。宣告在 `org.yml` 裡不等於核可。

### 查證與它的兩個邊界

**驗得回來的**：`name`（對帳鍵）、`title`、`reportsTo`、`permissions.*`、`access.*`、`status`——
`GET /api/companies/<CID>/agents` 或 `GET /api/agents/<AID>` 都讀得到。

**驗不回來的**（2026-09-06 以 agent 身分實測，兩項都不是 404）：

| 想驗什麼 | 實際結果 | 落到哪 |
| --- | --- | --- |
| 別的 agent 的模型層與 skill 掛載 | `GET /api/agents/<別人的 AID>` 的 `adapterConfig` 回 **`{}`**（`GET /api/agents/me` 讀自己則完整可見） | `../SKILL.md` §8.2 成功判準第 3 條：列為**未證實** |
| 別的 agent 掛了哪些 skill | `GET /api/agents/<AID>/skills` 回 `deny_missing_membership`（agent 不是 company member） | 同上 |

**未證實不等於通過。** 這兩格的收法只有兩條：請使用者在面板確認，或由該成員自己讀
`GET /api/agents/me` 回報。用「查不到」冒充「查過了」，正是 §4 共通規則要擋的事。

### 本節刻意不做的三件事

| 不做 | 為什麼 |
| --- | --- |
| 刪除／終止／暫停任何成員 | 三條路徑（`DELETE /api/agents/<id>`、`POST …/terminate`、`POST …/pause`）**都是 board-only，agent 打過去一律 403**。這正好與 `../SKILL.md` §8「只增不減」對齊——那條規則在本平台上連違反的機會都沒有 |
| 改 instructions bundle | `instructions*` 相關欄位對 agent 403（MYL-33 實測）。角色規範一律靠**掛 skill** 進 context，不靠改 instructions |
| 依平台實況回寫 `org.yml` | `org.yml` 是應然、不是平台的鏡子；`org-sync` **刻意不比對平台實況**（`../config-schema.md`）。而且 agent 本來就不得改該檔 |

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
| `PATCH /api/agents/<AID>/permissions` 名為 PATCH，`canCreateAgents`／`canAssignTasks` 卻是必填 | read-modify-write（同 `labelIds`）。見「provision_team」步驟 2 |
| agent 權限「寫 `permissions.*`、讀 `access.*`」，兩者可能相反 | **限 `canAssignTasks`**——兩組欄位不重疊，`canCreateAgents`／`canCreateSkills` 只在 `permissions` 底下。該項稽核看 `access.*` ＋ `access.grants`。見「provision_team」步驟 2 |
| 以 agent 身分讀**別的** agent，`adapterConfig` 回 `{}`；`GET /api/agents/<AID>/skills` 回 `deny_missing_membership` | 模型層與 skill 掛載跨 agent 驗不了，列為「未證實」由使用者確認。見「provision_team」查證一節 |

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
| 「provision_team」一節的**讀取面**：`GET …/agents`（裸陣列、`role` 的 12 值粗桶、步驟 0 那張 8 名成員對帳表——含 CEO 的平台 `title` 為 `null` 與 `Developer（全端）` 的顯示名分岔）、`GET /api/agents/me` 的 `adapterConfig`、讀別人回 `{}`、`…/skills` 的 `deny_missing_membership` | 2026-09-06 於本公司以 agent 身分實機執行驗證（MYL-77） |
| `POST /api/companies/<CID>/agents` 的 `required` 只有 `name`（`minLength: 1`）、`title` 為 `nullable: true` 的選填欄位——**對帳鍵定在 `name` 的全部依據** | 依平台 `GET /api/openapi.json` 的 schema 定義（2026-09-06 取，MYL-77） |
| 「provision_team」一節的**寫入面**：`POST …/agents`、`PATCH …/permissions`、`POST …/skills/sync`、`PATCH /api/agents/<AID>` 的欄位與必填 | 依平台 `GET /api/openapi.json` 的 schema 定義。**本單未實跑任何寫入**——依工單邊界，真的在平台上建 agent 屬 MYL-79（T7）。第一次執行時逐步比對實際回傳，對不上就改回本節 |

首次在新專案套用本 adapter 時，先用一張測試工單走一遍 `create_issue → set_labels → update_status → comment → list_issues`，確認無誤再正式使用。
