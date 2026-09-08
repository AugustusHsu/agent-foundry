# 審查報告：MYL-121 規範同步：handbook-version-tags 永久 Disabled 之後，七處敘述與現況不符

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-121 |
| 分支 | `MYL-121-ruleset-disabled-sync` |
| 審查範圍 | `main..HEAD` ＝ `df08d1a` 單顆；5 檔 8＋／8－ |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-08 |

## 0. 機械層（第 1 層，先跑）

| 指令 | 結果 |
| --- | --- |
| `make check` | ✅ 19 項自檢全綠；測試 376＋84＋34＋107 全 OK |
| `git diff --name-only main...HEAD` | ✅ 只有 5 檔，全在本單範圍內，無夾帶別單檔案 |
| `git log --oneline main..HEAD` | ✅ 單顆 `df08d1a`，gitmoji ＋繁體中文標題 |
| `git merge-base --is-ancestor main HEAD` | ✅ 基底不落後；且 `local main == origin/main == ae439be` |
| `git rev-parse origin/<branch>` vs `HEAD` | ✅ 同為 `df08d1a9c34e…`，推送確實落地 |

機械層全過，進第 3 層。

## 1. AC 逐條核對

證據一律自己重跑／自己讀原始檔，不採信交付回報的宣稱。

| AC | 結果 | 證據 |
| --- | --- | --- |
| **前提**：敘述所描述的狀態必須已成真（本單 blocker MYL-120 的理由） | ✅ | `gh api repos/:owner/:repo/rulesets/22327706` 實測 `enforcement: "disabled"`、`updated_at: 2026-09-08T09:47:33.399+08:00`。commit 的 author date 是 `2026-09-08 10:29:52 +0800`，**晚於使用者的切換 42 分鐘** ⇒ 改的不是還沒發生的事 |
| **AC1** 把七處改成與現況一致 | ✅ | 七處逐一讀 diff 核對：protocol `:412`（§7 第五步）、`:429`（`V1` 例外第 2 項義務）、`:439`（違反段 enforcement ＋兩項實益 ＋`V3` 半格前擋，即單上第 3、4 項同段兩處）、手冊 `03:86`、`04:59`＋`:60`、`07:101`。另加 `known-drift` `L22`。合計 8 行，與 8＋／8－ 相符 |
| **AC1 判準**：`L22` 核心推導仍成立、仍要留著，不得把提到 ruleset 的字都刪掉 | ✅ | `known-drift.md:42` 逐字比對：「以 actor 為單位的限制在本 repo 結構上無解」整段推導、`owner.type: User` 三種 actor、兩種極端、與 `R5` 同根那句，全數原樣保留。新增的第二次裁定放在格末，且明寫「**不變的是這條的核心推導**……重新啟用也拿不回『限制身分』」 |
| **AC2** 誠實記錄失去的三件事，寫明而非靜靜刪掉 | ✅ | `protocol:439` 以 ①②③ 三個行內標號逐項列出（防誤推／留痕／`V3` 半格前擋），並以「⚠️ **關掉它失去的是三件具體的東西，這裡誠實記帳、不靜靜刪掉**」起頭。手冊 `07:101` 同樣列滿三項；`04:59` 列使用者面相關的兩項並補「**完全靠自律**，沒有任何機械後盾」。**我另行獨立查證這三項損失是真的沒有被別的閘門補上**，見下節「正確性」 |
| **AC3** `V1` 標記維持 `【自律】`，但理由要跟著改字 | ✅ | `protocol:439` 明寫「`V1` 的標記**維持 `【自律】`，但理由整條換過、不是同一句話**」，並把舊理由（有墊子但分不出身分）與新理由（連那塊速度墊都關了）並列，末尾補「讀到這裡不要以為還剩一道 guard」。行尾標記仍為 `【自律】`＋`【機械】`，`rule-marks` 綠 |
| **AC4** 走完手冊發佈四步 | ⏳ **結構上後置，不列入本次 APPROVED** | 四步以「合併進 main」起頭，合併在 APPROVED 之後才發生（MYL-117／128／139 同一序）。`protocol:348` 定義的「分支收尾」是分支衛生，本單已滿足（見第 5 節）。**APPROVED 不等於 AC4 已達成**——交接事項見第 5 節 |
| **AC4 附帶**：`handbook-stamp` 閘門 | ✅ | 交付**刻意不推四章戳記**，理由正確。我從實作確認而非採信說法：`foundry_lint.py:1948` `unsynced_protocol_commits()` 的 docstring 明文——「戳記之後的每一顆 protocol 改動都要有手冊變更同行，於是『protocol 與手冊一起改』的那顆自然算已同步，**不必再補一顆戳記 commit 去指它**」。並以反向突變實證閘門是活的，見下節 |

