# 審查報告：MYL-115 X1 規範修訂：組織形狀改為 CEO → Product Manager → 團隊，含 PM 正名

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-115（審查單 MYL-122，第 2 輪／APPROVED） |
| 分支 | `feat/MYL-115-org-shape-pm-rename`，遠端 tip `31c5d34704101b5f1779fc8702e992fb2bd34d6f` |
| 審查範圍 | 第 1 輪已審 `gh/main`(`f234eb7`)`...40ddd49`（3 顆、26 檔、+301/-233）；本輪增量 `40ddd49..31c5d34`（1 顆、5 檔、+5/-5） |
| 審查者 | Code Reviewer（agent `148355fe`） |
| 日期 | 2026-09-06 |

> 審查環境：`git clone --shared` 隔離 clone ＋ `git remote add gh` 直抓 GitHub（共用 workspace 被 run
> `37ec8605`／MYL-115 佔著，HEAD 在 `main`）。隔離 clone 沒有 pre-commit hook，`make check` 自跑。
>
> **增量審查的前提已驗**：`git merge-base --is-ancestor` 逐顆確認 `316f06e`／`fc67c64`／`40ddd49`
> 三顆**都仍是 `31c5d34` 的祖先**——分支沒有被 rebase 或改寫，第 1 輪對那 26 檔的審查結論依然成立，
> 本輪因此只需審增量。`gh/main` 仍為 `f234eb7`，與第 1 輪同一基底。

## 1. AC 逐條核對

第 1 輪已逐條驗過 AC1／2／3／4／5／9，證據在 `review-report` 第 1 輪留言（MYL-115 留言
`6ade6488`）。本輪依角色規範「複審對著上一輪瑕疵清單逐項驗，不重新全面審查」，
只重跑受影響的機械項並補驗 AC6。

| AC | 結果 | 證據（本輪自跑，不採信交付回報的宣稱） |
| --- | --- | --- |
| AC1 `--selfcheck` 全綠，`org-sync`／`handbook-stamp` 明確通過（`⏭` 不算） | ✅ | 本輪自跑：**14 項 ✅ ＋ `mirror-recon` `⏭`**。`org-sync` ✅（8 名）、`handbook-stamp` ✅（protocol 最新 `316f06e`）**兩項皆非 `⏭`**，AC 字面成立。`mirror-recon` 見 §4 第 1 點 |
| AC2 `make check` 通過 | ✅ | 隔離 clone 自跑 → **exit 0**；245＋15＋34＋107 測試全 OK（log 中段的 `❌` 字樣是負面測試 fixture 的預期輸出，四段之後皆為 `OK`） |
| AC3 §9 匯報樹 ↔ `org.yml` `reports_to` ↔ §8 分層表三方一致 | ✅ | 本輪增量未動這三處任一，`org-sync` 仍 ✅。第 1 輪已做三組反向突變證明該綠不空轉 |
| AC4 §9 可查到「本次改寫依據 MYL-96」，且與 MYL-61 卡 `f80e66b3` Q1 的關係交代清楚 | ✅ | 第 1 輪驗過（`SKILL.md:541`／`:543`），本輪增量未動 protocol |
| AC5 「暫停＝加 blocker」在 §11 有穩定 ID 且標了 `【自律】`／`【機械】` | ✅ | 第 1 輪驗過（`O5`，`SKILL.md:611`／索引 `:677`）；本輪 `rule-ids`（45 個 ID）／`rule-marks`（29 行違反段）仍綠 |
| AC6 正名逐格相符；`grep -rn "roles/pm" .` 無殘留 | ✅ | **第 1 輪唯一不成立的一條，本輪達成。** 三處活文件的舊詞彙／舊數字全數修正，逐項驗收見 §3；四組獨立 sweep grep 見下方 |
| AC7 手冊發佈四步 | ⏭ | 合併後動作，**不在本單射程**（工單載明） |
| AC8 經 Code Reviewer 審查 APPROVED，報告用 `templates/review-report.md` | ✅ | 本報告即依該模板；Verdict ✅ |
| AC9 正名對帳表寫進審查報告 | ✅ | §6（第 2 輪更新版，三格由 ❌ 轉 ✅，並補入本輪新增的第 4 格） |

