# 審查報告：MYL-139 SM 退場已在平台側完成 ⇒ 規範側三處敘述過期（protocol 那句「全程可逆」實為不可逆）

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-139 |
| 分支 | `MYL-139-sm-exit-sync` |
| 審查範圍 | `cc9a15e..702216e`（單一 commit，4 檔 +18/-8） |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-08 |

本輪為第 1 輪。交付物訂正的是**會被當權威引用的源碼行號**，因此第 3 層的重點放在
「搬運忠實度」——`L35` 與 protocol 裡每一個行號、每一句全集宣稱，都在平台實跑樹上
重新開檔對過，**不沿用交付回報第 4 節那張查證表**。

**驗明正身**（照 `L32` 的取證法自行重跑，不採信交付回報的轉述）：
`ss -lptn 'sport = :3100'` → pid 1355907 → `ps -eo pid,args` ＝
`/home/augustushsu/.paperclip/cli/current/node_modules/paperclipai/dist/index.js run --instance default`，
而 `cli/current` 為符號連結 → `installs/npm/2026.831.1`。以下行號全部取自該樹的
`@paperclipai/server/dist`。

## 0. 機械層（第 1／2 層）

| 項目 | 指令 | 結果 |
| --- | --- | --- |
| 規範自檢＋測試 | `make check` | **rc 0**；19 項自檢全綠，測試 **376 / 84 / 34 / 107** 全 OK |
| 分支只含本單變更 | `git diff --name-only main...HEAD` | 4 檔，全在單上射程內：`.foundry/org.yml`、`docs/handbook/06-org-structure.md`、`docs/standards/known-drift.md`、`skills/foundry-protocol/SKILL.md` |
| commit 訊息形狀 | `git log --oneline main..HEAD` | 單一 commit，gitmoji ＋繁體中文標題 |
| 基底 | `git merge-base --is-ancestor main HEAD` | main 是 HEAD 祖先，基底不落後 |

機械層全過，進第 3 層。

## 1. AC 逐條核對

| AC | 結果 | 證據 |
| --- | --- | --- |
| **1** 三處敘述與 2026-09-08 事實相符；「不可逆」附得出源碼依據（不是轉述本單） | ✅ | 三處全改，另加第四處 `L35`。**行號逐條自行覆核**：`terminate` 起始 `:714`、`status: "terminated"` `:721`、API key `revokedAt` `:728`–`:731`（`sed -n '710,733p'` 逐行數到）；四道守衛 `grep -n 'terminated' services/agents.js` ⇒ `:646` pause／`:666` resume／`:689` clearError／`:463` updateAgent 全部命中，且 `:463` 的字串逐字為 `Terminated agents cannot be resumed`，與 `L35` 引用相符。名冊濾除 `:572` `if (!options?.includeTerminated)` ＋ `:573` `conditions.push(ne(agents.status, "terminated"))`，與「沒帶 `includeTerminated` 時濾掉」的敘述相符 |
| **2** 動 protocol ⇒ 依 MYL-44 同步手冊戳記，`make check` 全綠 | ✅ | `make check` 我自己跑過 rc 0（見上表），`handbook-stamp` 綠、報 `protocol 最新 702216e`。**「不推戳記」是正確判斷而非疏漏**：`unsynced_protocol_commits()`（`tools/foundry-lint/foundry_lint.py:1948`）docstring `:1951`–`:1954` 明寫判準是「戳記之後每顆 protocol 改動都要有手冊變更同行」，並言明「protocol 與手冊一起改的那顆自然算已同步，不必再補一顆戳記 commit 去指它」 |
| **3** 動 `docs/handbook/` ⇒ 走完手冊發佈四步 | ⏳ **未完成，且順序上不可能在本輪完成** | 四步的第一步是「合併進 main」（protocol `:408`），而合併發生在 APPROVED 之後。protocol `:138` 把四步定為**結案**條件而非審查條件。⇒ 不構成瑕疵，但**仍是 Tech Lead 在合併後的未了義務**，於結案時檢查（見 §5） |
| **4** `org.yml` 只動註解行，`git diff` 自證 | ✅ | 不只複跑，**另做反向突變證明管線活著**（見 §2 正確性）：乾淨態空輸出、往非註解行塞一格後管線立刻吐出 `-foundry_org: 1` / `+foundry_org: 1_MUTANT` |

## 2. 四維檢查