## 2. 四維檢查

### 正確性

**無重大發現。** 三項獨立查證：

1. **`L22` 第二次裁定的每個欄位都與 API 實測逐項吻合**——`enforcement: disabled`、`updated_at` 到毫秒完全相同、id `22327706` 仍在、`bypass_actors: []`、`conditions.ref_name.include: ["refs/tags/handbook-v*"]`、`rules` 只有 `{"type":"creation"}`。文件寫「ruleset 物件**未刪除**、隨時可切回」屬實。格末「**查現值不要引用本格**，實測跑 `gh api`」這句是對的做法。

2. **AC2 ① 宣稱的「誤推會直接觸發 CI 建站」，我追到 CI 尾端確認損失是真的**。`.github/workflows/publish-handbook-site.yml:18` 的 `tags: ['handbook-v*']` 會觸發；`gate` job 過 `decide` 與 `check-version`（`V3`）；`deploy` job 執行 `scripts/publish-site.sh`，該腳本 `:60` 引入 `scripts/lib/publish-gate.sh`（證據閘門）、`:85` 才 `mike deploy`。**關鍵在於證據閘門驗的是「這份手冊有沒有 APPROVED 記錄」，而不是「使用者是否有意發這個版本號」**（`publish-gate.sh:73` 判 `verdict == 'APPROVED'`）——所以一個殘留的本地 `handbook-v*` tag 只要剛好指在已核可的手冊狀態上，就會**整條通過並上站**。既有閘門確實沒有補上 ruleset 讓出的那個洞，AC2 ① 的宣稱在最可能的誤推情境下成立。

3. **反向突變：`handbook-stamp` 對這個交付形狀不是空過的**。在 `PAPERCLIP_RUN_SCRATCH_DIR` 的 `clone --shared` 上做，未動共用 workspace（`X1`）：
   - 對照組（`df08d1a` 原樣）→ `✅ [handbook-stamp]`
   - 突變（同一顆 commit 只取 protocol ＋ `known-drift`，手冊完全不跟）→ **`❌ [handbook-stamp]`，`--selfcheck` rc=1**

   附一則過程教訓，也是這次突變台自己的對照組救回來的：第一次我把手冊還原做成**分支上的另一顆 commit**，閘門仍綠——因為它是**逐 commit** 判「這顆動了 protocol 有沒有同顆動手冊」。那次的綠燈是探針沒打中，不是閘門壞了。

### 規格符合度

**無偏離。** 本單改的是規範文本自身，對照基準即工單 AC 與現況；七處與 AC 的對應已逐條列在第 1 節。`L22` 的兩次裁定按時間序並置（`2026-09-05 MYL-62` 記 `active` 為當時落地值、`2026-09-08 MYL-61` 記改為 `disabled`），是歷史紀錄的正確寫法，不是自相矛盾。

### 安全性

**無發現。** 無程式碼變更、無機敏資料。新增內容（ruleset 名稱、id、`GH013` 錯誤碼、Settings 路徑）在 `docs/publish-reviews/MYL-62.md`、`MYL-68.md`、`MYL-71.md` 已判定可公開並已發佈過，本次未擴大公開面。

值得記一筆的是本單**降低**了一項安全保證而非提高：`V1` 這一格現在零機械後盾。交付沒有掩飾這件事，這正是 AC2 要的。

### 可維護性

**無重大負擔。** 一項觀察見次要建議 2。

## 3. 重大瑕疵清單

**無。**

## 4. 次要建議

**均不擋結案，Developer 自行決定。**

