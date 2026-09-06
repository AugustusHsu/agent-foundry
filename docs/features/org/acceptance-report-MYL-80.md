# MYL-80 T8 端到端驗收報告：組織重新規劃（MYL-61 整包）

- **被驗範圍**：MYL-61 底下 T1～T7（MYL-73／74／75／76／77／78／79，另含 T9＝MYL-82）
- **驗收人**：QA Engineer（agent `14732ae9`）
- **執行 run**：`7f0e20ae-dd23-4dc4-8966-12cc2c1670c0`
- **基準 commit**：`130bbd3`（main，2026-09-06）
- **結論**：**通過，附一項不合格發現（F-1）與一項結構性觀察（F-2）**。詳見 §1 對照表與 §7 結論。

> **本報告的立場**：T8 的目的是驗「這一整包真的成立」，不是複述各單自己的結論。
> 因此本報告引用的每一格證據都是**本輪重新讀出來的現值**，不是引述前面幾張單的宣稱。
> 引述性的內容一律標明「引述」。

---

## 1. AC 對照表

| # | AC | 判定 | 證據指標 |
| --- | --- | --- | --- |
| AC1 | `org-sync` 綠：`.foundry/org.yml` ↔ protocol §9／§8 ↔ 平台實況三者一致 | ⚠️ **通過，但發現一項三方不一致（F-1）** | §2 |
| AC2 | PM 產狀態報告 → CEO 只讀報告做一個決定，全程 CEO 未載入原始材料 | ✅ **通過**，附結構性觀察 F-2 與一項界線修訂 | §3 |
| AC3 | 唯讀檢視模式：CEO 或 PM 開一次頁面截圖，標注「不作為關卡證據」，且無人拿它推進關卡 | ✅ **通過** | §4 |
| AC4 | 導入模擬：空目錄跑 `foundry-init`（`local-md`）＋`provision_team`，產出含團隊定義，問答問到 harness 與組織兩題 | ✅ **通過** | §5 |
| AC5 | 缺陷收容依 `D1`～`D4`：能退回原單就不開新單 | ✅ **通過** | §6 |

---

## 2. AC1：三向對帳

### 2.1 第一向：`.foundry/org.yml` ↔ protocol §9／§8（機械）

```
✅ [org-sync] 組織宣告與 protocol 第 9／8 節一致（9 名）
```

- 執行：`python3 tools/foundry-lint/foundry_lint.py --selfcheck`，於 commit `130bbd3`。
- 這一項**刻意不比對平台實況**（`foundry_lint.py:1128` 的 docstring 明寫，MYL-76 AC7）。
  所以它綠**不構成** AC1 的答案，只覆蓋三向裡的第一向。第二向必須另外讀平台。

### 2.2 第二向：`.foundry/org.yml` ↔ 平台實況（本輪逐名實讀）

對帳鍵依 `adapters/paperclip.md`「provision_team／步驟 0」：**`org.yml` 的 `title` ↔ 平台的 `name`**，逐字比對。
資料來源 `GET /api/companies/{cid}/agents` ＋ 每名 `GET /api/agents/{id}`，2026-09-06 05:0x 讀取。

- **集合比對**：宣告 9 名 ∖ 平台 9 名 = ∅；平台 ∖ 宣告 = ∅。**無「缺的」、無「多出來的」。**

| 宣告 `title` | 匯報線一致 | 平台顯示名 | 模型層 | 掛載 skill | 權限 |
| --- | --- | --- | --- | --- | --- |
| CEO | ✅（`reports_to: user` ↔ `reportsTo: null`）| `CEO` | 未證實 | 未證實 | ✅ |
| Product Analyst | ✅ → CEO | `Product Analyst` | 未證實 | 未證實 | ✅ |
| PM | ✅ → CEO | `PM` | 未證實 | 未證實 | ✅ |
| Scrum Master | ✅ → CEO | `Scrum Master` | 未證實 | 未證實 | ✅ |
| Frontend Verifier | ✅ → CEO | `Frontend Verifier` | 未證實 | 未證實 | ⚠️ 見下 |
| Tech Lead | ✅ → CEO | `Tech Lead` | 未證實 | 未證實 | ✅ |
| Developer | ✅ → Tech Lead | **`Developer（全端）`** | 未證實 | 未證實 | ✅ |
| Code Reviewer | ✅ → Tech Lead | `Code Reviewer` | 未證實 | 未證實 | ✅ |
| QA Engineer | ✅ → Tech Lead | `QA Engineer` | ✅ `claude-opus-5`／`high` | ✅ 2 份 | ✅ |

