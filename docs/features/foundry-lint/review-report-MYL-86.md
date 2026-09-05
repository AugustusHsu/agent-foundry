# 審查報告：MYL-86 補一項 `--selfcheck`：foundry-init 複製清單 ↔ Makefile 目錄對應

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-86 |
| 分支 | `feat/MYL-86-init-copy-list` @ `049cd4f`（已推 origin；本報告 commit 後 +1） |
| 審查範圍 | `main...HEAD` 共 7 檔、3 顆 commit。**第三輪**：R3 覆驗＋AC 全條重取證據＋機械層重跑。設計取捨已於第一輪認可，本輪不重審 |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |

環境：全程 `git clone --shared` 隔離 clone。共用 workspace 這三輪都被 MYL-77 的 run 持有
（`git symbolic-ref --short HEAD` ＝ `feat/MYL-77-provision-team`），**自始至終沒有動過 HEAD**（`X1`）。

## 0. 機械層（第 1 層）

在 `049cd4f` 的乾淨 checkout 上重跑，數字逐項自行核對，不採信交付回報：

| 指令 | 結果 |
| --- | --- |
| `--selfcheck` | 12 項全綠＋`mirror-recon` ⏭。`init-copy-list` 印 `（Makefile 引用 4 個、清單列 4 個）`。⏭ 的理由是隔離 clone 沒有 GitHub remote（`gh issue list` 報 `none of the git remotes … point to a known GitHub host`），屬環境所致而非缺陷 |
| 四個 suite | **164／15／34／107** 全 `OK`，與交付回報一致 |
| `git diff --name-only main...HEAD` | 7 檔全屬本單，無夾帶：`.pre-commit-config.yaml`、`AGENTS.md`、`CLAUDE.md`、`Makefile`、`skills/foundry-init/SKILL.md`、`tools/foundry-lint/foundry_lint.py`、`tools/foundry-lint/test_foundry_lint.py` |
| `git log --oneline main..HEAD` | 三顆（`dcb35d8`／`e74bbb7`／`049cd4f`），全數 gitmoji ＋繁體中文標題 |

機械層沒有退件理由。

## 1. AC 逐條核對

證據一律為本輪自行執行的結果。

| AC | 結果 | 證據 |
| --- | --- | --- |
| AC1 `SELFCHECKS` 新增一項檢查，解析 Makefile 取出目錄逐一驗它在複製清單裡，缺一個就紅 | ✅ | `check_init_copy_list()` 掛在 `SELFCHECKS` 第 12 位。**正向反證自己跑過**：在副本的 `Makefile` 追加一行 `@python3 -m unittest discover tools/never-listed` ⇒ `❌ [init-copy-list] …（Makefile 引用 5 個、清單列 4 個）`，失敗訊息點名目錄、說明後果（「目標專案第一次跑 `make check` 就掛在這個目錄上」）並給出修法（「把 `tools/never-listed/`（全目錄）補進清單」）。缺一個確實紅 |
| AC2 依慣例配擋得住的反例測試，放既有測試檔 | ✅ | `test_foundry_lint.py` 共 8 條，全在既有檔案：`:630` test: 多一個不在清單的目錄被擋下、`:639` 非 test: target 引用的同樣被擋下、`:647` 只出現在註解裡的不誤報、`:652` 錨點漂掉時報錯而非放行、`:664` 目錄被移到「不複製」那行就不算列過、`:687` 那行以前的項目照樣算數、`:710` 清單列得比 Makefile 多不算失敗、`:729` 同一目錄只算一次。**不是擺設**——第二輪把 `init_copy_list_block()` 的終點還原成單一條件，`:664`／`:687` 同時紅；本輪把 `INIT_EXCLUDE_RE` 放寬成 `contains`，全套 164 測試中恰好只有 `:687` 紅 |
| AC3 先判斷要不要涵蓋其他 target；只做 `test:` 也可以，但要在檢查名稱與文件寫明範圍 | ✅ | 裁定＝**掃整份 `Makefile`**（比工單字面更大，工單明文允許）。範圍寫明於三處且用語一致：檢查 summary「`Makefile` 引用到的 `tools/` 目錄都在 foundry-init 複製清單裡」（不提 `test:`，不會讓人以為只管一個 target）、`Makefile:23-24`「它掃的是**整份本檔**的 `tools/` 引用，不只這個 target，所以下面 providers／browser 那幾行同樣受管」、`skills/foundry-init/SKILL.md:97`「它掃**整份 `Makefile`** 引用到的 `tools/` 目錄」。`:639` 那條測試把「非 test: target 也受管」釘住 |
| AC4 Makefile 註解從自律提醒改成指向本檢查；`selfcheck` 說明行、hook 名、入口檔 §6 一併同步；別寫「共 N 項」 | ✅ | 四處逐一看過：①`Makefile:19-24` 已改成「忘了改的話 `--selfcheck` 的 init-copy-list 會擋下（MYL-86）」，不再只是自律提醒；②`Makefile:14` `selfcheck` 說明行末尾加「init 複製清單」；③`.pre-commit-config.yaml:33` `foundry-selfcheck` hook 名同步加同一詞，另 `:43` `foundry-tests` 順手補上漏掉的 `publish-docs`；④`CLAUDE.md:134` 與 `AGENTS.md:134` 逐字相同、同樣列舉到「init 複製清單」。**「共 N 項」措辭全 repo 規則層零命中**（`grep` 的三筆全在 `docs/features/`、`docs/publish-reviews/` 的歷史審查記錄裡，那是綁 commit 的當時證據，非活文件） |
| AC5 `--selfcheck` 全綠、`make check` 過；動到入口檔兩份都要改（`entry-sync` 會擋） | ✅ | 見 §0。`entry-sync` 綠即雙入口共用正文逐字同步。本次未動 `skills/foundry-protocol/SKILL.md`，`handbook-stamp` 綠是正確結果而非漏檢 |

