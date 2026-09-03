---
name: foundry-platform
description: Foundry 平台 adapter 抽象層。凡是要對「執行層」（工單、狀態、里程碑、看板）做任何讀寫——開單、改狀態、留言、掛 label、查工單、建關聯、初始化平台骨架——先載入本文，依 .foundry/config.yml 的 platform 欄位選定 adapter 對照文檔，再照對照文檔執行具體指令。不得繞過 adapter 直接對平台下未列於對照文檔的寫入操作。
---

# foundry-platform：平台 adapter 介面

依 MYL-9 HLD §2 制定（repo 歸檔本：`docs/features/cross-platform/HLD.md`，下同）。執行層（工單／進度／里程碑／看板）的所有操作收斂成 **8 個抽象動詞**；每個支援的平台有一份對照文檔（`adapters/<name>.md`）把動詞翻成具體指令。流程規範（foundry-protocol）只引用抽象動詞，不綁定平台——新增平台時只需新增一份對照文檔，介面與流程都不動。

## 1. 使用方式

1. 讀專案根目錄的 `.foundry/config.yml`（schema 見 `config-schema.md`），取得 `platform` 欄位。
2. 依值載入對照文檔：`github` → `adapters/github.md`；`local-md` → `adapters/local-md.md`；`paperclip` → `adapters/paperclip.md`。
3. 要做的操作對應到下方哪個動詞，就照對照文檔中該動詞的指令執行。
4. 對照文檔沒有涵蓋的平台寫入操作，一律不做——需要新操作時先開單擴充介面，不得私下直呼平台指令繞過。
5. 找不到 `.foundry/config.yml` 時視為專案尚未導入 Foundry：停下，走 `foundry-init`（新專案）或 `foundry-adopt`（既有開發中專案），不得自行猜測平台。

## 2. 共通詞彙

所有動詞共用下列定義；兩份 adapter 都必須遵守，不得各自另創。

- **issue_ref**：平台無關的工單參照。github＝issue 編號（`#12`）；local-md＝檔名主幹（`FND-12`）；paperclip＝`identifier`（`MYL-12`，API 參數另需 UUID，對照見該 adapter 附錄 A）。
- **status**：六態，與 foundry-protocol 第 2 節一一對應：`todo`｜`in_progress`｜`in_review`｜`blocked`｜`done`｜`cancelled`。平台自身的狀態集比六態多時（如 paperclip 多一個 `backlog`），由 adapter 明定映射規則，**六態之外的值不得由 Foundry 流程寫入**。
- **依賴**：工單間的硬依賴一律用 `link_issues` 的 `blocked_by` 關聯表達，不用工單內文的文字描述代替（foundry-protocol 第 2 節）。各平台的承載欄位由 adapter 定義（github＝`Blocked-by:` 留言慣例＋`blocked` label；local-md＝frontmatter `blocked_by`；paperclip＝`blockedByIssueIds`）。
- **標準 label 集**（`init_structure` 建立，命名空間固定）：
  - `type:brd`、`type:prd`、`type:hld`、`type:lld`、`type:impl`、`type:review`、`type:test`、`type:docs`
  - `role:product-analyst`、`role:scrum-master`、`role:tech-lead`、`role:developer`、`role:code-reviewer`、`role:qa`
  - `size:small`、`size:medium`、`size:large`（gates 的 `skip_below` 依此判定；未掛 size label 視為 `medium`）
- **relation**：工單關聯只有兩種：`parent`（子單 → 父單）與 `blocked_by`（本單被某單阻塞）。方向以「動詞主詞」為準，見 §3.8。

## 3. 動詞介面

每個動詞定義：輸入、行為、成功判準。錯誤處理共通規則見 §4。

### 3.1 init_structure

- **輸入**：無（讀 `.foundry/config.yml` 取得平台與選項）。
- **行為**：建立平台側骨架——§2 標準 label 集、里程碑容器、專案看板＋三個 view（board：依 status 分欄；table：全欄位清單；roadmap：依 milestone 時間軸）。
- **冪等**：重跑不得報錯、不得清空或覆蓋既有資料；已存在的元素跳過或就地補齊。
- **成功判準**：標準 label 全數存在；三個 view 可開；重跑一次結果不變。

### 3.2 create_issue

- **輸入**：`title`（必填）、`body`（必填，依 foundry-protocol 第 1 節四段骨架）、`type_label`（必填，`type:*` 之一）、`milestone`（選填）、`assignee`（選填）、`labels`（選填，追加的其他 label）。
- **行為**：開一張新工單，初始 status 為 `todo`（body 骨架不合格時仍可建立，由流程層退回，adapter 不代為把關）。
- **成功判準**：回傳新工單的 issue_ref；用 `list_issues` 查得到該單且欄位正確。

