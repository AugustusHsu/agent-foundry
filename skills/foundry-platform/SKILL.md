---
name: foundry-platform
description: Foundry 平台 adapter 抽象層。凡是要對「執行層」（工單、狀態、里程碑、看板）做任何讀寫——開單、改狀態、留言、掛 label、查工單、建關聯、初始化平台骨架——或要把文檔投影到對外閱讀面（wiki、文檔站），先載入本文，依 .foundry/config.yml 的 devtools_platform／docs 欄位選定 adapter 對照文檔，再照對照文檔執行具體指令。不得繞過 adapter 直接對平台下未列於對照文檔的寫入操作。
---

# foundry-platform：平台 adapter 介面

依 MYL-9 HLD §2 制定（repo 歸檔本：`docs/features/cross-platform/HLD.md`，下同）。本介面有 **9 個抽象動詞**，分屬兩條互相獨立的軸：

| 介面 | 動詞 | 由哪個設定欄位分派 | 管什麼 |
| --- | --- | --- | --- |
| **執行層** | §3.1–§3.8 共 8 個 | `devtools_platform` | 工單／狀態／里程碑／看板 |
| **文檔投影** | §3.9 `publish_docs` | `docs`（宿主平台由 `mirror_platform`／`devtools_platform` 決定） | 源頭文檔 → 對外閱讀面 |

每個支援的平台有一份對照文檔（`adapters/<name>.md`）把動詞翻成具體指令。流程規範（foundry-protocol）只引用抽象動詞，不綁定平台——新增平台時只需新增一份對照文檔，介面與流程都不動。

**兩條軸為什麼要分開**（MYL-52 裁定，理由見 §5）：一個專案的工單可以在 A 平台、文檔面在 B 平台，這不是假設性的——**本 repo 自己就是**：`devtools_platform: paperclip`，而手冊投影到 GitHub wiki。把 `publish_docs` 掛在 `devtools_platform` 上分派，本 repo 會被判成「不支援文檔投影」。同一個道理：`model_routing` 那段也是獨立軸（見 `config-schema.md`），別混。

## 1. 使用方式

1. 讀專案根目錄的 `.foundry/config.yml`（schema 見 `config-schema.md`），取得 `devtools_platform` 欄位。
2. 依值載入對照文檔：`github` → `adapters/github.md`；`gitlab` → `adapters/gitlab.md`；`local-md` → `adapters/local-md.md`；`paperclip` → `adapters/paperclip.md`。**只讀當前平台那一份**；要看跨平台差異走 §7 的對照表，不要把四份都載進來。
3. 要做的操作對應到下方哪個動詞，就照對照文檔中該動詞的指令執行。
4. 對照文檔沒有涵蓋的平台寫入操作，一律不做——需要新操作時先開單擴充介面，不得私下直呼平台指令繞過。
5. 找不到 `.foundry/config.yml` 時視為專案尚未導入 Foundry：停下，走 `foundry-init`（新專案）或 `foundry-adopt`（既有開發中專案），不得自行猜測平台。
6. 要跑 `publish_docs` 時改讀 `docs` 段。對照文檔由**宿主平台**決定：`mirror_platform` 有值取它、否則取 `devtools_platform`（判定方式與 `config-schema.md` 的 `docs` 合法性規則同一條）——宿主是 `github` 時，`primary: wiki` 與 `mirror_site` 兩個面都在 `adapters/github.md` 的「§publish_docs」一節。`docs` 段缺席＝本專案不做文檔投影，此時 `publish_docs` 不可用，**這不是設定缺漏**。

## 2. 共通詞彙

所有動詞共用下列定義；兩份 adapter 都必須遵守，不得各自另創。