- **匯報線 9／9 一致**，含樹根（CEO 的 `reportsTo` 為 `null`，對應宣告的 `reports_to: user`）。
- **顯示名分岔一項**：`Developer（全端）` ≠ 宣告的 `Developer`。這是 `foundry-platform` §8.2 的
  **第五種差異**——規格明訂「只列進報告，不自動改」。**不是不一致，是已定義的容許差異。**
- **「未證實」8 名不是通過，也不是失敗**，是查證路徑被平台權限擋住（成功判準第 3 條要求明列）：
  - 模型層：以 agent 身分讀別人的 `adapterConfig` 一律回 `{}`（`L4`／平台限制表已記）。
  - 掛載 skill：`GET /api/agents/{id}/skills` 回 **403 `deny_missing_membership`**。
  - **本輪對這條限制的範圍有一項訂正（F-3）**：既有記載寫的是「讀**別的** agent」會被擋，
    但實測**讀自己也一樣 403**。自己這一格能驗得成，靠的是另一條路徑——
    `GET /api/agents/me` 的 `adapterConfig.paperclipSkillSync.desiredSkills`
    （回 `["local/…/foundry-protocol", "local/…/role-qa-engineer"]`，與 `org.yml` 宣告的
    `qa-engineer.skills[]` 兩項逐項對得上）。
- **權限逐格**（讀 `access.*` ＋ `access.grants[]`，不讀 `permissions.*`——依平台限制表）：

| 宣告 | 平台實況 | 判定 |
| --- | --- | --- |
| CEO：`assign_tasks`／`configure_agents`／`create_skills` | `canAssignTasks: true`（`ceo_role`）＋ grants `tasks:assign`、`agents:configure`、`skills:create` | ✅ |
| PM：`assign_tasks`／`create_skills` | `canAssignTasks: true`（`explicit_grant`）＋ grant `tasks:assign` | ✅ |
| 其餘 7 名：只有 `create_skills` | `canAssignTasks: false`／`taskAssignSource: none`、`grants: []`、`canCreateSkills: true` | ✅ 6 名 |
| Frontend Verifier：只有 `create_skills` | `canAssignTasks: **true**`／`simple_default`、`grants: []` | ⚠️ **已知且使用者知情下保留**（MYL-79 卡 `0bd69c99` Q5）。`org.yml` 檔頭已逐字登記。**不列為本輪新缺陷。** |
| CEO 的 `create_agents` 刻意不宣告 | `permissions.canCreateAgents: false` | ✅ 臨時授權確已收回 |

### 2.3 第三向：平台詞彙 ↔ 組織宣告 —— **F-1：不一致**

**這一格是本輪唯一的三方不一致，而且是實際踩到的，不是推論出來的。**

依「時機 1」為 MYL-104 建鏡像時，指令實際失敗：

```
gh issue create … --label "role:pm"
→ could not add label: 'role:pm' not found
```

- **標準 label 集是固定 6 個角色**（`skills/foundry-platform/SKILL.md:42`，三份 adapter 各抄一份：
  `adapters/github.md:21`、`adapters/gitlab.md:79`、`adapters/paperclip.md:61`）：
  `product-analyst`／`scrum-master`／`tech-lead`／`developer`／`code-reviewer`／`qa`。
- **`.foundry/org.yml` 與 protocol §9 是 9 個角色**。差集＝`role:pm`、`role:ceo`、`role:frontend-verifier`。
- 這條詞彙不是裝飾：`adapters/github.md`「時機 1」第 4 點寫明鏡像**不設 assignee**，
  **「負責角色以 `role:*` label 表達」**——所以 PM 承接的工單，在對外可見面上表達不出負責角色。
  跨平台對照表（`foundry-platform/SKILL.md:204`）另把 `role:*` label 列為軸 A 缺席時
  **組織的唯一文檔落點**，缺格會一路傳到那裡。
- **成因分佈**（我查過才寫，不是猜的）：`role:pm` 是 T1（MYL-73 把 PM 寫進 §9）之後才出現的缺口；
  `role:ceo`／`role:frontend-verifier` 兩格**早於 MYL-61**，不是本次重新規劃造成的。
  ⇒ **T1～T7 這一包要負責的是 `role:pm` 那一格**，另外兩格是既有缺口一併浮出來。

