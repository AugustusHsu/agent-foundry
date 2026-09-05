---
name: foundry-platform
description: Foundry 平台 adapter 抽象層。凡是要對「執行層」（工單、狀態、里程碑、看板）做任何讀寫——開單、改狀態、留言、掛 label、查工單、建關聯、初始化平台骨架——或要把文檔投影到對外閱讀面（wiki、文檔站），先載入本文，依 .foundry/config.yml 的 devtools_platform／docs 欄位選定 adapter 對照文檔，再照對照文檔執行具體指令。不得繞過 adapter 直接對平台下未列於對照文檔的寫入操作。
---

# foundry-platform：平台 adapter 介面

依 MYL-9 HLD §2 制定（repo 歸檔本：`docs/features/cross-platform/HLD.md`，下同）。本檔定義 **3 個介面**，各自由不同的設定欄位分派：

| 介面 | 動詞 | 由哪個設定欄位分派 | 屬哪條軸 | 管什麼 |
| --- | --- | --- | --- | --- |
| **執行層** | §3.1–§3.8 共 8 個 | `devtools_platform` | 軸 B | 工單／狀態／里程碑／看板 |
| **文檔投影** | §3.9 `publish_docs` | `docs`（宿主平台由 `mirror_platform`／`devtools_platform` 決定） | 軸 B | 源頭文檔 → 對外閱讀面 |
| **組織層** | §8 `provision_team` | `ai_platform` | **軸 A** | `.foundry/org.yml` 的宣告 → 平台上真的存在的一支團隊 |

⚠️ **「9 個動詞」指的是前兩列**（§3.1–§3.9）。`provision_team` 不是第 10 個——它由另一條軸分派，理由與界線見 §8 開頭，別把它讀成「九動詞再加一個」。

⚠️ **「軸」在本檔曾經是另一個意思。** MYL-52 當時把上表前兩列稱為「兩條軸」，MYL-78 之後「軸」是 A／B 的專有名詞（軸 A＝agent 在哪個殼裡跑，軸 B＝工單與文檔在哪；定義見 `../foundry-ai-platform/SKILL.md` §0）。兩個切法不重疊：**執行層與文檔投影都在軸 B 之內**。本檔以下一律用「介面」稱前兩列的分別，§5 那段 `<details>` 保留當時的原文，指的是同一件事。

每個支援的平台有一份對照文檔（`adapters/<name>.md`）把動詞翻成具體指令。流程規範（foundry-protocol）只引用抽象動詞，不綁定平台——新增平台時只需新增一份對照文檔，介面與流程都不動。

**執行層與文檔投影為什麼要分開分派**（MYL-52 裁定，理由見 §5）：一個專案的工單可以在 A 平台、文檔面在 B 平台，這不是假設性的——**本 repo 自己就是**：`devtools_platform: paperclip`，而手冊投影到 GitHub wiki。把 `publish_docs` 掛在 `devtools_platform` 上分派，本 repo 會被判成「不支援文檔投影」。同一個道理：`model_routing` 那段也是獨立軸（見 `config-schema.md`），別混。

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

