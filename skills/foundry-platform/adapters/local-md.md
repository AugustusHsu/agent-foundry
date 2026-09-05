# adapter：local-md

`devtools_platform: local-md` 時的動詞對照。介面語意見 `../SKILL.md`。無 git server 平台可用時的 fallback：以 repo 內 `.foundry/board/` 目錄模擬執行層，全部操作都是本地檔案讀寫（MYL-9 HLD §2.4）。日後遷移到 GitHub 由 `foundry-adopt` §4 轉換。

## 目錄結構

```
.foundry/board/
├── issues/          一單一檔：<ID>.md（frontmatter 存狀態欄位，body 存內容與留言）
├── milestones.md    全部里程碑，單一檔
└── views/           預存查詢定義＋最近一次快照：board.md、table.md、roadmap.md
```

## 資料格式

### issues/<ID>.md

檔名主幹即 issue_ref（如 `FND-12.md` → `FND-12`）。前綴取自 `.foundry/config.yml` 的 `platform_options.local-md.id_prefix`（預設 `FND`），序號遞增。

```markdown
---
id: FND-12
title: 範例工單標題
status: in_progress        # todo | in_progress | in_review | blocked | done | cancelled
labels: [type:impl, role:developer, size:small]
milestone: v1              # 無則寫 null
assignee: developer        # 無則寫 null
parent: FND-9              # 無則寫 null
blocked_by: []             # issue_ref 清單
created: 2026-09-03
updated: 2026-09-03
---

（此處為工單 body，依 foundry-protocol 第 1 節四段骨架）

## 留言

### 2026-09-03 tech-lead

（一則留言一個 `### <日期> <作者>` 小節，依時間順序追加在檔尾）
```

- frontmatter 是唯一的狀態真實來源；`## 留言` 之前為 body、之後為討論串，兩區都只增不刪。
- 日期一律 `YYYY-MM-DD`（本地時區）。

### milestones.md

```markdown
# Milestones

## v1

- due: 2026-12-31
- state: open            # open | closed
- description: 首個可用版本
```

一個 milestone 一個 `## <名稱>` 小節。

### views/*.md

view 檔＝frontmatter 的查詢定義＋body 的快照。`list_issues` 執行後**應**重新產生對應快照（見該動詞）。

```markdown
---
view: board
filters: {}                # 同 list_issues 的過濾條件
group_by: status           # board 依 status 分組；table 不分組；roadmap 依 milestone
generated: 2026-09-03
---

## in_progress

| id | title | labels | milestone | assignee |
| --- | --- | --- | --- | --- |
| FND-12 | 範例工單標題 | type:impl | v1 | developer |
```

## 寫入紀律（全動詞共通）

- board 目錄在 git 版控內：**每次寫入類動詞完成後，立即以一個獨立 commit 收尾**（訊息如 `🎫 FND-12 狀態 → in_review`），這是 local-md 模式下多執行者協調的唯一機制。
- 修改任何 issue 檔的 frontmatter 時，一併更新 `updated` 欄位。
- 只用文字編輯工具改檔；不得用腳本整批重寫整個 `issues/` 目錄。

## 動詞對照

### init_structure

1. 建目錄：`mkdir -p .foundry/board/issues .foundry/board/views`。
2. 建 `milestones.md`（已存在則跳過）：只含 `# Milestones` 標題，milestone 內容由使用者或後續流程增補。
3. 建三個 view 檔（已存在則跳過）：`views/board.md`（`group_by: status`）、`views/table.md`（無分組全欄位）、`views/roadmap.md`（`group_by: milestone`），frontmatter 照上方格式、body 先放空快照。
4. 標準 label 集（`../SKILL.md` §2）在本 adapter 無需預建——label 只存在於各 issue 的 frontmatter，合法值以介面文檔為準。
- **冪等**：所有步驟先檢查存在再建立。
- **查證**：三個 view 檔與 `milestones.md` 存在；重跑無報錯、內容不變。

### create_issue

1. 取號：掃 `issues/` 現有檔名的最大序號＋1（目錄空則從 1 起）。
2. 依「資料格式」建 `issues/<新ID>.md`：`status: todo`、`labels` 含 type_label、milestone／assignee 依輸入（未給則 `null`）、`parent: null`、`blocked_by: []`、created／updated 為今天。body 放輸入的四段骨架，檔尾加空的 `## 留言` 節。
3. `milestone` 有給時，須先存在於 `milestones.md`，否則報錯（同 `set_milestone` 規則）。
- **查證**：新檔可讀、frontmatter 欄位齊全；回報新 ID。

### update_status

1. 改 `issues/<ID>.md` frontmatter 的 `status` 為指定值，更新 `updated`。
2. local-md 無「開／關」概念，`done`／`cancelled` 不需額外動作。
- **查證**：重讀 frontmatter 值正確。

### comment

在 `issues/<ID>.md` 檔尾（`## 留言` 節內）追加：

```markdown
### <YYYY-MM-DD> <作者角色名>

<留言內容>
```

並更新 frontmatter 的 `updated`。

- **查證**：檔尾出現該小節、內容完整。

### set_labels

改 frontmatter 的 `labels` 清單：加入 `add` 中缺少的、移除 `remove` 中存在的，其餘不動；更新 `updated`。

- **查證**：重讀 `labels`，add 全在、remove 全不在。

### set_milestone

1. 目標名稱須存在於 `milestones.md` 的 `## <名稱>` 小節，否則報錯、不自動建立。
2. 改 frontmatter 的 `milestone` 為該名稱（輸入 `none` 時改為 `null`）；更新 `updated`。
- **查證**：重讀 `milestone` 值正確。

### list_issues

1. 逐檔讀 `issues/*.md` 的 frontmatter，依輸入條件（status／labels／milestone／assignee，AND 組合）過濾。
2. 輸出每筆至少含：id、title、status、labels、milestone、assignee。空結果回空清單。
3. 查詢條件與某個 view 檔的 `filters`＋`group_by` 相符時，把結果依該 view 的格式重寫其 body 快照並更新 `generated`——view 快照因此永遠是「最近一次查詢」的產物，人類直接開 view 檔就能看板。
- **查證**：抽一筆對照原始檔 frontmatter 一致。

### link_issues

- `parent`（把 `<ID>` 掛為 `<P>` 的子單）：改 `issues/<ID>.md` frontmatter 的 `parent: <P>`。`<P>` 檔不存在則報錯。
- `blocked_by`（標記 `<ID>` 被 `<B>` 阻塞）：把 `<B>` 加進 `issues/<ID>.md` frontmatter 的 `blocked_by` 清單（已在則冪等跳過）。`<B>` 檔不存在則報錯。
- **查證**：重讀 frontmatter，關聯欄位正確；反向查詢用 `list_issues` 逐檔比對 `parent`／`blocked_by` 欄位即可，不另存反向索引（單一真實來源）。