### AC6 的四組 sweep grep（我自己重跑，不沿用交付回報的那三行）

| # | 掃描式 | 結果 |
| --- | --- | --- |
| B | 獨立詞 `SM`（排除 `skills/roles/scrum-master/`），掃 `skills`／`docs/handbook`／`templates`／`.foundry`／`tools`／兩份入口檔 | **零命中** ✅ |
| C | `CEO 與 PM`，掃 `skills`／`docs`／`templates` | **零命中** ✅ |
| D | 寫死角色數量 `(九或9)…(角色/成員/在編)` | 只剩 `config-schema.md:262`、`adapters/paperclip.md:222` **兩處有日期（2026-09-06）且綁 MYL-79 的歷史敘述** ✅ 與 §6 判尺一致 |
| E | 獨立詞 `PM` 在全部活文件（**第 1 輪沒跑過的一組，本輪補做**） | 20 處命中，逐處判讀後**無一是漏改的活宣稱**：型態分類學術語（protocol `:529` 標題「三種 PM 型態」、`彙整型 PM`／`stream owner 型 PM`）、綁工單的歷史敘述（`config-schema.md:206`、protocol `:469`／`:503`、`paperclip.md` 四處）、刻意引述使用者原話（`06-org-structure.md:42`～`:55`「跟以前說的『不加 PM』是不是矛盾」）、以及本輪刻意新增的那一格（`03-workflow.md:9`） |

D 組那兩處與 E 組的判讀，套用的是第 1 輪 §6 定下、本輪未改的同一把尺：
**現在式的規範層宣稱要改；有日期或綁工單編號的實測／歷史紀錄不改。**

## 2. 四維檢查

- **正確性**：無發現。本輪增量是 5 行純文字替換，無程式邏輯。
- **規格符合度**：**第 1 輪的偏離已消除**。三處逐項對照我當初寫下的判準核對通過（見 §3），
  沒有出現「改了字面、判準其實沒滿足」的情形。本輪增量未動 protocol、未動 `org.yml`、
  未動 §8／§9，因此第 1 輪已確認落地的 MYL-96 裁定 #1／#2／#3／#16 不受影響。
- **安全性**：無發現。無程式邏輯、無輸入面、無機敏資料、未新增任何授權宣告。
- **可維護性**：無發現，並記兩處正面判斷：
  1. **第 4 處是他自己掃出來的，掃法也對。** 他沒有只照我給的三個行號改，而是把三項抽象成
     「一族」再各掃一次全 repo，因此多抓到 `CLAUDE.md:67`／`AGENTS.md:67`。這正是第 1 輪
     §4.2 指出的那個失效模式該有的處理方式。
  2. **「在編」不是本輪憑空造的詞。** `skills/foundry-platform/SKILL.md:43` 在 `40ddd49`
     就已寫入「八格＝foundry-protocol 第 9 節組織圖的每個在編角色」，`ai-platform:61`
     用同一個詞是**與既有用語一致**，不是各寫各的。

## 3. 重大瑕疵清單

**本輪無。** 第 1 輪三項逐項驗收如下（每一列的「判準」欄是我第 1 輪寫下的原始期望，不是事後補的）：

| # | 位置 | 我第 1 輪定的判準 | 本輪實況 | 驗收 |
| --- | --- | --- | --- | --- |
| 1 | `docs/handbook/03-workflow.md:9` | 圖上第三棒、`:5` 指向的 protocol §3、`:44` 節標題**三者講同一個角色** | 圖上第三棒 `PM`；protocol `:120` 流程鏈第三棒為「工單（**Product Manager**）」；`:44`「第 3 段：拆單（**Product Manager**）」，另 `:41`／`:46` 亦為 Product Manager。三者同指一角色 | ✅ |
| 2 | `skills/foundry-browser/SKILL.md:198` | `PM` 改 `Product Manager`，與 protocol `F1` 的列舉**逐字**一致 | `:198`「適用對象：**CEO 與 Product Manager**，就這兩個角色」；protocol `F1`（`:242`）「**CEO 與 Product Manager**（Frontend Verifier 以外……）」。列舉逐字相同 | ✅ |
| 3 | `skills/foundry-ai-platform/SKILL.md:61` | 改成不寫死數量的形狀（建議前者）或改成 8 | 改為「第 9 節組織：**各在編角色**分工」——採建議的不寫死數量 | ✅ |

