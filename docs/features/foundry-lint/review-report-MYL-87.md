# 審查報告：MYL-87 foundry-init 產出的專案 `make check` 必掛：selfcheck 四項在沒有手冊的專案紅

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-87 |
| 分支 | `feat/MYL-87-selfcheck-target-project` |
| 審查範圍 | `b0177e0..6fcbff1`（單一 commit）：`skills/foundry-init/SKILL.md`、`tools/foundry-lint/foundry_lint.py`、`tools/foundry-lint/test_foundry_lint.py` |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |

> 全程在隔離 clone 進行——共用 workspace 被 MYL-77 的 run 佔著、HEAD 在 `feat/MYL-77-provision-team`（`X1`）。
> ⚠️ 該 clone 的 `origin` 是 workspace 不是 GitHub（MYL-86 的教訓），所以分支存在性另用
> `git ls-remote git@github.com:AugustusHsu/agent-foundry.git` 驗過：`6fcbff1` 確實在 GitHub。

## 0. 機械層（第 1 層，三條）

| 指令 | 結果 |
| --- | --- |
| `make check` | exit 0。`--selfcheck` 13 項全綠（`mirror-recon` 因隔離 clone 無 GitHub remote 而 ⏭）；`unittest discover` 四組全 OK，foundry-lint 那組 **175 tests OK** |
| `git diff --name-only main...HEAD` | 三檔，全屬本單；無夾帶 |
| `git log --oneline main..HEAD` | `6fcbff1 ✨ MYL-87 目標專案的 selfcheck：手冊四項改跳過、大檔清單改機械產生`——gitmoji ＋繁中標題 |

## 1. AC 逐條核對

證據皆為本輪自跑，Developer 留言的宣稱一律另行複驗。

| AC | 結果 | 證據 |
| --- | --- | --- |
| AC0 先定案再動手：至少比較兩案並寫建議，滿足判準①② | ✅ | 留言 `982708a3` 有完整兩案比較，且**另外列出三個被否掉的替代判準**（`config.yml` 的 `docs` 段判不開、只看手冊存不存在違反判準①、加旋鈕＝閘門可被關掉）。判準①②的落地見下方 AC1～AC5 |
| AC1 `nav-sync` 依 AC0 定案落地 | ✅ | `foundry_lint.py:454-460`。目標專案 fixture 實跑印 `⏭ [nav-sync]` ＋跳過理由 |
| AC2 `anchors` 同上 | ✅ | `foundry_lint.py:508-514`，同一支 `handbook_absent_skip()`；fixture 實跑 ⏭ |
| AC3 `handbook-stamp` 同上，沿用降級措辭體例 | ✅ | `foundry_lint.py:1335-1340`。**跳過放在淺 clone 分支之前**是對的：「沒有手冊」與「有手冊但驗不了歷史」是兩件事，合併會吐出指錯方向的處置。AC3 點名的降級分支原樣未動（diff 可見） |
| AC4 `big-files` 不准直接關掉 | ✅ | 檢查本體 `check_big_files()` **一行未改**（diff 只在其上方新增 `render_big_files_list()`）。目標專案 fixture 實測：大檔表沒填時 `❌ big-files` 列出全部 7 份漏列；填完轉 ✅。**它在目標專案仍然管著** |
| AC5 每項改動配擋得住的反例 | ✅ | 新增 `TargetProjectSkipTest` 11 條。**不只讀測試，我自己做了實地變異**：見下方「判準①的獨立驗證」 |
| AC6 用相同方法重跑 fixture，貼前後對照 | ✅ | **我自己另組了一份 fixture**（沒照抄 Developer 的腳本），前後對照見下節 |
| AC7 `--selfcheck` 全綠、`make check` 過、動到入口檔要兩份都改、別寫「共 N 項」 | ✅ | 見第 0 節。入口檔未動（diff 三檔），`entry-sync` 不涉及。計數措辭全部是**列名式**（「四項檢查（`nav-sync`／`anchors`／`handbook-stamp`／`init-copy-list`）」、「手冊三項（…）」），自帶對照，不是 MYL-41 禁的裸 N |

### AC6：我自己重跑的 fixture 前後對照

不照抄交付留言那支腳本——那支缺了雙入口檔那一段（見次要建議 2）。我依 `templates/entry-file.md`
的 SHARED-BODY ＋ §8-A／§8-B 自行產出兩份入口檔，其餘照複製清單組。

| | 前（`ws/main` 的 lint × main 版 fixture） | 後（本分支） |
| --- | --- | --- |
| `nav-sync` | ❌ | ⏭ 附理由 |
| `anchors` | ❌ | ⏭ 附理由 |
| `handbook-stamp` | ❌ | ⏭ 附理由 |
| `init-copy-list` | ❌ | ⏭ 附理由 |
| `big-files` | ❌（7 份全漏列） | ✅（門檻 12KB，達標 7 份） |
| 總結行 | `14 項未通過`（exit 1） | `全部通過，4 項跳過未檢查`（exit 0） |