---

## 3. AC2：PM 產報告 → CEO 只讀報告做決定

**演練載體**（本輪為此開的兩張子單，都掛在 MYL-80 底下）：

| 單 | 角色 | 狀態 | 鏡像 |
| --- | --- | --- | --- |
| MYL-104 | PM（`eac62c45`） | 前半完成，因補 AC5 重啟中 | github#37／#38（**一對多，見 F-2**） |
| MYL-105 | CEO（`622b78d0`） | 執行中 | github#36 |

### 3.1 PM 側：已完成

- 報告落點：MYL-104 留言 `926963e2`（2026-09-06 05:08:41）。
- **自足性成立**：報告本文寫出八張單的狀態、交付物與落點，路徑與 sha 只作為事後抽查的出處；
  末節給出**恰好一個**待決事項與三個選項（A／B／C）及各自取捨，並明講「三者可組合，但要 CEO 明講，
  我不自行推斷成組合方案」。
- **PM 自述其產出方法是全部重查**（Paperclip issues API、`git log main`、`gh issue list`、實跑 `--selfcheck`），
  並主動指出本單描述裡的現況敘述已過期。

### 3.2 CEO 側：已完成，三項證據齊備

留言 `ffa716f5`（05:15:32）＋ MYL-104 上的 `fff64acb`（05:15:56）。

| AC3 要求 | 判定 | 內容 |
| --- | --- | --- |
| (a) 決定是什麼 | ✅ | 採 PM 選項 A 的責任線、**第一步從「補建」改成「先對帳」**、明確否決 B、C 的根因併進同一張單。已開 **MYL-108**（priority `high`、母單 MYL-80、指派 QA、六條 AC） |
| (b) 本輪讀了哪些東西 | ✅ | 逐項四筆：喚醒 payload／`GET /api/issues/{本單}` ×2／`GET /api/issues/{MYL-104}/comments`／`GET /api/openapi.json`。並列出未讀清單皆為 0（repo 檔案、其他工單、commit、GitHub API、`--selfcheck`、agent 註冊表） |
| (c) 有沒有載入原始材料 | ✅ | 明確聲明「沒有」，且**主動補報一項洩漏**：`GET /api/issues/{本單}` 的回應內嵌 `ancestors[]`，含 MYL-80／MYL-61 的完整 description，未請求也未當依據，但確實進了 context——「把判定權交出來，不自行認定無害」 |

**判定：AC2 通過。** CEO 未載入任何 T1～T7 的交付物內容，僅憑一份彙整報告就做出可執行的決定。
主動補報 `ancestors` 內嵌洩漏這一點，比「聲明沒有」本身更有說服力——它證明這個聲明是查過才寫的。

### 3.3 F-2：兩份報告都栽在同一種過期讀取，而**我自己也是其中一份**

這一格是本輪最重要的發現，而且它的形狀跟我原先以為的不一樣，訂正如下。

**事實序列**（全部以 GitHub REST 讀出的時間戳為準，非推論）：

| 時刻 | 事件 |
| --- | --- |
| 05:04:37 | #36 建立（MYL-105 的鏡像，QA） |
| 05:04:40 | #37 建立（MYL-104 的鏡像，Developer 對帳補建） |
| 05:05:07 | #38 建立（MYL-104 的鏡像，QA 依「時機 1」——**與 #37 撞車**） |
| **05:07:03** | **#38 已被另一個 run 去重**：移除來源標記、body 首行改成「重複鏡像，已作廢……保留較早建立的 #37」、`closed (not_planned)` |
| 05:08:41 | **PM 報告**斷言「MYL-104／105 在鏡像端找不到對應 issue」——`gh issue list` 落在 05:04:30 前後，早於 #37／#38 ⇒ **過期** |
| 05:12:09 | **QA（我）的訂正**斷言「#37 與 #38 撞成一對多，待 CEO 拍板關掉哪一張」——**#38 早在 05:07:03 就已經去重關閉了** ⇒ **同樣過期** |
| 05:12:05 | #37 被關閉（`completed`，PM 走「時機 3」） |

⇒ **PM 錯了一次，我也錯了一次，錯的是同一種錯。** 我原先把 F-2 寫成
「彙整型 PM 的失效模式」，那個歸因**太窄**：在一個併行 run 頻繁寫入同一片外部狀態的工作區裡，
**任何一份把外部現值抄進文字的報告，在寫完的那一刻就開始過期**——與作者是不是彙整層無關。
（這與 known-drift `X1` 是同一族：`X1` 講共用 workspace 的檔案，本項講的是共用的**外部平台狀態**。）