補驗兩件容易被漏掉的事：

- **ASCII 圖對齊沒壞**：`SM` → `PM` 是 2 個 ASCII 字元對 2 個，`git show gh/main` 比對後
  第 8 行（`需求 ──▶ … 結案`）一字未動，第 9 行僅該 2 字元變動，欄位對齊維持。
- **戳記不需要再推**：本輪未動 protocol，protocol 最新仍是 `316f06e`，`03-workflow.md:3`
  的戳記即 `316f06e`，`handbook-stamp` ✅。方向也對——pre-commit 擋的是「改了 protocol 卻沒動手冊」，
  反方向（動手冊未動 protocol）不觸發。

### 第 4 處的射程裁定（他請我裁）

**判：在射程內，維持這一顆的兩行，不必還原。**

`CLAUDE.md:67`／`AGENTS.md:67` 原文「第 2 層：角色薄 skill（**9 個角色**）」與第 1 輪瑕疵 3
（`ai-platform:61`「九個角色分工」）**是同一族、同一個失效模式**：入口檔對組織規模的
**現在式宣稱**，被本分支從 9 改成 8 之後變成假的。我第 1 輪已把瑕疵 3 判進 AC6「正名逐格相符」，
同一把尺套到這一格就必須得到同樣的結論——**判不同會讓 AC6 的判準自相矛盾**。

他指出的歧義我也覆驗了，且比他說的更值得改：`ls skills/roles/` 實際**確有 9 個目錄**
（ceo／code-reviewer／developer／frontend-verifier／product-analyst／product-manager／
qa-engineer／**scrum-master**／tech-lead），因為 `scrum-master/` 依第 1 輪 §6 裁定 2 刻意保留。
所以「9」同時有一個為假的讀法（9 個在編角色）與一個為真但誤導的讀法（9 個目錄，把已退場角色算進來）。
改成「一個角色一份」既不寫死數量、也正確描述了目錄與角色的對應關係，是這一格的正解。

`entry-sync` ✅ 證實兩份入口檔共用正文仍逐字相同。

## 4. 次要建議

1. **`mirror-recon` 仍是 `⏭`，本輪我同樣沒能替他驗掉——處置與第 1 輪相同，不計入 Verdict。**
   本輪自跑輸出為「讀不到鏡像端：`gh issue list` 失敗：GraphQL: API rate limit already exceeded
   for user ID 22841553」，而 `gh api rate_limit` 兩桶仍顯示滿——證實爆的是 Projects v2 那個
   不在 `rate_limit` 裡的**次級限制**，是環境限制、非本分支造成，且 AC1 的字面只要求
   `org-sync`／`handbook-stamp` 非 `⏭`。**但它不是綠**：鏡像 #53 → `In Progress`／#46 → `Blocked`
   兩格仍未經全表對帳覆驗（第 1 輪我用手寫 GraphQL 只選 `number`＋`Status` 繞過限制，驗到那兩次
   `item-edit` 確實落地，但那是點驗不是對帳）。**請在 MYL-115 合併後那一輪必跑一次**，
   不要拿「`item-edit` 沒回錯誤」當它綠。他在送審留言裡主動這樣寫，判斷正確。
2. **跨檔案複述漂移的機械檢查——同意他這一輪不開單，理由成立。** 他給的理由不是射程而是
   **開單本身會製造紅燈**：`POST issues` 預設落 `backlog`（第七態），而建鏡像要走 GitHub API，
   正卡在上述次級額度上；開得出單、建不出鏡像＝`mirror-recon` 判漏建，會擋住整個 workspace 的 commit。
   這與 `known-drift` 記載的形態一致。他已把完整規格寫進 MYL-115 留言存查並回報 Product Manager，
   依角色規範（不夾帶新需求進本單）這是正確的收法。**本項不擋本單結案。**
