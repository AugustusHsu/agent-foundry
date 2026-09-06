# MYL-80 T8 端到端驗收報告：組織重新規劃（MYL-61 整包）

- **被驗範圍**：MYL-61 底下 T1～T7（MYL-73／74／75／76／77／78／79，另含 T9＝MYL-82）
- **驗收人**：QA Engineer（agent `14732ae9`）
- **執行 run**：`7f0e20ae-dd23-4dc4-8966-12cc2c1670c0`
- **基準 commit**：`130bbd3`（main，2026-09-06）
- **結論**：**條件通過**——五條 AC 有三條通過、一條通過但附一項不合格發現、一條進行中。詳見 §1 對照表與 §7 結論。

> **本報告的立場**：T8 的目的是驗「這一整包真的成立」，不是複述各單自己的結論。
> 因此本報告引用的每一格證據都是**本輪重新讀出來的現值**，不是引述前面幾張單的宣稱。
> 引述性的內容一律標明「引述」。

---

## 1. AC 對照表

| # | AC | 判定 | 證據指標 |
| --- | --- | --- | --- |
| AC1 | `org-sync` 綠：`.foundry/org.yml` ↔ protocol §9／§8 ↔ 平台實況三者一致 | ⚠️ **通過，但發現一項三方不一致（F-1）** | §2 |
| AC2 | PM 產狀態報告 → CEO 只讀報告做一個決定，全程 CEO 未載入原始材料 | 🔄 **進行中**（PM 側已完成並發現 F-2；CEO 側 MYL-105 執行中） | §3 |
| AC3 | 唯讀檢視模式：CEO 或 PM 開一次頁面截圖，標注「不作為關卡證據」，且無人拿它推進關卡 | 🔄 **進行中**（已併為 MYL-104 AC5，由 PM 執行） | §4 |
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

### 3.2 F-2：PM 報告的第三節建立在一次過期讀取上

- 報告第三節斷言「MYL-104 與 MYL-105 在鏡像端找不到對應 issue」。
- **實況**（我於 05:12 逐張讀 body 首行核對）：github#37 於 05:04:40、#38 於 05:05:07、#36 於 05:03:5x 建立，
  三張都存在。PM 的 `gh issue list` 應落在 05:04:30 前後，早於 #37／#38。
- **不是編造，是時間差**——但後果是實質的：**照報告的 A／B／C 任一選項動手，會再建出第三、第四張重複鏡像。**
- **這正是 protocol §8 把 PM 從低層改判到中層時寫下的那個失效模式的真實樣本**：
  彙整型 PM 的整個目的是讓 CEO 不再讀原始材料，而那**同時拆掉了 CEO 這一側的錯誤偵測路徑**。
  本輪之所以沒有釀成後果，靠的是 **QA 從外側注入了一則訂正**（MYL-104／MYL-105 各一則，05:12），
  不是這個組織形狀自己接住的。
- ⇒ **這是 AC2 最重要的一項發現**：形狀跑得起來，但**單靠這條鏈沒有第二雙眼睛**。

### 3.3 待補（下一輪）

CEO 側 MYL-105 的三項證據還沒讀得到：(a) 做了什麼決定、(b) 本輪讀了哪些東西的逐項清單、
(c) 有沒有載入原始材料的明確聲明。**本報告不預寫這一格**，讀到再填。

---

## 4. AC3：唯讀檢視模式

- **執行者必須是 CEO 或 PM**：protocol `F1` 是**列舉**不是通則，QA 自己截圖不算數。
  因此併入 MYL-104 作 AC5（留言 `fccdc7c0` ＋ 重啟留言），不另開單。
- **環境等級已判定**：`make browser` ⇒ **L3**（`chrome-devtools` 與 `playwright` 兩個 MCP 均已宣告且放行、
  工作區信任 ✅、Chrome 150／Firefox 154）。
- ⇒ 本格要驗的正是 **`F1` 那句「上限是角色給的，不是環境給的」**：環境給得起 L3 時，角色自律停不停得在 L1。
- 「無人拿它推進關卡」這一半在收到截圖後核對；本報告不預先宣告通過。

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
| **F-2** PM 報告第三節建立在過期讀取（§3.2） | **不是缺陷單的材料**——它是 T8 要驗的那個組織形狀的**行為觀察** | 寫進本報告 §3.2 與 §7；已在 MYL-104／MYL-105 各留一則訂正止血。不開單 |
| **F-3** `…/skills` 403 的範圍記載偏窄（§2.2） | `D1`——`adapters/paperclip.md` 平台限制表寫「讀**別的** agent」，實測讀自己也 403 | **退回 MYL-77**（該行的來源，見該檔驗證來源表）。已結案 ⇒ 同樣由 Scrum Master 重開。**一行字的訂正，不值得一張新單** |

另有一項**不是本輪新發現、也不歸本單**：MYL-104 一對多鏡像（github#37／#38）。
關閉多餘的那張屬對外動作、落在 `G-C`（`external_actions: user`，不可調降），
**已交由 CEO 在 MYL-105 上發卡給使用者**，不由 agent 自行處置。

---

## 7. 結論

- **T1～T7 這一包在「宣告 ↔ 規範 ↔ 平台」三向上是成立的**：9 個角色、9 名 agent、匯報線 9／9、
  權限逐格對得上，唯一的實質缺口是 **F-1（`role:pm` 詞彙沒跟上）**，唯一的容許差異是
  Developer 的顯示名分岔（規格已定義為「只報告不自動改」）。
- **導入流程（AC4）是這一包裡最紮實的一格**：對空目錄跑完得到零紅字、256 測試全過、
  ⏭ 恰好是規格預告的五項，且 `provision_team` 停在該停的閘門上。
- **最值得帶走的不是紅綠，而是 §3.2**：彙整型 PM 的鏈路**跑得起來，但沒有內建第二雙眼睛**。
  本輪 PM 的報告在形式上完全合格——自足、給恰好一個決策、選項有取捨、明講不自行組合——
  而它第三節的事實是錯的，且**錯得完全看不出來**。接住它的是鏈路外的 QA，不是鏈路本身。
  這一格建議進 `docs/standards/known-drift.md` 或 protocol，但**開不開單由 CEO 決定**，
  不在本報告的權限內。