- **正確性**：無重大發現。三項高風險宣稱逐一打靶：
  1. **全集宣稱「全檔四個寫入語句無一寫 `agents`」**——這是 `L35` 裡最脆的一句（漏數一個就從強證據變成錯的）。用 Python 掃全檔 388 行的 `.update(`／`.insert(`／`.delete(` ⇒ **恰好 4 個命中**：`:188` `insert(projectMemberships)`、`:263` `insert(agentMemberships)`、`:327` `insert(documentMemberships)`、`:371` `delete(documentMemberships)`，**無一寫 `agents`**。宣稱成立。（刻意用 Python 數而非 `grep -c`：本機 `grep` 是 ugrep，計數行為有已知假陽性。）
  2. **AC4 自證管線**——依 `L33` 的教訓（綠燈比沉默危險）做對照組／突變組配對。⚠️ 我第一次的突變測試**設計錯了**：對工作樹改動，卻用 `cc9a15e..HEAD` 這個**純 commit 區間**的 diff 去看，工作樹變更根本不進那個 diff，於是「沒出聲」不代表管線壞，只代表探針沒打到靶。改成 `git diff --unified=0 cc9a15e -- .foundry/org.yml`（含工作樹）後：乾淨態空、突變態出聲 ⇒ 管線確實擋得住非註解變更，AC4 的「空輸出」是真綠燈。
  3. **`Leave agent` 不動 agent**——路由 `routes/resource-memberships.js:75` 確為 `router.put("/companies/:companyId/resource-memberships/me/agents/:agentId", …)`，`:78` `requireBoardUserId(req, res)` 取的是呼叫者自己；服務層 `updateAgent`（`:219`）讀 `agents` 僅為存在性驗證（`:220`–`:224`），`:223` 對 `terminated` 直接 `throw notFound("Agent not found")`。UI 側另行覆核：bundle `ui-dist/assets/index-BHbrFFmp.js` 內 ``updateAgent:(e,t,n)=>ue.put(`/companies/${e}/resource-memberships/me/agents/${t}`,n)`` 逐字命中，`Leave agent` 字樣 1 次、`hideTerminate`／`onTerminateSuccess` 各 2 次 ⇒ 兩顆鈕確為不同呼叫。
  4. **「只有使用者按得動、agent 不得代按」**——這句同時出現在手冊與 `L35`，是給使用者的行為指示，值得單獨驗：`routes/agents.js:3416` `router.post("/agents/:id/terminate", …)` 的**下一行 `:3417` 就是 `assertBoard(req)`** ⇒ agent 身分在路由第一道即被擋，宣稱結構上成立。
- **規格符合度**：無偏離。單上 Inputs 給的行號（`:642`／`:662`／`:714`／`:463`）與交付物採用的守衛行（`:646`／`:666`／`:689`／`:463`）**兩者都對、但指的東西不同**——前者是函式起始行、後者是 `if` 守衛行。交付物選守衛行是對的：守衛行才是「不可逆」的直接證據。此判斷已在交付回報 §2.1 主動揭露，覆核相符。另 `clearError`（`:689`）是交付方自行補上的第四道守衛，`grep` 覆核確有 `throw conflict("Cannot clear error on terminated agent")`，屬同組事實，補得正確。
- **安全性**：不適用（純文件變更，無程式碼路徑、無輸入處理、無機敏資料）。**已確認未寫入機敏資訊**：新增內容只含伺服器 `dist` 的相對路徑與行號、公開的 API 路徑形狀，以及使用者按鈕操作的時間戳；無金鑰、無 agent id 以外的識別資料。
- **可維護性**：符合 MYL-134 的分界（**事實只能一份、放 known-drift；決定貼著它拘束的那張表**）。完整源碼鏈集中在 `L35` 一處，protocol 與手冊只留結論＋指標 ⇒ 沒有製造三份會各自過期的行號拷貝，這正是本單要修的病灶本身，處置一致。`L35` 編號經**全 refs 掃描**覆核：`refs/heads` ＋ `refs/remotes` 全掃，本分支之外最大值為 **34**（`main`、`origin/main`、`origin/MYL-138-assign-gate-drift`），本分支 35 ⇒ `L34` 那個「別的分支已經用掉」的坑沒有重演；本檔 L 編號 1–35 連號無重複。

### 射程與越界宣稱檢查（交付方點名要我確認的一項）

交付方宣稱的是「`terminate` 不可逆」，不是「agent 刪不掉」。覆核：**`L35` 全文未提及 `remove`**，因此沒有越界宣稱。另實查 `remove` 為獨立的一支（起始行是 **`:734`**，不是交付回報 §5 寫的 `:733`——`:733` 是 `terminate` 的收尾 `},`），其內容是刪除而非還原，**不會削弱「不可逆」這個結論**。⇒ 射程乾淨。（該筆 off-by-one 只出現在工單留言，未進交付物。）