**基準線確認**：實跑就是 `14 項未通過`，工單描述寫的 13 是錯的——Developer 的訂正屬實。
（那個數字數的是失敗訊息數不是檢查項數，`render_selfcheck_text()` 的 `bad = sum(len(r.failures)…)`。）

**中途一格另外有意義**：填大檔表之前只剩 `big-files` 一項紅，且錯誤訊息逐份點名。
我照 `foundry-init/SKILL.md` 新寫的步驟走 `--big-files-list`、把輸出取代模板那一列
`| {路徑} | {為什麼大／通常只需要哪一節} |`，一次就綠——**那段新寫的指示照著做真的會通**，
不是只有作者的環境成立。順帶驗到 `check_big_files` 要求 block 內含 `12KB` 字樣那一格
仍由模板散文供應，取代整段 block 才會踩到。

### 判準①的獨立驗證（不靠單元測試，實地變異真 repo）

| 變異 | 結果 | 判讀 |
| --- | --- | --- |
| 規則本體刪掉整個 `docs/handbook/` | `nav-sync`／`anchors`／`handbook-stamp` **仍 ❌**，且 `skipped` 為空 | 判準①成立：只用「手冊在不在」當條件就會在這裡從 ❌ 變 ⏭，兩層條件擋住了 |
| 規則本體刪掉整個 `skills/foundry-init/`（**我自己想到的反向破口**，Developer 未列） | `init-copy-list` 靜默 ⏭，但 `big-files` **❌** | **沒有靜默全綠的路**：入口檔 §4 列著 `skills/foundry-init/SKILL.md`，路徑消失被 `check_big_files` 的「列出的路徑都還在」抓住。防禦縱深成立，不構成缺陷 |

## 2. 四維檢查

- **正確性**：無重大發現。兩層跳過條件的**失效方向都是 fail-loud**：把 `skills/foundry-init/`
  複製進目標專案 → 四項一起回到必紅（吵，但不會錯放）；從規則本體刪掉它 → 由 `big-files` 接住（上表）。
  `--big-files-list` 走 `repo_root_of(args)`，`--repo-root` 實測有效；`parse_args` 的 `other_modes`
  已納入新旗標，不再誤要求 `--type`。產生器與檢查共用 `scan_big_files()`，集合必然相等——
  這是本次設計最好的一手，把「兩份清單各掃各的」這種漂移形狀從源頭消掉。
- **規格符合度**：符合 AC0 的自訂定案，且未越界——protocol 未動、關卡與 push 分級未動、
  `mirror-recon` 未動、`check_big_files` 未放鬆。範圍從四項擴到五項的決定（見下）我覆核後認同。
- **安全性**：無發現。無外部輸入、無網路、無機敏資料；`--big-files-list` 只讀檔並印路徑。
- **可維護性**：良好。跳過姿態沿用既有 `SelfcheckResult.skipped`，未新增第二套；
  判準抽成 `is_rule_repo()`／`handbook_absent_skip()` 單一來源，三個呼叫點不各寫一份條件。
  **雙向鎖＋守衛測試**（`test_複製清單那一行留有回指本檔的註解`）是本次的可維護性亮點：
  沒有它，互指註解被刪掉不會有任何地方報錯，判準就無聲懸空了。

### Developer 特別點名要被挑的三點

1. **跳過判準只吊在 `skills/foundry-init/` 目錄上** —— 我覆核後認為成立，且緩解措施到位。
   它不是挑的巧合，是複製清單自己那一行的硬對應；兩邊互指＋守衛測試把「註解被刪＝判準懸空」
   這條路封了。**兩個失效方向我都實地打過**（上表），沒有靜默放行的路。
2. **範圍從四項擴到五項** —— 這個板拍得對。MYL-86 交接時明說範圍歸本單決定；不收它，
   本單自己的目標（目標專案 selfcheck 不紅）字面上達不成，而且會掉在兩單之間。
   它的跳過只用一層條件也是對的：判準旗標與對照端**是同一個目錄**，沒有第二種情形要分；
   「目錄還在但 SKILL.md 不見」那一格仍然紅，測試與構造上都成立。
3. **`in_review` 寫不進去（`S6`）維持 `in_progress` ＋指派** —— 與 MYL-73／75／86 一致，
   不是漏改狀態。非缺陷。

### 我另外掃過的一格（MYL-77 的教訓）

