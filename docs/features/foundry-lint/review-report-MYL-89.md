# 審查報告：MYL-89 補一項 `--selfcheck`：四處手抄的自檢名稱清單 ↔ `SELFCHECKS`

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-89 |
| 分支 | `feat/MYL-89-selfcheck-name-list` @ `7acdb2f`（共用 workspace 的本地分支，未推 GitHub；本報告 commit 後 +1） |
| 審查範圍 | `main...HEAD` 共 6 檔、1 顆 commit。第一輪，全條取證 |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |

環境：全程 `git clone --shared` 隔離 clone。共用 workspace 本輪被 MYL-90 的 run 持有
（`git symbolic-ref --short HEAD` ＝ `feat/MYL-90-stale-axis-a-claims`，且有未 commit 的變更），
**自始至終沒有動過它的 HEAD**（`X1`）。

## 0. 機械層（第 1 層）

在 `7acdb2f` 的乾淨 checkout 上自行重跑，不採信交付回報的數字：

| 指令 | 結果 |
| --- | --- |
| `--selfcheck` | 13 項全綠＋`mirror-recon` ⏭，`selfcheck-names` 印 `（14 項 × 4 處）`。⏭ 是隔離 clone 沒有 GitHub remote 所致（`gh issue list` 報 `none of the git remotes … point to a known GitHub host`），屬環境非缺陷 |
| 四個 suite | **185／15／34／107** 全 `OK` |
| `git diff --name-only main...HEAD` | 6 檔全屬本單，無夾帶：`.pre-commit-config.yaml`、`AGENTS.md`、`CLAUDE.md`、`Makefile`、`tools/foundry-lint/foundry_lint.py`、`tools/foundry-lint/test_foundry_lint.py` |
| `git log --oneline main..HEAD` | 一顆 `7acdb2f`，gitmoji ＋繁體中文標題 |

機械層沒有退件理由。

## 1. AC 逐條核對

證據一律為本輪自行執行的結果；交付回報的宣稱一律重驗。

| AC | 結果 | 證據 |
| --- | --- | --- |
| AC1 四個抄寫點任一漏掉一項檢查名 ⇒ 紅，且訊息點名是哪個檔案漏了哪一項 | ✅ | 自建探針：只把 `CLAUDE.md` 那一行的「規則標記」拿掉（`AGENTS.md` 保持正確），`--selfcheck` rc=1，訊息為「CLAUDE.md 的§6 指令速查的自檢註解行漏了 `rule-marks`（標籤「規則標記」）——…把「規則標記」補進那一行」＝檔案／項目／修法三要素齊。四處各自擋得住則由 `test_四處任一漏抄一項檢查名都被擋下` 的 4 個 subTest 覆蓋（見 AC2 實驗 A） |
| AC2 反例測試真的擋得住，退回實作後必紅，且要跑全套 | ✅ | **我自己重跑了全部五組退回實驗**，每組都跑完整 185 測試（不是單一 TestCase，MYL-86 R3 的教訓）：A 拿掉「漏抄」偵測→`四處任一漏抄…`＋`錯字…`（failures=5）；B 拿掉「多寫」偵測→`四處多寫…`＋`錯字…`（2）；C 錨點漂掉改成放行→`抄寫點的錨點漂掉時報錯而不是放行`（1）；D 拿掉登記表綁定→`登記表少一項`＋`登記表多一項`（2）；E 拿掉子字串護欄→`標籤互為子字串時擋下`（1）。**每組紅的剛好只有該擋的那幾條**，其餘 180 條不受牽連；五組跑完檔案雜湊比對還原無誤 |
| AC3 檢查名與文件寫明它管的是「四個抄寫點 ↔ `SELFCHECKS`」，別讓人以為管得更多 | ✅ | 名稱 `selfcheck-names`；`foundry_lint.py:2027-2044` docstring 明寫「**管得到的只有這一組對應關係**：四處列到的名稱集合 ↔ `SELFCHECKS` 註冊的名稱集合。不管順序、不管措辭、也不管四處以外任何提到檢查名的散文」，並明文把 MYL-41 那類「所有反引號路徑都要驗存在」排除在外。輸出的 summary 亦為「四處手抄的自檢名稱清單與 `SELFCHECKS` 一致」 |
| AC4 四處維持列舉，全 repo 規則層不出現「共 N 項」 | ✅ | 四處 diff 逐一看過，都是在既有列舉尾端插入「自檢名稱清單」，無一改成計數。`grep -rn "共 [0-9N]* *項"` 全 repo 6 筆：4 筆在 `docs/features/` 的歷史審查報告（綁 commit 的當時證據，非活文件），2 筆是 `foundry_lint.py:136` 與 `:2037` **禁止這個寫法的規則文字本身**。規則層零違例。（`res.summary` 的「14 項 × 4 處」是 `len()` 算出來的執行期數字，與 `init-copy-list` 等 19 處既有 summary 同一慣例，非手抄計數） |
| AC5 `--selfcheck` 全綠、`make check` 過，且新增自檢本身要同步進那四處 | ✅ | `make check` 在乾淨 checkout 上通過（見第 0 節）。四處都補了「自檢名稱清單」，`test_本檢查自己也列在四處` 釘住這件事——本單確實是自己的第一個使用者 |
| AC6 需要 GitHub 鏡像，狀態變更照 adapter 時機 2／3 同步 | ⚠️ 部分 | `#23` 經 REST 確認 OPEN、標題與來源端一致。**Project Status 欄位本輪查不到也改不了**：GitHub GraphQL 對本帳號正處於 rate limit（`gh api graphql` 回 `graphql_rate_limit`，`gh api rate_limit` 卻顯示 5000/5000＝屬次級限制，reset 在約一小時後），而 Status 欄位與 `gh project item-list` 都只有 GraphQL 一條路。REST 走得通的部分我照時機 3 做完（見第 5 節），Status 那一格列為本單的接續義務 |