- **issue_ref**：平台無關的工單參照。github＝issue 編號（`#12`）；gitlab＝專案內編號 `iid`（`#12`，**不是**全域 `id`，對照見該 adapter 附錄 A）；local-md＝檔名主幹（`FND-12`）；paperclip＝`identifier`（`MYL-12`，API 參數另需 UUID，對照見該 adapter 附錄 A）。
- **status**：六態，與 foundry-protocol 第 2 節一一對應：`todo`｜`in_progress`｜`in_review`｜`blocked`｜`done`｜`cancelled`。平台自身的狀態集比六態多時（如 paperclip 多一個 `backlog`），由 adapter 明定映射規則，**六態之外的值不得由 Foundry 流程寫入**。
- **依賴**：工單間的硬依賴一律用 `link_issues` 的 `blocked_by` 關聯表達，不用工單內文的文字描述代替（foundry-protocol 第 2 節）。各平台的承載欄位由 adapter 定義（github＝`Blocked-by:` 留言慣例＋`blocked` label；gitlab＝Premium 用原生 `is_blocked_by` 關聯、Free 退回與 github 相同的留言慣例；local-md＝frontmatter `blocked_by`；paperclip＝`blockedByIssueIds`）。
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

### 3.9 publish_docs

把**源頭文檔**機械投影到一個對外閱讀面。判準只有一條，其餘規定都是它推導出來的：

> **機械投影不是第二份真相。人只改源頭，投影一律機械產生且不接受手改。**

（MYL-39 計畫 v3 用同一條否決過 E-2「手抄快照」。同一件事不能有兩套標準。）

- **輸入**：
  - `source_dir`：來源目錄，**唯一可寫的真相**（本 repo＝`docs/handbook/`）。
  - `target`：目標面，取自 `.foundry/config.yml` 的 `docs.primary`（主閱讀面）或 `docs.mirror_site`（精裝面）。一個專案可以同時有兩個面，各自有自己的觸發時機。
  - `trigger`：觸發時機，`on_merge_main`｜`on_tag`｜`manual`。宣告用途——動詞本身不排程，排程是 CI 或執行者的事。
- **行為**：
  1. **過前置閘門**：`source_dir` 的變更必須已合併進 main，且有對應的發佈審查證據（本 repo＝MYL-24 審查記錄 ＋ MYL-44 戳記旁路，見 foundry-protocol 第 7 節）。閘門不過就**不做任何寫入**。
  2. **防手改偵測**：比對目標面現況是不是上一次投影推上去的那一份。不是就**拒絕覆蓋並報錯**，不得自行覆寫——覆寫等於把別人寫的東西靜靜刪掉。放棄目標面上的改動必須是人的顯式決定（旗標／參數），不是預設行為。
  3. **投影**：來源 → 目標面的轉換必須是**確定性**的（同樣的來源永遠產出同樣的位元組），且轉換規則寫在 adapter，不留給執行者臨場判斷。
  4. **逐章比對**：投影完成後逐章比對標題文字、章節數、內部連結目標、規則層戳記行是否存活。**不接受「應該搬完了」，缺一章就是紅燈**，紅燈時不得推送。
- **成功判準**：目標面完整含有 `source_dir` 的全部章節；逐章比對表全綠；目標面留下可供下次防手改比對的投影記錄（本 repo＝commit trailer 記來源 sha 與內容摘要）。
- **失敗即停**：上述任一步失敗都**不推送**，並原樣保留錯誤輸出。這個動詞沒有「先推上去再修」的模式——目標面是對外的。
- **本動詞屬對外動作**：新開一個目標面（啟用 wiki、新建公開 repo、開 Pages）是關卡 C（`gates.external_actions: user`，不可調降），**不在本動詞授權範圍內**；本動詞只負責「已開通的管道」的例行同步（本 repo 依 MYL-23 分級表屬 P2）。

## 4. 錯誤處理共通規則

- `issue_ref` 或 `target_ref` 不存在 → 立即報錯並停止該操作，**不得靜默略過、不得自動開新單代替**。
- 平台指令失敗（權限、網路、認證）→ 原樣保留錯誤輸出，依 foundry-protocol 第 2 節判斷是否轉 `blocked`；連續兩次同指令失敗即停止重試。
- 寫入類動詞（**除 `list_issues` 外全部，含 `publish_docs`**）執行後，用對照文檔標明的查證指令確認結果，才算完成。`publish_docs` 的查證就是 §3.9 的逐章比對表——腳本自己回報成功不算數（known-drift `X2`：發佈互蓋過，當時腳本也回報成功）。

## 5. 跨平台相容原則（MYL-9 HLD §6.3）