**接住它的不是我。** CEO 在只讀 MYL-104 留言串的前提下，自己看出
「三則 `Mirrored-to:` 登記都早於報告，而報告說漏建 ⇒ 真因可能是重複建或 recon 失真，
此時補建會生出第三張收不回來的公開 issue」，因而**否決了 PM 建議的 B**。
我的訂正留言同時存在於 MYL-105 串上，兩者都指向同一結論，
**但 CEO 的理由書引用的是那兩則登記、不是我的訂正**——所以不能把功勞算在外部注入上。

⇒ **修正後的結論**：這條鏈**有**自我糾錯能力，但它**不在報告層，在決策層**，
而且成立的前提是 **CEO 的讀取面是「一則報告 ＋ 它所在的留言串」，不是「一則報告」**。
CEO 自己把這一條寫進了觀察：「如果 CEO 的讀取面被界定成只有那一則報告，我會照建議執行 B，
去建第三張收不回來的公開 issue。」**這是對 protocol 第 9 節『彙整型 PM』界線的一項實測修訂建議**，
歸 CEO 決定要不要進規範，不在本報告權限內。

---

## 4. AC3：唯讀檢視模式 —— 通過

**執行者必須是 CEO 或 PM**：protocol `F1` 是**列舉**不是通則，QA 自己截圖不算數。
因此併入 MYL-104 作 AC5（留言 `fccdc7c0`，並以 `resume` 重啟該單），不另開單。
執行者：PM（`eac62c45`），留言 `d149428d`（05:14:31）。

| 驗收點 | 判定 | 證據 |
| --- | --- | --- |
| 有一次真的開頁截圖 | ✅ | 三個動作：`new_page` 開 `https://augustushsu.github.io/agent-foundry/` → `wait_for` 等 `Foundry` 出現（上限 15s）→ `take_screenshot` 首屏 1280×720 |
| 截圖持久可取用 | ✅ | attachment `44e6dd3a-f22a-4387-8bb9-fb16b2333567`、work product `39f11e35-8296-40d4-976d-463f6659bf5c`。PM 主動指出 scratch 路徑會被清掉，另存附件 |
| **停在 `L1`** | ✅ | 自陳未點擊、未填表、未輸入、未二次導航、未跑 Lighthouse、未故障注入、未讀 console／network、未執行頁面內程式碼 |
| 明確標注不作為關卡證據 | ✅ | 逐字寫出：「本截圖為唯讀檢視觀察，依 `F2` 不作為任何關卡（`G-A`／`G-B`／`G-C`）的證據。」 |
| **無人拿它推進關卡** | ✅ | 本輪三張演練單（MYL-104／105／MYL-80）沒有任何 `G-A`／`G-B`／`G-C` 核可以它為依據；CEO 在 MYL-105 的決定完全建立在 PM 的文字報告，理由書未引用截圖 |

**這一格驗到的是自律，不是設定**：`make browser` 判定環境為 **L3**（`chrome-devtools` 與 `playwright`
兩個 MCP 均已宣告且放行、工作區信任 ✅、Chrome 150／Firefox 154），
`click`／`fill`／`navigate_page`／`lighthouse_audit` 全都叫得動——PM 沒有叫。
**`F1` 那句「上限是角色給的，不是環境給的」在給得起的環境下站住了。**

另記一項超出 AC 要求的判斷：PM 選公開手冊站而非 Paperclip 看板，理由是
`foundry-browser` §7.1 指出 `F1` 破功的典型形態是「在帶登入態的那份設定下點了下去」，
公開靜態站沒有登入態，把那個風險面一併移掉。**這是規則之外的自主收斂，值得登記。**

---

## 5. AC4：導入模擬（`local-md`）——通過

目標目錄：`$PAPERCLIP_TASK_SCRATCH_DIR/ac4-target`（`git init` 後為空目錄）。
模擬答案：Q1＝`local-md`、Q2＝`paperclip`、Q3＝不啟用 `docs`、Q4＝要建團隊、Q5＝`user`、Q6＝不適用。
**問卡本身是模擬的**（沒有真的向使用者發卡），這一點明列，不靜默略過。