3. **一處既有用詞差異，本輪不要求處理，也不是本分支造成的**：`03-workflow.md:8` 的圖上第三棒
   寫「拆單」，而 protocol `:120` 的同一棒寫「工單」。`git show gh/main:docs/handbook/03-workflow.md`
   比對確認第 8 行在本分支前後一字未動，屬既有差異。兩者指同一段工作、不影響角色判讀，
   列出來只是讓下一手知道我掃到了、也判過了。
4. `tools/foundry-lint/foundry_lint.py:1720` 的 docstring「AC2 要照定案組織填出 9 名，而 PM 的
   agent 要到 MYL-79（T7）才真的被建出來」——**同意他判不改**。我讀了上下文：該段在說明
   `check_org_sync` **刻意不比對平台實況**（MYL-76 AC7）的理由，敘述的是 MYL-76 當時 AC2 的要求，
   綁兩張工單編號，屬歷史敘述而非對 §9 現況的宣稱。

## 5. 分支收尾檢查

- **分支狀態**：**待合併**——本報告即為 APPROVED 的最後一件交付物，依 protocol 第 5 節
  commit 進本分支後，由 Developer 接手合併。
- **commit 訊息**：四顆皆 gitmoji ＋繁體中文標題，`31c5d34`「🐛 MYL-115 補正名殘留：活文件對權威的
  複述沒跟著改（審查第 1 輪退回）」合格。
- **未夾帶別單變更**：`git diff --name-only gh/main...31c5d34` 共 **30 個路徑**＝第 1 輪已審的 26
  ＋ 本輪首次觸及的 4（`AGENTS.md`／`CLAUDE.md`／`foundry-ai-platform/SKILL.md`／`foundry-browser/SKILL.md`）；
  `03-workflow.md` 第 1 輪即在清單內（`fc67c64` 推戳記）。30 之中含 `roles/pm/` 刪除與
  `roles/product-manager/` 新增兩側（加 `-M` 偵測改名仍為 30，內容改動幅度大到不併為一筆）。
  全部落在本單射程。本輪增量 `git diff --stat 40ddd49..31c5d34` ＝ **5 檔、+5/-5**，
  與送審回報宣稱完全相符，無夾帶。
- **已推遠端**：`gh/feat/MYL-115-org-shape-pm-rename` ＝ `31c5d34704101b5f1779fc8702e992fb2bd34d6f`。
- **合併後仍待辦（不屬本單，列此以免掉單）**：AC7 手冊發佈四步、平台側正名
  （`PATCH /api/agents/eac62c45-…`）、GitHub 鏡像端 `role:*` label 集改 8 格、`mirror-recon` 補驗。

## 6. 正名對帳表（AC9 正式版，第 2 輪更新）

第 1 輪表格中三格 ❌ 本輪已轉 ✅，並補入本輪新增的第 4 格；其餘列第 1 輪已逐格驗過，維持原判。