- 本文與兩份對照文檔皆為純 markdown＋YAML frontmatter，任何 agent runtime（Claude Code、Codex 等）或人類皆可直接閱讀照做，不依賴特定 runtime 專屬功能。
- 對照文檔中的指令一律是可直接在 shell 執行的完整範例（含佔位符說明），不是偽代碼。
- 新增平台（如 GitLab）：新增 `adapters/gitlab.md` **覆蓋該介面的全部動詞**＋在 `config-schema.md` 的對應枚舉補值，介面本文不改。做不到全覆蓋的不得上線——寧缺勿殘。
  - 執行層平台（`devtools_platform` 的值）＝§3.1–§3.8 的 8 個動詞全覆蓋。
  - 文檔投影宿主（被 `docs` 段指到的平台）＝`publish_docs` 完整定義（轉換規則、防手改比對依據、逐章比對方式），且 `docs.primary` 用得到的面都要涵蓋。
  - **兩者互不蘊含**：只做執行層的平台不因為沒有 `publish_docs` 而殘缺，只做文檔面的目標也不必實作工單動詞。

  <details><summary><b>MYL-52 裁定：加第 9 個動詞為什麼沒有讓既有三份 adapter 全部不合格</b></summary>

  加 `publish_docs` 時，本節原本寫的是「新增平台要覆蓋全部 8 個動詞」，字面上會讓 `github.md`／`paperclip.md`／`local-md.md` 當場全部不合格。三條路擺在眼前，選的是第三條——**改寫「全覆蓋」的定義**，理由如下：

  - **① 三份 adapter 全部補齊 `publish_docs`：否決。** Paperclip 沒有文檔面（它的 documents 掛在單張工單上，不是一本手冊），補出來的會是憑空發明的東西，而發明出來的規格沒有人驗得了。
  - **② 把 `publish_docs` 標為選配動詞：否決。** 選配只是讓分派錯軸這件事靜默下來，沒有解決它。**本 repo 就是決定性反例**：`devtools_platform: paperclip`、文檔面卻在 GitHub wiki。若 `publish_docs` 跟著 `devtools_platform` 分派，本 repo 讀到的是 `adapters/paperclip.md`，得到「本平台不支援文檔投影」——而本 repo 正在做文檔投影。選配讓這個矛盾不報錯，不代表它不存在。
  - **③ 改寫定義（採用）**：`publish_docs` 由 `docs` 段分派（宿主取 `mirror_platform`／`devtools_platform`），與執行層的 `devtools_platform` 正交；「全覆蓋」改為**每個介面各自全覆蓋**。既有三份 adapter 維持為執行層 adapter，全部仍然合格；`github.md` 另外多一個身分——它同時是 wiki 與 mkdocs 精裝站兩個文檔投影面的對照文檔。

  「寧缺勿殘」的原意（不讓半套平台上線）因此完整保留：殘不殘的判準是「**宣告支援的那個介面有沒有做完**」，而不是「有沒有做完所有介面」。
  </details>
- **平台專屬限制寫在 adapter，不上升為流程規則**（MYL-35）：某平台的欄位語意、權限例外、API 怪癖（如 paperclip 的 `labelIds` 全量替換、`skill_actor_restricted` 403）一律收在該 adapter 的「平台限制」一節；foundry-protocol 與角色 skill 只引用抽象動詞與六態，換平台時**只換 adapter、不改規範**。判準：一句規則若在其他平台字面上不成立，它就屬於 adapter。

## 6. 檔案地圖

| 檔案 | 內容 |
| --- | --- |
| `SKILL.md`（本文） | 介面定義：9 動詞（8 執行層＋1 文檔投影）、共通詞彙、錯誤規則 |
| `adapters/github.md` | 執行層動詞 → gh CLI 指令對照；**另含 `publish_docs` 的兩個投影面**（wiki 主閱讀面、mkdocs 精裝站） |
| `adapters/gitlab.md` | 執行層動詞 → GitLab REST API v4 對照（含 Free／Premium 分岔）；**另含 `publish_docs` 的兩個投影面**（wiki、Pages）。**本 repo 無 GitLab 實例，全文未實跑**，證據等級見該檔附錄 B |
| `adapters/local-md.md` | 執行層動詞 → `.foundry/board/` 檔案操作對照 |
| `adapters/paperclip.md` | 執行層動詞 → Paperclip REST API 對照（含平台限制表） |
| `config-schema.md` | `.foundry/config.yml` 與 `.foundry/org.yml` 欄位說明（MYL-76 起兩份設定檔共用本檔）|
| `config.example.yml` | 設定檔範例（含註解），`foundry-init` 據此產生實際檔案 |