**本節只有軸 B 的九個動詞**，全部由 `devtools_platform`／`docs` 分派。軸 A 的 `provision_team` 在 §8，不在本節——把它編成 §3.10 會讓「同一條軸上的第 10 個動詞」這個誤讀在編號上就成立。

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
  - 組織層平台（`ai_platform` 的值）＝§8 `provision_team` 完整定義。**這一項的門檻與上面兩項不同**：軸 A 沒有「寧缺勿殘」，缺了是降級不是不合格，見下方 MYL-77 裁定。
  - **三者互不蘊含**：只做執行層的平台不因為沒有 `publish_docs` 而殘缺，只做文檔面的目標也不必實作工單動詞，而軸 B 的平台**根本不在組織層這一軸上**——不是沒做完。

  <details><summary><b>MYL-77 裁定：加 `provision_team` 為什麼沒有讓四份 adapter 全部不合格</b></summary>

  同一個問題第二次出現，但答案的形狀跟 MYL-52 那次不一樣，所以不能照抄結論。逐份判：

  | adapter | 是不是 `ai_platform` 的合法值 | 判定 |
  | --- | --- | --- |
  | `paperclip.md` | ✅ 是 | **要覆蓋，且已覆蓋**（該檔「provision_team」一節）。四份裡唯一同時承載軸 A 與軸 B 的一份 |
  | `github.md` | ❌ 不是 | **不適用**，不列入本介面的覆蓋判定 |
  | `gitlab.md` | ❌ 不是 | 同上 |
  | `local-md.md` | ❌ 不是 | 同上 |

  關鍵差別：MYL-52 那次，`paperclip` **有可能**被 `docs` 段指到卻沒有文檔面，那是「同一條軸上做不到」，所以必須改寫全覆蓋的定義才不會誤傷。這次三份軸 B adapter 連被 `ai_platform` 指到的可能性都沒有（枚舉是 `paperclip`｜`claude-code`｜`codex`，權威在 `config-schema.md`）——**不是能力不足，是不在這一軸**。§8 與那三份 adapter 因此都不用「降級」這個詞：降級的前提是同軸上撐不住。

  三份軸 B adapter 仍各增了一節，但**那一節不是為了滿足全覆蓋**：它回答的是另一個問題——當一個專案的軸 B 是 GitHub／GitLab／local-md 時，`org.yml` 宣告的那份編制在**這個平台上**還看得到嗎（AC3／AC4）。答案是看得到，但只以文檔形式（見各該節）。

  **真正的缺口在軸 A 這一側，而它刻意不擋上線**：`ai_platform` 的三個合法值裡，只有 `paperclip` 覆蓋得了 `provision_team`；`claude-code`／`codex` 沒有 agent 註冊表，覆蓋不了，也不會有 adapter 檔。依 `../foundry-ai-platform/SKILL.md` §7 最後一段，軸 A **沒有**「全覆蓋否則不得上線」的門檻，缺一項是降級（走該檔 `AP-4`）。所以 `ai_platform: codex` 的專案帶著這個缺口上線是允許的——**別把軸 B 的寧缺勿殘套過來**，套過來的結果是三個 AI 平台裡有兩個當場不合格。
  </details>

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
| `SKILL.md`（本文） | 介面定義：軸 B 的 9 動詞（8 執行層＋1 文檔投影）、共通詞彙、錯誤規則；**§8 另定義軸 A 的 `provision_team`** |
| `adapters/github.md` | 執行層動詞 → gh CLI 指令對照；**另含 `publish_docs` 的兩個投影面**（wiki 主閱讀面、mkdocs 精裝站）；末節寫組織層在本平台的文檔落點 |
| `adapters/gitlab.md` | 執行層動詞 → GitLab REST API v4 對照（含 Free／Premium 分岔）；**另含 `publish_docs` 的兩個投影面**（wiki、Pages）；末節寫組織層在本平台的文檔落點。**本 repo 無 GitLab 實例，全文未實跑**，證據等級見該檔附錄 B |
| `adapters/local-md.md` | 執行層動詞 → `.foundry/board/` 檔案操作對照；末節寫組織層退化成的 roster 檔 |
| `adapters/paperclip.md` | 執行層動詞 → Paperclip REST API 對照（含平台限制表）；**另含 §8 `provision_team` 的唯一實作面**——四份裡唯一同時承載軸 A 的一份 |
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
| **【軸 A】** `provision_team` | ✅ `POST /companies/<CID>/agents` 起的四步（見 `adapters/paperclip.md`） | 本軸不適用 → 組織只剩文檔落點（`CODEOWNERS`＋`role:*` label＋roster） | 本軸不適用 → 同左，`CODEOWNERS` 另受 Premium 限制 |

⚠️ **最後一列的欄位標題要換一條軸讀。** 前面每一列的欄名都是 `devtools_platform` 的值（軸 B）；
`provision_team` 由 `ai_platform` 分派，而 `github`／`gitlab` **不是 `ai_platform` 的合法值**——
那兩格填的不是「這個 AI 平台做不到」，是「當專案的軸 B 是它時，組織宣告在這個平台上以什麼形式存在」。
軸 A 三個平台自己的對照（`paperclip`／`claude-code`／`codex`）不在本表，在 `../foundry-ai-platform/SKILL.md` §3。

**換平台時真正會咬人的三件事**（其餘差異照 adapter 走就好）：

1. **喚醒面與可見面往往不是同一個平台。** 這不是假設：本 repo 執行在 paperclip、可見面鏡像到
   github；來源專案 SuperOD 正本在自架 GitLab、鏡像到 GitHub。表格最後一列就是 `mirror_platform`
   存在的全部理由——搬工單前先問「搬過去之後還叫得動人嗎」。
2. **「狀態」在三個平台是三種東西**（原生欄位／專案欄位／label），而 `cancelled` 是最容易掉的一態：
   gitlab 上它與 `done` 在平台層完全同形，漏掛 label 不會有任何地方報錯。