| 面 | 位置 | 舊 | 新 | 狀態 |
| --- | --- | --- | --- | --- |
| repo 規範 | `skills/roles/pm/` → `skills/roles/product-manager/` | 目錄 | 目錄 | ✅ 第 1 輪 |
| repo 規範 | 該檔 frontmatter `name` | `role-pm` | `role-product-manager` | ✅ 第 1 輪 |
| repo 規範 | `.foundry/org.yml` `id`／`title`／`skills[]` | `pm`／`PM`／`roles/pm/…` | `product-manager`／`Product Manager`／`roles/product-manager/…` | ✅ 第 1 輪 |
| repo 規範 | `org.yml` `reports_to`：PA／FV／TL | `ceo` | `product-manager` | ✅ 第 1 輪，三格 |
| repo 規範 | `org.yml` `scrum-master` 整段 | 存在 | 移除 | ✅ 第 1 輪 |
| repo 規範 | protocol §3 流程鏈與四處交接小節標題 | `Scrum Master` | `Product Manager` | ✅ 第 1 輪 |
| repo 規範 | protocol §5「只有 X 有權改 AC」 | `Scrum Master` | `Product Manager` | ✅ 第 1 輪 |
| repo 規範 | protocol §7／§9「巡檢兜底」四格 | `Scrum Master` | `Product Manager` | ✅ 第 1 輪，與 q2＝`pm` 相符 |
| repo 規範 | `templates/publish-review.md:12` 巡檢兜底 | `Scrum Master` | `Product Manager` | ✅ 第 1 輪，第 5 格 |
| repo 規範 | protocol §8 分層表中層／低層 | 舊兩列 | 改寫 | ✅ 第 1 輪 |
| repo 規範 | protocol §9 組織圖、三種 PM 型態表、決策權矩陣、`O5`、§11 索引 | 舊組織 | 改寫 | ✅ 第 1 輪 |
| repo 規範 | protocol `F1`／`F2` 適用對象 | `CEO 與 PM` | `CEO 與 Product Manager` | ✅ 第 1 輪，`:242`／`:247` |
| repo 規範 | 6 份角色 skill | `Scrum Master`／`PM` | `Product Manager`（成因判定改掛 `Tech Lead`） | ✅ 第 1 輪 |
| repo 規範 | `templates/hld.md:4` 讀者 | `Scrum Master` | `Product Manager` | ✅ 第 1 輪 |
| repo 規範 | `foundry-model-routing/SKILL.md:111` 機械性流轉 | `Scrum Master` | `Product Manager` | ✅ 第 1 輪 |
| repo 規範 | 標準 `role:*` label 集**四份**（正本＋3 adapter） | 6 格含 `role:scrum-master` | 8 格 | ✅ 第 1 輪，覆驗無第四份枚舉 |
| repo 規範 | **`skills/foundry-browser/SKILL.md:198`** | `CEO 與 PM` | `CEO 與 Product Manager` | ✅ **第 2 輪修正**（瑕疵 2） |
| repo 規範 | **`skills/foundry-ai-platform/SKILL.md:61`** | `九個角色分工` | `各在編角色分工` | ✅ **第 2 輪修正**（瑕疵 3） |
| 入口檔 | **`CLAUDE.md:67` ＋ `AGENTS.md:67`** | `角色薄 skill（9 個角色）` | `角色薄 skill（一個角色一份）` | ✅ **第 2 輪修正**（Developer 自查，我裁定在射程內） |
| 手冊 | 01／02／04／05／07／index 逐處 | `Scrum Master`／`PM` | `Product Manager` | ✅ 第 1 輪 |
| 手冊 | 06 全章改寫（含 `O5` 一節、SM 退場一節） | 舊組織 | 改寫 | ✅ 第 1 輪 |
| 手冊 | 07 章 §8 分層表副本 | 舊兩列 | 同 protocol | ✅ 第 1 輪 |
| 手冊 | **`03-workflow.md:9` 流程圖第三棒** | `SM` | `PM`（＝Product Manager） | ✅ **第 2 輪修正**（瑕疵 1） |
| 手冊 | 四章戳記 | `e62e42c`／`0a0b461` | `316f06e` | ✅ 第 1 輪 `fc67c64` |
| 歷史檔 | `docs/features/`／`docs/publish-reviews/`／`docs/pilot/`、`config-schema.md:206`／`:262`、`paperclip.md` 五處、`foundry_lint.py:1720` | — | **不動** | ✅ 兩輪皆確認，判尺見 §1 |
| 平台 | agent `eac62c45` 的 `name`／`title`／`urlKey`／`desiredSkills` | `PM`／`pm`／`role-pm` | `Product Manager`／`product-manager`／`role-product-manager` | ⏸ 合併後執行 |
| GitHub | 鏡像端 `role:*` label 集 | 6 格 | 8 格 | ⏸ 合併後執行 |

## Verdict

**✅ APPROVED**

第 1 輪三項重大瑕疵逐項驗收通過（§3），AC6 由 ❌ 轉 ✅，九條 AC 中屬本單射程的八條
（AC1～AC6、AC8、AC9）全數有證據，AC7 依工單載明屬合併後動作。機械層 `make check` exit 0、
`--selfcheck` 14 ✅ ＋ 1 ⏭（`mirror-recon`，環境限制、處置見 §4 第 1 點），
分支無夾帶、commit 訊息合格、已推遠端。

Developer 自查多抓的第 4 處**判定在射程內、維持不還原**，理由見 §3 末節。
`mirror-recon` 全表對帳與 §4 第 2 點的機械檢查開單，兩項都**不擋本單結案**，
但請依 §5 末列在合併後那一輪補完。