## 7. 跨平台對照表

「換到別的平台，這一步怎麼做」的速查（MYL-56）。**本表不是規格，是索引**——每一格只給形狀，
權威在對應的 adapter。三欄取 `paperclip`／`github`／`gitlab`，理由是這三個是有遠端平台的實作；
`local-md` 是無 server 的退路（工單就是 `.foundry/board/` 裡的檔案），它的每一格都是「改檔案」，
列進來只會沖淡真正的差異——要它的對照直接讀 `adapters/local-md.md`。

| 面向 | paperclip | github | gitlab |
| --- | --- | --- | --- |
| 存取方式 | REST API（`curl`） | `gh` CLI ＋ GraphQL | REST API v4（`curl`）；`glab` 選配 |
| issue_ref | `identifier`（`MYL-12`），API 另需 UUID | issue 編號（`#12`） | 專案內 `iid`（`#12`），非全域 `id` |
| status 承載 | 原生 `status` 欄位（七態，映射到六態） | ProjectV2 的 Status 欄位（要三個 ID） | scoped label `status::*` |
| `done` vs `cancelled` | 原生兩個不同值 | 關單 reason（`completed`／`not planned`） | **平台上無從區分**，唯一載體是 `status::` label |
| label 增刪 | `labelIds` **全量替換** → read-modify-write | `--add-label`／`--remove-label` 增量 | `add_labels`／`remove_labels` 增量（`labels=` 是全量，不用） |
| milestone | goal 物件 | 吃名稱 | 設定吃**數字 id**、查詢吃**名稱** |
| `parent` | `parentIssueId` | sub-issue API（GraphQL） | 父單描述的 task list `- [ ] #<iid>` |
| `blocked_by` | `blockedByIssueIds`（全量替換） | `blocked` label ＋ `Blocked-by:` 留言 | Premium：原生關聯；Free：同 github 的留言慣例 |
| 看板 | 平台內建 | ProjectV2＋三 view（**view 只能 GraphQL 建**，`L11`） | 專案內建 board／issues 頁；roadmap 是 Premium |
| 工單清單含不含 PR／MR | 不適用 | **REST `/issues` 會混進 PR**（要自行濾） | `/issues` **不含 MR** |
| `publish_docs` 主閱讀面 | **無**（documents 掛在單張工單上，不是一本手冊） | wiki（頁面**平的**、首頁 `Home`、側欄 `_Sidebar.md`） | wiki（**允許目錄層級**、首頁 `home`、側欄 `_sidebar`） |
| `publish_docs` 精裝面 | 無 | 公開鏡像 repo ＋ Pages | Pages（`pages` job ＋ `public/` artifact） |
| 指派會不會喚醒 agent | **會**（指派＝喚醒，`S7`） | 不會 | 不會 |

**換平台時真正會咬人的三件事**（其餘差異照 adapter 走就好）：

1. **喚醒面與可見面往往不是同一個平台。** 這不是假設：本 repo 執行在 paperclip、可見面鏡像到
   github；來源專案 SuperOD 正本在自架 GitLab、鏡像到 GitHub。表格最後一列就是 `mirror_platform`
   存在的全部理由——搬工單前先問「搬過去之後還叫得動人嗎」。
2. **「狀態」在三個平台是三種東西**（原生欄位／專案欄位／label），而 `cancelled` 是最容易掉的一態：
   gitlab 上它與 `done` 在平台層完全同形，漏掛 label 不會有任何地方報錯。
3. **兩個 wiki 不是同一種 wiki。** 頁面層級、首頁與側欄命名、錨點 slug 演算法都不同，
   照抄轉換規則會得到「頁面渲染正常、連結按了不跳」的無聲失敗（`L16`）。投影面換宿主
   一律當成新的目標面重新驗一次錨點，不繼承前一個平台的驗證結果。