## 2. 四維檢查

- **正確性**：`init_copy_list_block()` 的終點取 `min(ends)`（兩個條件裡先出現的那一個），方向正確；`INIT_EXCLUDE_RE` 以行首錨定，散文裡的「照舊不複製。」不會誤觸發，並有 `:687` 釘住。`makefile_tools_dirs()` 先丟整行註解再掃，避免「註解提到就算數」的誤殺（`:647` 釘住）。正則字元類有界，無回溯風險。**無發現**。
- **規格符合度**：AC3 的裁定範圍比工單字面大，但工單本文明寫「只做 `test:` 也可以，但要寫明範圍」，擴大並寫明三處符合條文。兩條邊界都守住——沒有動 `foundry-init` 清單的內容本身，也沒有擴大成「所有反引號路徑都要驗存在」（`internal-links` 刻意排除的那一大類，MYL-41 判例）。**無發現**。
- **安全性**：檢查只讀 repo 內檔案、不執行外部指令、不處理機敏資料。**無發現**。
- **可維護性**：檢查失敗訊息含目錄名、後果與修法三要素，符合 repo 既有訊息體例。唯一負擔見 §4 第 2 項——那是既存問題，非本單引入。

## 3. 重大瑕疵清單

**無。** 三輪提出的三項全數修畢，逐項覆驗如下（覆驗方法都是自己跑，不是讀交付回報）：

| # | 內容 | 覆驗 |
| --- | --- | --- |
| R1（第一輪） | 本檢查讓 foundry-init 產出的專案多紅一項，而 MYL-87 邊界正好把它排除 ⇒ 要留 durable 交接 | ✅ 第二輪驗畢：MYL-87 留言 `dd69d22d` 實際存在，含實測輸出、清單第 104 行的結構性根因、AC0 兩個選項；`check_init_copy_list()` docstring 亦指過去。本單未因此改行為，正確 |
| R2（第一輪） | `- 不複製：` 那行被算進清單 ⇒ 假綠，正是本檢查存在理由的那個情境 | ✅ 第二輪驗畢：修法即 `min(ends)`；退回實驗證實兩條新測試同時紅，非擺設 |
| R3（第二輪） | `test_不複製那行以前的項目照樣算數` docstring 末句「提前截斷 ⇒ 假紅」方向講反，會害下一個人刪掉守門的 assert | ✅ **本輪驗畢**，見下 |

### R3 的覆驗

`049cd4f` 只動一個檔案、6 行、純 docstring，程式行為零改動（`git show --stat`）。新文字的三項事實宣稱逐一實測：