## 2. 四維檢查

- **正確性**：無發現。除交付回報列的反例外，我另做了五個探針試著打穿：①真的在 `SELFCHECKS` 前面插入一個第 15 項檢查（＝MYL-86 漂移的實際形狀）→ 紅，訊息點名 `probe-15` 並給出補登記表＋補四處的修法；②只讓四處之一漏抄 → 紅且點名該檔（見 AC1）；③④⑤見次要建議第 2 項。靜態取名的邊界也查過：`SELFCHECK_NAME_RE` 對 14 個 check 函式各只命中一次且名稱正確（`check_selfcheck_names` 自己的失敗訊息裡那段 `SelfcheckResult("<名稱>"` 因 `<名稱>` 不合 `[a-z0-9-]+` 而不會誤命中）。錨點找不到時報錯不放行，方向是對的——找不到清單等於沒比對，這種時候印 ✅ 比印 ❌ 危險。
- **規格符合度**：符合。三層結構（登記表 → 綁死登記表 → 子字串護欄）各有反例守著，第 2 層正是讓登記表不淪為第五份手抄的關鍵。目標專案跳過的理由我獨立查證過，成立：`skills/foundry-init/SKILL.md:169` 與 `:240` 確認 `Makefile`／`.pre-commit-config.yaml` 是整份複製，而 `templates/entry-file.md:111-112` 的 §6 明寫「列出這個專案實際會用到的指令」＝自由格式，四個抄寫點中有兩個在目標專案依規格就不存在，整項跳過比只驗一半誠實；`test_抄寫點整份不見時報錯而不是放行` 也把「規則本體缺檔照樣紅」釘住了，判準沒有被偷偷放寬成「那一行在不在」。**`staged-handbook-sync` 不列進登記表**的取捨正確（它不在 `SELFCHECKS`），且配了反例。
  - **裁定：argparse `--selfcheck` help 刪掉列舉——保留這個處置，不改成第五個受管抄寫點。** 交付回報請覆審裁定的就是這一項。事實面我覆核無誤：原本那行確實是第五份手抄，且已落後四項（缺 `version-shape`／`table-shape`／`org-sync`／`init-copy-list`），MYL-44 審查報告當年寫的「四處」正是把入口檔算一處、CLI help 算一處。判定理由：(a) 這是**刪除**同一組清單的一份副本，落在本單「自檢名稱清單這組對應關係」的範圍內，不是擴大範圍；(b) 入口檔自我約束那條「不要把規範內容抄進來——抄過來的那份會過期」與 MYL-41／MYL-42 的既有立場都指向少一個副本；(c) 舊的那行是**錯的**（落後四項），比沒有更糟，而跑一次就印得出逐項名稱。原地留的註解也寫明了「要在這裡列，就得先把本行加進 `SELFCHECK_COPY_SITES`」，把往後的取捨釘死，不會被誰無聲加回去。`grep` 確認全 repo 沒有其他地方依賴那行 help 的列舉。