3. **兩個 wiki 不是同一種 wiki。** 頁面層級、首頁與側欄命名、錨點 slug 演算法都不同，
   照抄轉換規則會得到「頁面渲染正常、連結按了不跳」的無聲失敗（`L16`）。投影面換宿主
   一律當成新的目標面重新驗一次錨點，不繼承前一個平台的驗證結果。

## 8. 軸 A 介面：`provision_team`

依 MYL-77 制定。承 MYL-76：`.foundry/org.yml` 讓一支團隊**可宣告**；本節讓那份宣告**可套用**。

### 8.1 它為什麼不是第 10 個動詞

三個理由，任一個成立就不該與 §3 同列；三個同時成立。

1. **分派欄位不同。** §3 的九個動詞由 `devtools_platform`／`docs` 分派，本動詞由 `ai_platform` 分派。這不是分類癖：一個專案可以是 `devtools_platform: github` ＋ `ai_platform: paperclip`（工單在 GitHub、團隊在 Paperclip）。若 `provision_team` 跟著 `devtools_platform` 走，這個專案會被帶去 `adapters/github.md` 找 agent 註冊表、找不到，然後判成「本專案不支援建團隊」——而它明明建得出來。**這是 MYL-52 對 `publish_docs` 的同一個論證，換一條軸再跑一次**（§5 那段 `<details>` 的第 ② 點）。
2. **覆蓋門檻不同。** 軸 B 是「寧缺勿殘」，少一個動詞不得上線；軸 A 缺一項是**降級**，帶著缺口上線是允許的（`../foundry-ai-platform/SKILL.md` §7 末段）。把兩者編在同一節，遲早有人拿同一把尺去量。
3. **adapter 的形狀不同。** 軸 B 是「每個平台一份對照文檔」；軸 A **只有 `paperclip` 有落點**，`claude-code`／`codex` 沒有 agent 註冊表，不會有對照文檔，它們的規則寫在 `foundry-ai-platform` 的能力矩陣裡。硬要湊出兩份空的 adapter，就是 MYL-52 否決過的「憑空發明、沒有人驗得了」。

### 8.2 介面定義

- **輸入**：`.foundry/org.yml`（**唯一的編制輸入**，schema 權威見 `config-schema.md`）。本動詞**不吃「要建哪些角色」這類參數**——要改編制去改 `org.yml`，而那份檔案有自己的授權路徑（agent 不得自行改，見同一份 schema 的「誰能改 `org.yml`」）。另有兩個隱含輸入：`.foundry/config.yml` 的 `ai_platform`（決定讀哪一份對照），以及 foundry-protocol 第 8 節（`model_tier` 的高／中／低 → 實際 model／effort 的對應）。

- **前置閘門**（四條全過才動手；任一條不過就**不做任何寫入**）：
  1. `org.yml` 合法，且 `--selfcheck` 的 `org-sync` 是綠的。宣告本身歪掉還往平台上建，只是把錯誤放大成平台狀態。
  2. `ai_platform` 的值有對照文檔。沒有（`claude-code`／`codex`）→ 走 §8.3 的降級，**這不是錯誤**，報告寫明即可。
  3. **執行者持有建置權限。** 沒有就停下發卡，不得自我授權（`H6`）。本 repo 的 `create_agents` 依 MYL-61 卡 `f80e66b3` Q5 是**臨時**授權，用完收回——所以本動詞不得假設權限是常設的。
  4. **建成員會持續花錢**（每個成員各自燒模型額度），觸發 `H3`。第一次在一個專案上跑本動詞**必須經使用者核可**；`H3` 不因為「org.yml 已經寫了」而豁免——宣告不是預算核可。

- **行為**（先對帳，再逐角色收斂）：
  1. **對帳**：讀平台現況，與 `org.yml` 的 `roles` 比對，分成三堆——**缺的**／**有但設定不符的**／**平台上多出來的**。對帳鍵用 `title` 而不是 `id`：`title` 依 schema 全檔唯一且逐字等於組織圖節點名，`id` 只是 repo 內的名字，平台上不保證有承載處。
  2. **缺的** → 建立成員。
  3. **不符的** → 就地補齊四項：匯報線（`reports_to`）、模型層（`model_tier`）、掛載 skill（`skills`）、權限（`permissions`）。**只改對不上的那幾項**，不整批覆寫。
  4. **多出來的** → **只列進報告，不動手**（理由見冪等）。