| 宣稱 | 實測 |
| --- | --- |
| 「四個 `tools/` 項在 SKILL.md 都排在那句散文**之前**」 | ✅ 四項在 `skills/foundry-init/SKILL.md` 第 88／89／91／93 行，「照舊不複製。」在第 103 行，`- 不複製：` 在第 104 行 |
| 「一個都掉不出區塊，自檢照樣印 ✅『清單列 4 個』」 | ✅ 把 `INIT_EXCLUDE_RE` 放寬成 `re.compile(r"不複製", re.M)` 實跑：`✅ [init-copy-list] …（Makefile 引用 4 個、清單列 4 個）`。確實是**靜默綠**，不是原本寫的假紅 |
| 「實際擋住它的是下面那條 `assertIn`——放寬正則時只有它會紅」 | ✅ 同一次放寬下跑**全套 164 測試**（Developer 只跑了 SelfcheckTest 那 40 個，本輪把範圍擴到全套）：`Ran 164 tests … FAILED (failures=1)`，唯一紅的就是 `test_不複製那行以前的項目照樣算數`。宣稱在全套範圍成立 |

末句「看到它紅而自檢是綠的，別把它當誤報刪掉：綠的那邊才是壞的」正面堵住 R3 擔心的那條最省事路徑，採納。

`foundry_lint.py:1785-1788` 那段刻意沒改也是對的：它談的是**另一個失效方向**（完全不截斷＝假綠、複製項排到那行之後＝紅），與 R3 的「提前截斷」不同前提，兩句各自成立，不是漏改。

## 4. 次要建議

不擋結案，Developer／合併者自行決定。

1. **`X1` 的那一格目前沒有家。** 第一輪撞出的「驗完 `HEAD` 到 commit 之間仍會被搶」＋純 ref 復原三步（絕不用 `--hard`），現在只存在於 **MYL-87 的留言**裡，而 MYL-87 的主題是「新專案 selfcheck 四項必紅」——與它無關，留言很可能被淹掉。建議由 Tech Lead 開一張小單寫進 `docs/standards/known-drift.md` 的 `X1`。**不要搭本分支的便車**：報告已 APPROVED，依 MYL-74 判準合併者不單方面編輯已核可的交付物。
2. **三處平行列舉清單沒有機械對應。** `Makefile:14`、`.pre-commit-config.yaml:33`、入口檔 §6（兩份）現在各自手抄同一串檢查名，與 `SELFCHECKS` 之間沒有任何檢查在管——**與本單所修的正是同一型漂移**，只是換了對象。本單邊界明文排除擴大範圍，要做得另開單。順帶一提，這四處都是列舉名稱而非計數，已避開 MYL-41 的「共 N 項」教訓，維持這個寫法。

## 5. 分支收尾檢查

- 分支狀態：**待合併**。`feat/MYL-86-init-copy-list` @ `049cd4f` 已推 origin，三顆 commit 全屬本單，工作區無已追蹤檔修改。Code Reviewer 不執行合併（合併屬 CEO）。
- **合併者的接續義務**：
  1. 合併回 main 後刪除 `feat/MYL-86-init-copy-list`（`P1` 明文含「刪已合併的遠端分支」）。
  2. **不觸發手冊發佈四步**——本單未動 `docs/handbook/`，`skills/foundry-protocol/SKILL.md` 亦一字未改（`git diff --name-only main...HEAD` 已證）。
  3. 鏡像 `github#20`（現況 OPEN／In Progress，已查證）依 `adapters/github.md` 時機 3 結案。
  4. ⚠️ **本單結案會讓 MYL-87 自動轉 `in_progress`，但它的鏡像 `github#21`（現況 OPEN／Blocked）不會跟著動** ⇒ `mirror-recon` 立刻轉紅並擋住全 workspace 的 commit。此現象在 MYL-73／MYL-75／MYL-82 各驗證過一次，已是通則：結案時順手把 #21 的 Status 一併同步。
- 附記：工作區有兩項與本單無關的未追蹤檔（`.codex/`、`myl69-repo-viewport.png`），屬 MYL-61 遺留待處置，未混入本分支任何 commit。

## Verdict

**✅ APPROVED**