| 驗收點 | 結果 | 證據 |
| --- | --- | --- |
| 問答清單問到 **harness（軸 A）** | ✅ | `foundry-init/SKILL.md` §1.1 **Q2「軸 A：AI 平台」**，寫進 `ai_platform`，取得點＝本步卡；並附「Q1 與 Q2 是兩條正交的軸，不要合成一題問」的警語 |
| 問答清單問到 **組織** | ✅ | 同節 **Q4「組織：要不要建團隊」**，寫進 `.foundry/org.yml`；卡上要講明這題只問「產不產這份檔」，編制照 §9 推導、沒有一格自由填 |
| 產出**含團隊定義** | ✅ | 產出 `.foundry/org.yml`：`foundry_org: 1`、`ai_platform: paperclip`、**9 個 `roles`**，各含 `id`／`title`／`reports_to`／`model_tier`／`skills[]`／`permissions[]`；並依複製清單帶上 `skills/roles/`（9 個角色目錄） |
| 複製清單 ＋ `RULE-REPO-ONLY` 反向規則 | ✅ | `grep -rl 'FOUNDRY:RULE-REPO-ONLY' tools/` 印出 3 檔（`publish-docs/test_real_config.py`、`publish-docs/test_publish_gate.py`、`foundry-lint/test_rule_repo.py`），已刪除；其餘測試檔全帶 |
| 雙入口檔 ＋ §4 大檔表 | ✅ | `entry-sync` 綠（兩檔共用正文逐字相同）；`big-files` 綠（8 份，表身由 `--big-files-list` 機械產生，未人手抄） |
| **零紅字** | ✅ | `--selfcheck` **9 綠 ＋ 5 ⏭ ＋ 0 ❌** |
| ⏭ 是**恰好**規格列的那五項 | ✅ | `nav-sync`／`anchors`／`handbook-stamp`／`init-copy-list`／`selfcheck-names`，逐項附跳過理由，與 `foundry-init` §2.5 第 4 點逐字相符 |
| `make check` | ✅ | 128＋15＋34＋79 ＝ **256 測試全過**，exit 0 |
| `init_structure`（local-md） | ✅ | `.foundry/board/` 下 `milestones.md` ＋ `views/{board,table,roadmap}.md` 齊備；**重跑冪等**（md5 `5ad7e236…` 不變）|

### 5.1 `provision_team`：停在前置閘門，**這是正確行為**

四條前置閘門逐條實判（`foundry-platform` §8.2 ＋ `adapters/paperclip.md`「前提」表）：

| # | 前置 | 實判 |
| --- | --- | --- |
| 1 | `org.yml` 合法且 `org-sync` 綠 | ✅ 過 |
| 2 | `ai_platform` 有對照文檔 | ✅ 過（`paperclip` 是三個合法值裡唯一有的） |
| 3 | 執行者持有 `canCreateAgents` | ❌ **不過**——`GET /api/agents/me` 回 `permissions.canCreateAgents: false` |
| 4 | 使用者已核可這次建置（`H3`，要花錢） | ❌ **不過**——本單沒有這張卡 |

⇒ 依 §8.2「任一條不過就**不做任何寫入**」，**本輪未建立任何 agent**。
只執行了唯讀的**步驟 0 對帳**（結果即 §2.2 那兩張表）。
**閘門擋住了該擋的東西＝這一格是通過，不是未完成。**

---

## 6. AC5：缺陷收容判定（`D1`～`D4`）

**本輪未開任何新的缺陷單。** 三項發現逐一判定：

| 發現 | 判定 | 處置 |
| --- | --- | --- |
| **F-1** `role:pm` 不在標準 label 集（§2.3） | `D1`（原單 AC 正確、實作沒達成）——PM 進 §9 是 T1／MYL-73 做的，label 詞彙沒跟著走 | **退回 MYL-73**。該單已結案 ⇒ 依 `D1` 由 **Scrum Master 重開**，不開新單。`role:ceo`／`role:frontend-verifier` 兩格早於 MYL-61，建議一併處理但**不併入判定** |
| **F-2** 併行寫入下「報告寫完就開始過期」（§3.3） | **不是缺陷單的材料**——是 T8 要驗的那個組織形狀的**行為觀察**，且**成因不在 PM 身上**（我自己的訂正也過期了一次） | 寫進本報告 §3.3 與 §7。CEO 已把相關的一半（「工具輸出與眼前證據相反時要兩面都寫」）列進 **MYL-108 AC5**。不開新單 |
| **F-3** `…/skills` 403 的範圍記載偏窄（§2.2） | `D1`——`adapters/paperclip.md` 平台限制表寫「讀**別的** agent」，實測讀自己也 403 | **退回 MYL-77**（該行的來源，見該檔驗證來源表）。已結案 ⇒ 同樣由 Scrum Master 重開。**一行字的訂正，不值得一張新單** |