- **冪等**：
  - 重跑不得重建已存在的成員、不得清空既有設定；「已存在」以 `title` 判定。
  - **本動詞只增不減。** 平台上多出來的成員一律只報告。三個理由缺一都不行：①刪成員是不可逆的破壞性操作，屬 `H5`，而且動到編制就是關卡 `G-C` 的範圍；②`org.yml` 是「應然」不是平台的鏡子（`config-schema.md` 明訂 `org-sync` **刻意不比對平台實況**），拿應然去裁剪實然會刪掉正在跑的東西；③在 Paperclip 上刪除／終止／暫停根本是 board-only，agent 打過去一律 403（見 `adapters/paperclip.md`）。
  - 判準：同一份 `org.yml` 連跑兩次，**第二次應該全部落在「已符合」那一堆**。

- **成功判準**（五條，缺一不算成功）：
  1. `org.yml` 的每個 `roles` 項目在平台上都找得到對應成員；
  2. 每個成員的匯報線、模型層、掛載 skill、權限四項與宣告一致，且**逐項用對照文檔標明的查證指令讀回來確認**——寫入 API 自己回 200 不算數（§4 共通規則）；
  3. 查證讀不回來的項目**明列為「未證實」**，不得當成通過。adapter 有權限邊界時這種格子一定會出現（`adapters/paperclip.md` 現在就有兩個），把它算成通過等於用查不到冒充查過了；
  4. 平台上多出來的成員列成清單交給使用者；
  5. 重跑一次，三堆的分佈不變。

- **失敗怎麼收**：
  - 任一步失敗 → **停在該角色，不回滾已經建好的成員**。回滾就是刪除，刪除是 `H5`；而且本動詞是冪等的，從中斷處重跑本來就會收斂——回滾除了製造不可逆操作之外什麼也沒換到。把「已完成到哪一個角色」寫進工單，依第 2 節轉 `blocked` 或發卡。
  - 權限不足（403）→ 依 §4，連續兩次同一指令失敗即停止重試，發卡請使用者執行，不空轉。
  - 建到一半發現 `org.yml` 與規範對不上 → 停下，依 `O1` 判斷缺口在哪一邊，**不是就地改 `org.yml` 遷就平台**（agent 也改不得）。

### 8.3 可攜性的誠實上限

**這一節是規格正文，不是附註。** 理由見 MYL-61 `org-review` §7.4：組織層的落差如果不寫在規格裡，會等到導入做完才發現對不上，而那時候已經沒有便宜的退路了。

| 層 | 內容 | 可攜性 | 換平台時實際會發生什麼 |
| --- | --- | --- | --- |
| **規則層** | foundry-protocol、角色 skill、模板、lint 檢查 | **100% 可攜** | 純 markdown＋Python，複製過去一行都不用改 |
| **執行層** | §3 的九個動詞 | **可攜** | 換一份 adapter，介面與流程規範都不動（§5） |
| **組織層** | 誰是誰、匯報線、權限、模型層 | **只在有 agent 註冊表的平台可攜** | 沒有註冊表時 `provision_team` 建不出任何東西，`org.yml` 退化成一份「**人**要扮演哪個角色」的對照表 |

三件事要說清楚，否則上面那張表會被讀成「組織層做得不夠好」：

1. **這不是本動詞沒做完，是這一層沒有平台無關的載體。** 「可以被指派、而且會醒過來的角色」是 Paperclip 這類 AI 平台的產物；GitHub／GitLab 上只有**人**與**權限**，沒有這種東西。九個抽象動詞裡也從來沒有一個是「建組織」——那個缺口是 MYL-61 `org-review` 盤出來的，不是本節造成的。
2. **落差的形狀是「宣告可攜、套用不可攜」。** `org.yml` 是純 YAML，複製到任何專案都照樣被 `org-sync` 驗；驗得過不代表建得出來。導入一個 `ai_platform: codex` 的專案時，`org.yml` 一字不改仍然成立，但它從那一刻起只是一份**約束人的文件**。
3. **剩下的三樣東西約束得了人，喚不醒任何東西。** 沒有註冊表的平台上，組織層只剩：角色定義（`skills/roles/`）、審查責任歸屬（`CODEOWNERS`）、「誰扮演哪個角色」對照表。三樣都是文檔，指派一個名字不會讓任何人開始工作——`../foundry-ai-platform/SKILL.md` 的 `AP-2` 講的那件事，在組織層原封不動再發生一次。

**降級規則的權威不在本檔**：軸 A 上做不到 `provision_team` 時怎麼辦，以 `../foundry-ai-platform/SKILL.md` 的 `AP-4`（單一身分怎麼維持角色分工）為準，本節不另立一套。本節只負責兩件事：把上限寫進正文，以及要求**導入報告必須明列這一條**——與 `AP-2`／`AP-4` 的硬約束同一個要求，不得靜默略過。