### 未訂正但經查屬正確的兩處

動手前先掃過全 repo 的 `.md`／`.yml`，確認「三處」是否真的窮盡：

- `docs/publish-reviews/MYL-115.md:89` 仍寫著「把 `pause`＋`leave` 解釋成兩個⋯⋯可一鍵還原的動作」。**這一處正確地不該動**：該檔 frontmatter 有 `handbook_commit: 31c5d34…`／`reviewed_at: 2026-09-06`，是綁 commit sha 的**發佈審查證據記錄**，陳述的是「該 sha 當下手冊寫了什麼」——那個陳述在當時為真。改它等於竄改證據記錄。
- `skills/roles/scrum-master/SKILL.md` 仍在 repo 內。交付回報 §2.5 判它不在射程內，**判得對，而且理由比交付方寫的更強**：它的保留是 **MYL-115 第 1 輪 §6 裁定 2 的明文裁定**（見 `docs/features/org/review-report-MYL-115.md:92`），不是無人處置的殘留。另查本樹（排除 `worktrees/`）所有引用，無任何規則層檔案把 SM 當在編角色；`tools/foundry-lint/test_foundry_lint.py:1461` 反而是斷言它**不在** `org.yml`。⇒ 不列瑕疵、也不建議在本單或新單處置。

## 3. 重大瑕疵清單

無。

## 4. 次要建議

1. **（採納交付方的編輯判斷）** `org.yml` SM 段開頭 `⚠️` → `✅`：我**支持**這個改動。`:13`–`:14` 那句「除**下方 ⚠️** 那一處刻意保留的例外（Frontend Verifier 的 `canAssignTasks`）」是以 emoji 定址的指標，實查其標的仍在（`:45`／`:50` 兩處 `⚠️` 標著 FV 那格），少一個中途的 `⚠️` 讓定址更好認，不是更差。
2. **（純可讀性，不必改）** 同一段的括號註 `:22`「這句的『只剩一項』⋯⋯」與其指涉對象（`:13`–`:14`）之間，因本次擴寫從隔 4 行變成隔 7 行。指涉仍無歧義（中間新增的 SM 段落不含「只剩一項」字樣，接不上），故不構成瑕疵；日後若該段再擴寫，可考慮把括號註改成明指「上面第 13–14 行那句」。
3. **（給下一個動 known-drift 的人）** 本輪的全 refs 編號掃描可以機械化。目前 `--selfcheck` 只驗本分支內的表格形狀，驗不到「別的分支已經用掉這個編號」——而這個坑 `L34`、`L35` 連兩張單都得靠人工掃。建議評估加一項自檢或 pre-commit 掃 `refs/remotes` 的最大 L 編號。**依角色規範，此建議不夾帶為本單需求**，交由 Product Manager 判是否開單。

## 5. 分支收尾檢查

- 分支狀態：**待合併**。`git rev-parse` 覆核本地 HEAD 與 `origin/MYL-139-sm-exit-sync` 同為 `702216e`（已推送）。
- APPROVED 後由 Tech Lead 執行，**兩項未了義務**：
  1. 合併進 main 並刪除已合併的遠端分支（`P1` 常設授權）。
  2. **AC3 手冊發佈四步**（protocol `:404`–`:412`）：合併 → 用 `templates/publish-review.md` 寫 `docs/publish-reviews/MYL-139.md` → commit 填實際 `handbook_commit` sha → `scripts/publish-wiki.sh`。屬 `P2` 常設授權、無使用者介入點。**AC3 未完成前不得結案**（protocol `:138`）。
  3. ⚠️ 提醒：`handbook_commit` 有時就是合併 commit 自己（TREESAME 判準），不要照抄別單的形狀。

## Verdict

**✅ APPROVED**

四條 AC 中三條有我自己驗過的證據，AC3 因流程順序（第一步即為合併進 main）在本輪結構上不可能完成，已列為合併後的未了義務並在 §5 指名執行者與動作。無重大瑕疵。

本輪特別確認的是**搬運忠實度**：`L35` 與 protocol 新增的每一個行號、四道守衛的字串、以及「全檔四個寫入語句」這句全集宣稱，都在實跑樹 `2026.831.1` 上重新開檔核對無誤；AC4 的自證管線另以對照組／突變組配對證明它擋得住反例，不是壞掉的綠燈。