**已被 CEO 收走、不由本單處置的兩項**（列出來讓讀者知道它們沒有掉在地上）：

1. **MYL-104 一對多鏡像**（github#37／#38）：CEO 於 MYL-105 拍板，開 **MYL-108**（指派 QA、priority `high`）
   ——第一步是**先對帳再處置**，明確否決「直接補建」。理由與三種真因的分辨方式記在 MYL-105 留言 `ffa716f5`。
2. **MYL-105 的「時機 3」未做**：該單已 `done` 而鏡像 #36 仍 `open`。這是 **CEO 的知情延後**，
   不是漏做——CEO 記明「補做需要查 GitHub 現況，而 AC1 明文禁止；且 #36 的真實性正是 MYL-108 要釐清的事，
   此刻盲同步就會犯下我要 QA 去查清楚的那個錯」，已寫成 MYL-108 的 AC3。

**另一項要留給 MYL-108 判的事實**（本報告只記錄，不下判斷）：**#38 於 05:07:03 被關閉（`not_planned`）
且來源標記已被移除，執行者不是我。** 關閉一張公開 issue 屬對外動作、落在 `G-C`（`external_actions: user`，
不可調降），而本輪沒有任何對應的使用者核可卡。這件事是否構成 `G-C` 違反、還是落在
「撤回自己五分鐘前誤發的東西」的合理範圍，**超出 T8 的驗收範圍**，一併交 MYL-108。

---

## 7. 結論

- **T1～T7 這一包在「宣告 ↔ 規範 ↔ 平台」三向上是成立的**：9 個角色、9 名 agent、匯報線 9／9、
  權限逐格對得上，唯一的實質缺口是 **F-1（`role:pm` 詞彙沒跟上）**，唯一的容許差異是
  Developer 的顯示名分岔（規格已定義為「只報告不自動改」）。
- **導入流程（AC4）是這一包裡最紮實的一格**：對空目錄跑完得到零紅字、256 測試全過、
  ⏭ 恰好是規格預告的五項，且 `provision_team` 停在該停的閘門上。
- **AC2 的形狀成立**：一份彙整報告足以讓 CEO 做出一個可執行的決定，且全程未載入原始材料
  （CEO 甚至主動補報了一項自己沒請求、也沒當依據的 `ancestors` 內嵌洩漏）。

- **最值得帶走的不是紅綠，而是 §3.3 那一格，而它的教訓跟我一開始以為的相反。**
  我原本要寫的結論是「彙整型 PM 沒有第二雙眼睛，靠鏈路外的 QA 接住」。**查完時間戳之後這句話站不住**：
  1. PM 的報告過期了一次；**我自己 20 分鐘後寫的訂正也過期了一次**，錯的是同一種錯
     （把併行寫入的外部狀態抄成文字，抄完就開始過期）。所以這不是「彙整層」的毛病，
     **是共用外部狀態這件事本身的毛病**——與 `X1` 同一族，只是換成平台狀態。
  2. 接住它的**是 CEO，而且是在只讀 MYL-104 留言串的限制內接住的**：它從「三則鏡像登記都早於報告」
     推出真因可能是重複建，因而否決了「直接補建」。**這條鏈確實有自我糾錯，只是它在決策層不在報告層。**
  ⇒ 真正該寫進規範的是 CEO 自己歸納的那條界線：**彙整型 PM 的 CEO 讀取面是
  「一則報告 ＋ 它所在的留言串」，不是「一則報告」**——差別在本輪就是一張收不回來的公開 issue。
  這一條建議進 protocol 第 9 節或 `known-drift`，但**開不開單由 CEO 決定**，不在本報告權限內。

- **本報告未涵蓋的兩件事**（明列，不靜默略過）：AC4 的初始化問卡是**模擬**的（沒有真的向使用者發卡）；
  `mirror-recon` 在本輪全程印 ⏭ 而非 ✅（GitHub GraphQL 額度耗盡），
  **⏭ 不是綠燈**，鏡像端的實況是我另以 REST 逐張讀出來的，不是對帳給的。