Developer 這次改掉了 `foundry-init/SKILL.md` 步驟 4「其他三項……屬預期狀況」那段過期散文。
依 MYL-77 學到的「訂正機械宣稱要 grep 那句宣稱本身、不只是被點名的詞」，我全 repo 掃了
同型宣稱（`預期狀況`／`不算 init 失敗`／`docs/handbook/ 不存在`／`必紅` 等）：
**沒有第二份副本**。`foundry-adopt` 沒有對應段落（它不產入口檔，只探測既有的），
手冊 07 章只在故障對照表提 `nav-sync` 一次、與本次語意無關。四處 selfcheck 名稱清單
（`CLAUDE.md`／`AGENTS.md`／`Makefile`／`.pre-commit-config.yaml`）本次未增減檢查項，無須動。

## 3. 重大瑕疵清單

無。

## 4. 次要建議

**建議 1（最值得處理）：`handbook-stamp` 對「目標專案自建手冊」是一個必紅的死路，而新寫的步驟 4 把它描述成好事。**

`skills/foundry-init/SKILL.md` 步驟 4 新增了兩句，放在同一段裡：

- 「**要求是零紅字**……有任何 ❌ 就是 init 沒做完，回頭修，不要寫進報告當「已知狀況」。」
- 「目標專案哪天自建了 `docs/handbook/`，前三項就自動回到照驗。」

但 `foundry_lint.py:216-218` 的 `STAMPED_CHAPTERS` 是**寫死**的 agent-foundry 自家四章
（`03-workflow.md`／`04-decision-points.md`／`06-org-structure.md`／`07-workflows.md`），沒有設定點。
我實跑過：目標專案 fixture 一旦建了任何 `docs/handbook/`（我放了一份 `01-start.md`），
`handbook-stamp` 立刻吐四條 `…不存在——掛戳記的章節少了一份`，指名它沒有理由擁有的章節。
兩句合起來，等於叫該專案的維護者去修一個修不掉的紅字。

（同情境下 `nav-sync` 報 `mkdocs.yml 不存在`——那一條**是對的也可修**，所以問題只在 `handbook-stamp`。）

**不列為重大瑕疵的理由**：init 不產手冊，所以本單交付的情境完全不受影響，沒有任何 AC 因此不成立；
而改 `STAMPED_CHAPTERS` 的行為屬工單邊界明文禁止的「擴大成 selfcheck 全面支援任意專案」。

兩個處置方向，擇一即可：

- **(a) 一行程式**：`handbook-stamp` 的第 2 層條件由「`docs/handbook/` 不存在」改成
  「四章一份都不在」。安全性由第 1 層保證——規則本體恆有 `skills/foundry-init/`，
  永遠走完整檢查，判準①不受影響；而複製了整份手冊的目標專案仍照驗。
- **(b) 純文件**：把那句話收斂成只講 `nav-sync`／`anchors`，並明寫
  「`handbook-stamp` 的四章清單是 agent-foundry 自家的，目標專案自建手冊會紅，處置見 ⟨單號⟩」。

任一方向都**不建議搭本分支的便車**（報告一旦 APPROVED，依 MYL-74 判準合併者不單方面編輯已核可的交付物）。
開單與歸屬回報 Scrum Master／Tech Lead；掛在 MYL-91 底下也合理，它已經在收「目標專案 `make check` 的另一半」。

**建議 2：交付留言那支 fixture 腳本不是「照抄即可重現」，而 MYL-91 被指過去照抄。**

`d8c06d70` 說「照抄即可重現」，但腳本裡雙入口檔那段是註解
（`# 雙入口：模板 SHARED-BODY 逐字寫入兩檔…`），本體註明「完整版在我的 run scratch」——
而 run scratch 在 run 結束後會被清掉。少了那段，fixture 的 `entry-sync`／`big-files` 都跑不到
（`check_big_files` 找不到入口檔就直接記 failure）。我這輪自己補寫了那段並驗證可行，
建議在 scratch 被清掉之前把完整版貼進 MYL-91；需要的話我把我這份貼過去也可以。

**建議 3（最小）：`templates/entry-file.md` 沒跟上。**

模板 §0 第 4 點仍只說「跑 `--selfcheck` 確認……大檔清單沒有漏列」，第 92 行仍是人手填的
`| {路徑} | {為什麼大／通常只需要哪一節} |`，沒有指向 `--big-files-list`。
指示寫在 `foundry-init/SKILL.md` 步驟 2.5 是對的（那裡才是流程權威），但模板正是執行者
低頭填的那份檔案，補一句指過去可以少一次「照著模板手抄」。不影響紅綠。

## 5. 分支收尾檢查

- 分支狀態：**待合併**。`6fcbff1` 已在 GitHub（`git ls-remote` 實證），分支上只有本單三檔、無夾帶，
  commit 訊息合規。依 protocol 第 7 節「合併時點」，掛審查單的實作分支在 APPROVED **之後**才合併回 main，
  故本輪不合併；合併與刪分支由 CEO 依既有分流原則處理。
- 本單未動 `docs/handbook/`、未動 protocol ⇒ **不觸發手冊同步義務，也沒有發佈四步**。已複驗 diff 確認。

## Verdict

**✅ APPROVED**