- **安全性**：無發現。不吃外部輸入、不連線（刻意用原始碼字面量靜態取名，避免為了問名字而觸發 `mirror-recon` 的網路呼叫），無機敏資料。`inspect.getsource` 只讀本模組自身。
- **可維護性**：無發現須擋結案者。`SELFCHECK_LABELS` 的順序照 `SELFCHECKS`，並由 `test_靜態取名與實際跑出來的名稱一致` 同時釘住「靜態取名＝實跑名稱」與「登記表順序＝`SELFCHECKS` 順序」兩件事——這條測試是整組設計的地基，位置擺得對。註解密度、失敗訊息三要素、`res.summary +=` 的用法都與 `init-copy-list` 同體例。次要建議見第 4 節。

## 3. 重大瑕疵清單

無。

## 4. 次要建議

不擋結案，Developer 或後續工單可自行決定是否採納。

1. **`tools/foundry-lint/test_foundry_lint.py:832` 的 docstring 寫「把 13 項跑一遍」，正確值是 14——上線當天就過期了。** 本單管的正是這一類手抄數字，而這行剛好落在受管範圍外（測試檔非規則層，AC4 不涵蓋）。建議直接把數字拿掉寫成「把每一項跑一遍」，別再換成 14 又等下一次過期。
2. **包含比對在兩個方向上都比「集合相等」鬆，實測有兩種寫法會靜默通過**，兩者都是形狀壞掉而非名稱漂移，屬本檢查刻意的邊界，但值得記在這裡免得日後被當成漏洞重新發現：①把分隔符刪掉讓兩項黏成一團（`大檔清單相對連結`）→ 綠；②在正確標籤後面附加雜訊（`錨點但其實沒在跑`）→ 綠。收緊的代價是四處措辭得先統一，而 docstring 已說明為什麼不走那條路（最短形不必談判），我認同這個取捨。另補一則實測：把入口檔任一份的列舉重排或重複，`entry-sync` 會先擋下（兩份必須逐字相同），所以那條路徑實務上不是無人看管。
3. `check_selfcheck_names()` 開頭 `selfcheck_registered_names()` 呼叫了兩次（一次求 `unnamed`、一次求 `registered`），等於對 14 個函式各跑兩遍 `inspect.getsource`。純冗餘、無正確性影響。

## 5. 分支收尾檢查

- 分支狀態：**已合併並刪除**。本報告 commit 進 `feat/MYL-89-selfcheck-name-list` 後 `--no-ff` 併入 `main`，刪本地分支；分支從未推上 GitHub，無遠端分支要清。合併後在 `main` 上重跑 `make check` 覆驗。
- 手冊發佈四步：**不觸發**。`git diff --name-only main...HEAD` 六檔皆不在 `docs/handbook/`，protocol 未動，`handbook-stamp` 綠。
- 入口檔兩份都改了，`entry-sync` 綠。
- **接續義務（本單無法完成的那一格）**：GitHub GraphQL 於本輪 rate limited，鏡像 `#23` 的 Project Status 改 `Done`、以及本單結案後 MYL-91 自動轉 `in_progress` 所連帶的 `#24` Status 改 `In Progress`，兩者都得等 GraphQL 恢復後補做。期間 `mirror-recon` 讀不到鏡像端會判 **skip 而非 fail**（靜默失效，MYL-60 已記），所以綠燈不代表已對上帳。

## Verdict

**✅ APPROVED**