### 3.3 update_status

- **輸入**：`issue_ref`、`status`（六態之一）。
- **行為**：把工單狀態改為指定值。`done`／`cancelled` 同時關閉工單（平台有開關概念時）；自其他狀態離開 `done`／`cancelled` 時重新開啟。
- **成功判準**：`list_issues` 以該 status 過濾能查到此單。

### 3.4 comment

- **輸入**：`issue_ref`、`body`（markdown）。
- **行為**：在工單追加一則留言，附時間與作者身分。交接包、審查結論、blocked 解除路徑都走此動詞（foundry-protocol 第 2、3 節）。
- **成功判準**：留言出現在工單討論串，內容完整未截斷。

### 3.5 set_labels

- **輸入**：`issue_ref`、`add`（label 清單，可空）、`remove`（label 清單，可空）。
- **行為**：增刪工單 label。不得整批覆蓋——只動 add／remove 列出的項目。
- **成功判準**：查詢該單 label 集合，add 全在、remove 全不在。

### 3.6 set_milestone

- **輸入**：`issue_ref`、`milestone`（名稱，或 `none` 表示移除）。
- **行為**：設定或移除工單的里程碑。指定的 milestone 不存在時報錯，不自動建立（建立走 `init_structure` 或人工）。
- **成功判準**：查詢該單顯示指定 milestone（或已無 milestone）。

### 3.7 list_issues

- **輸入**：過濾條件，全部選填、可組合：`status`、`labels`、`milestone`、`assignee`。
- **行為**：回傳符合條件的工單清單，每筆至少含：issue_ref、title、status、labels、milestone、assignee。唯讀，不改任何資料。
- **成功判準**：結果與平台側實際狀態一致；空結果回傳空清單，不報錯。

### 3.8 link_issues

- **輸入**：`issue_ref`（主詞）、`relation`（`parent`｜`blocked_by`）、`target_ref`。
- **行為**：
  - `parent`：把 `issue_ref` 掛為 `target_ref` 的子單。
  - `blocked_by`：標記 `issue_ref` 被 `target_ref` 阻塞；`target_ref` 進入 `done` 前，`issue_ref` 依 foundry-protocol 第 2 節不得離開 `blocked`。
- **成功判準**：關聯在平台側可查得（兩份 adapter 各自定義查法）；重複建立同一關聯冪等、不報錯。

## 4. 錯誤處理共通規則

- `issue_ref` 或 `target_ref` 不存在 → 立即報錯並停止該操作，**不得靜默略過、不得自動開新單代替**。
- 平台指令失敗（權限、網路、認證）→ 原樣保留錯誤輸出，依 foundry-protocol 第 2 節判斷是否轉 `blocked`；連續兩次同指令失敗即停止重試。
- 寫入類動詞（除 `list_issues` 外全部）執行後，用對照文檔標明的查證指令確認結果，才算完成。

## 5. 跨平台相容原則（MYL-9 HLD §6.3）

- 本文與兩份對照文檔皆為純 markdown＋YAML frontmatter，任何 agent runtime（Claude Code、Codex 等）或人類皆可直接閱讀照做，不依賴特定 runtime 專屬功能。
- 對照文檔中的指令一律是可直接在 shell 執行的完整範例（含佔位符說明），不是偽代碼。
- 新增平台（如 GitLab）：新增 `adapters/gitlab.md` 覆蓋全部 8 個動詞＋在 `config-schema.md` 的 `platform` 枚舉補值，介面本文不改。做不到全覆蓋的平台不得上線——寧缺勿殘。
- **平台專屬限制寫在 adapter，不上升為流程規則**（MYL-35）：某平台的欄位語意、權限例外、API 怪癖（如 paperclip 的 `labelIds` 全量替換、`skill_actor_restricted` 403）一律收在該 adapter 的「平台限制」一節；foundry-protocol 與角色 skill 只引用抽象動詞與六態，換平台時**只換 adapter、不改規範**。判準：一句規則若在其他平台字面上不成立，它就屬於 adapter。

## 6. 檔案地圖

| 檔案 | 內容 |
| --- | --- |
| `SKILL.md`（本文） | 介面定義：8 動詞、共通詞彙、錯誤規則 |
| `adapters/github.md` | 動詞 → gh CLI 指令對照 |
| `adapters/local-md.md` | 動詞 → `.foundry/board/` 檔案操作對照 |
| `adapters/paperclip.md` | 動詞 → Paperclip REST API 對照（含平台限制表） |
| `config-schema.md` | `.foundry/config.yml` 欄位說明 |
| `config.example.yml` | 設定檔範例（含註解），`foundry-init` 據此產生實際檔案 |