1. **完整性掃描的範圍建議含 `tools/`／`scripts/`**。我用 18 個不同措辭做了兩輪獨立掃描（`git grep` 天然排除未追蹤的 `worktrees/`，不必手動濾），掃出一處交付回報未提及的命中：`tools/publish-docs/site_docs.py:239`「根治手段是 tag ruleset（需要使用者權限）」。**我判它不需要改**——它是**規範性**敘述（要補這個缺口該用什麼手段），不是**描述性**敘述（ruleset 現在是開的），而 ruleset 物件仍在、隨時可啟用，所以這句話仍然成立；且它的交叉引用「見 protocol `V3` 的『違反』段」指向的正是本次已更新的 `:439`，讀者跟著跳會拿到現值。結論相同，但這次是我掃到的不是你掃到的——下次把 `tools/`／`scripts/` 納入掃描範圍，成本很低。

2. **`protocol:429` 的「三項義務」與改寫後的第 (2) 項略有張力**。第 (2) 項現在是「**不必**提醒使用者切回 `active`……但**切換 ruleset 本身仍是使用者專屬、agent 一律不代勞**」——前半取消義務、後半保留禁令。讀起來仍成立（禁令也是一種義務），但「三項義務」的計數與「不必」的開頭會讓快讀的人以為第 2 項作廢。若日後有機會再動這一段，把它改寫成「(2) 不得代勞切換 ruleset（原『提醒切回 `active`』一項已隨永久 Disabled 取消）」會更難誤讀。**本次不必為此退回。**

3. **`handbook-stamp` 的逐 commit 粒度有一個既有盲點**（非本單引入，也非本單責任）：同一分支上若在後續 commit 還原手冊變更，閘門看不到——這是我上面那次失敗突變的副產品實測。工具 docstring 已自陳採逐 commit 是刻意設計（並明列 evil merge 為已知代價），所以這可能是有意識的取捨。**依角色 skill 我不把新需求夾帶進放行條件**，僅在此登記，是否值得開單請 Product Manager 判。

## 5. 分支收尾檢查

- **分支狀態：待合併**。`HEAD` ＝ `origin/MYL-121-ruleset-disabled-sync` ＝ `df08d1a9c34e…`，已推送、無未推提交、工作區無已追蹤檔修改（`git status --porcelain` 僅三筆未追蹤：`.codex/`、`myl69-repo-viewport.png`、`worktrees/`，皆非本單產物）。基底 `main` 為最新且 `local main == origin/main`。Code Reviewer 不執行合併。

- **合併者（Tech Lead）的接續義務**：

  1. **AC4 手冊發佈四步**（protocol 第 7 節）——合併進 main → 用 `templates/publish-review.md` 寫審查記錄 → commit → `scripts/publish-wiki.sh` 同步主閱讀面。P2 常設授權、無使用者介入點。
     ⚠️ `handbook_commit` **每次實跑 `git log -1 --format=%H -- docs/handbook` 取值，不要照抄前一單的形狀**——MYL-117 那次是合併 commit 自己、MYL-139 那次是分支側的那顆，兩個方向都出現過。
  2. **鏡像結案**：合併並結案時把 GitHub 鏡像 issue 一併 close ＋ Status 設 `Done`，否則 `mirror-recon` 立刻轉紅並擋住全 workspace 的 commit。
  3. **第五步（打 `handbook-v1.0.0.0` tag 發精裝站）不是本單結案條件**，屬 MYL-120 且 `V1` 讓它專屬使用者。⚠️ 提醒：本次交付把「防誤推」這道保護移除的效果，從合併那一刻起就生效了。

- **本次一併裁定的爭點（Tech Lead 在交付留言第 3 節提交）**：
  `docs/features/cross-platform/review-report-MYL-82.md:122` 提及「切 Disabled、推完切回 Active」而未修改——**我同意這不是第八處，維持不動**。三條理由我逐條查證屬實：該檔 `:129` 確為 `**✅ APPROVED**`（已簽署的審查記錄，MYL-74 立過合併者不單方面編輯）；該句所在的第 5 節**整節都已過期**，同節 `:114` 仍寫「分支狀態：**待合併**，`HEAD` ＝ `475d130`」、`:120` 仍寫「鏡像 github#18 現況 OPEN」，只訂正其中一句會讓一份時間點一致的快照變成內部自相矛盾；`docs/features/` 不投影到公開面。判尺沿用 MYL-122——要訂正的是「複述權威的活文件」，不是有時間戳的快照。同理，`docs/publish-reviews/MYL-62.md`／`MYL-68.md`／`MYL-71.md` 三處綁 sha 的證據記錄維持不動亦正確。

## Verdict

**✅ APPROVED**
