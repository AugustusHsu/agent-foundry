# 審查報告：MYL-92 handbook-stamp 的 STAMPED_CHAPTERS 寫死四章

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-92 |
| 分支 | `feat/MYL-92-stamped-chapters-skip` @ `379663e`（本報告 commit 後 +1） |
| 審查範圍 | 第 2 輪（複審）。對象是 `5150cd7..379663e` 共 1 檔；`main...HEAD` 累計 4 檔、2 顆 commit |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |

環境：共用 workspace 本輪由本 run 持有（`git symbolic-ref --short HEAD` ＝
`feat/MYL-92-stamped-chapters-skip`），`make check` 直接在其上跑；fixture 另走
`git clone --shared` 的隔離 clone，沒有動過任何人的 HEAD（`X1`）。

複審依角色規範對著第 1 輪瑕疵清單（留言 `df61191e`）逐項驗，**不重新全面審查**。
第 1 輪已通過的程式面（兩層條件、五種突變、fixture 四情境）本輪未翻，只確認它一字未動。

## 0. 機械層（第 1 層）

| 指令 | 結果 |
| --- | --- |
| `make check` | **exit 0**；14 項自檢全部通過；197＋15＋34＋107 tests OK |
| `git diff --name-only main...HEAD` | 4 檔（`foundry_lint.py`／`test_foundry_lint.py`／`test_rule_repo.py`／`foundry-init/SKILL.md`），無夾帶別單 |
| `git log --oneline main..HEAD` | `5150cd7`／`379663e` 兩顆，皆 gitmoji ＋繁中標題 |
| `git diff --stat 5150cd7..379663e` | `skills/foundry-init/SKILL.md` 一檔、12 加 6 減——**程式與測試確實零改動**，交付回報這句屬實 |

## 1. AC 逐條核對

| AC | 結果 | 證據 |
| --- | --- | --- |
| AC0 先定案再動手 | ✅ | 第 1 輪已驗（留言 `86731e89`），本輪未翻 |
| AC1 定案落地＋`SKILL.md` 措辭對齊 | ✅ | 程式面第 1 輪已 ✅；**措辭面本輪轉綠**，證據見 §1.1／§1.2 |
| AC2 擋得住的反例測試 | ✅ | 第 1 輪五種突變全被接住；本輪確認測試檔一字未動（`git diff --stat`） |
| AC3 fixture 實測 | ✅ | 第 1 輪我獨立重建兩份 fixture、四情境吻合；本輪另跑一次「目標專案＋自建手冊」驗新散文（§1.1） |
| AC4 `--selfcheck` 全綠、`make check` 過、別寫「共 N 項」 | ✅ | 見 §0。新寫的段落是**列名式**（「五項檢查（`nav-sync`／…／`selfcheck-names`）」），自帶對照端，不是 MYL-41 禁的裸 N |

### 1.1 §3 瑕疵 #1 已修——三種時點我逐列打過

`SKILL.md:217-230` 現在把五項分成三列。我沒有照著讀，而是造一個**第 1 輪沒跑過的情境**
（目標專案 ＋ 自建手冊 ＋ 自己的 `mkdocs.yml`）直接問程式：隔離 clone 刪掉
`skills/foundry-init/` 與 `docs/handbook/`，改放一份自己的 `01-first-run.md`
與對得上的 `mkdocs.yml`，跑 `--selfcheck`：

```
✅ [nav-sync] 手冊章節與 nav 一致（且只有一份手寫 nav）（章節 1 篇）
✅ [anchors] 手冊內部錨點可跳轉（內部錨點連結 0 個）
⏭ [handbook-stamp] 手冊四章戳記不落後於 protocol（沒有掛戳記的章節，未驗）
⏭ [init-copy-list] `Makefile` 引用到的 `tools/` 目錄都在 foundry-init 複製清單裡
⏭ [selfcheck-names] 四處手抄的自檢名稱清單與 `SELFCHECKS` 一致
```

三列逐一對上：第一列**照驗且變得了 ✅**（這正是本單要恢復的「零紅字達得到」）；
第二列在自建手冊之後仍 ⏭；第三列**手冊建了照樣 ⏭**，證實「與建不建手冊無關」不是推論。
（同一份輸出裡 `big-files`／`internal-links` 報紅，是我這個粗製 fixture 沒回填大檔表、
又刪了入口檔連到的目錄所致，與本單判準無關。）

### 1.2 §4-1「四項→五項」已修，而且第二份副本是 Developer 自己找到的

我沒有數散文，改用判準的定義域反查：`grep -n "is_rule_repo" foundry_lint.py` 的呼叫點
只有五個檢查會問到它——`handbook_absent_skip()`（`nav-sync` `:509`、`anchors` `:563`）、
`stamped_chapters_absent_skip()`（`handbook-stamp` `:1390`）、`init-copy-list` `:1977`、
`selfcheck-names` `:2098`。沒有第六個。`:116-118` 與 `:214` 兩處現在都寫五項且列名一致。

**第 1 輪我只點名了 `:213`**，Developer 自行 grep 出同檔 `:116` 那份同樣過期的清單一併訂正——
這是對的，只改被點名的那一處會在 repo 裡留下第二份錯的。我另外掃過全 repo，
`docs/features/`／`docs/publish-reviews/` 裡的「四項」都在歷史報告裡（記載當時實況，不改），
`test_rule_repo.py:14` 的「手冊三項」在 MYL-92 之後仍然成立（旗標仍是那個目錄）。
唯一剩下的一格見 §4-1，非本分支造成。

### 1.3 兩處我特別去打的措辭（都站得住）

- **`:228` 說 `selfcheck-names` 的對照端在目標專案不存在**——這句範圍很容易寫寬。
  實況是四個抄寫點裡 `Makefile` 與 `.pre-commit-config.yaml` 是整份複製過去的、**會**存在
  （`check_selfcheck_names()` 的 docstring `:2091-2094` 自己講明了這件事）；不存在的是兩份
  入口檔 §6 那一行，因為 `templates/entry-file.md` 的 §6 是自由格式。散文寫的正是
  「入口檔 §6 那份自檢名稱清單」，**沒有把 Makefile 那兩處也說成不存在**，範圍精確。
- **`:214` 說「這五項在剛 init 完的專案會印 ⏭」是否漏了 `mirror-recon`**——不漏。
  真的 init 出來的專案不設 `mirror_platform`，`check_mirror_recon()` `:1846-1848` 走的是
  「無事可對」的 ✅ 分支、**不是 `skipped`**。我 fixture 裡看到的第六個 ⏭ 是因為隔離 clone
  沿用了 agent-foundry 自己的 `config.yml`（`mirror_platform: github`）卻連不上鏡像端，
  屬環境所致。第 1 輪我開的自檢判準（「每一個印 ⏭ 的項目都答得出何時變 ✅」）到此成立。

## 2. 四維檢查

- **正確性**：無發現。本輪改的是散文，三列時點我用一個新情境實跑逐列驗過（§1.1），
  沒有靠讀程式推斷。程式與測試零改動，第 1 輪的結論原樣有效。
- **規格符合度**：邊界全部守住。未動 protocol／關卡／push 分級；`STAMPED_CHAPTERS` 未變成設定項；
  MYL-87 那幾項跳過邏輯本體未動；未動 `docs/handbook/` ⇒ 不觸發手冊發佈四步。
  第 1 輪 §4-2 點出的 `--staged-handbook-sync` 缺口，Developer 依本單邊界**沒有順手做掉**，
  也沒有代開新單——處置正確（見 §4-2）。
- **安全性**：不涉及。純本地檔案存在性判斷。
- **可維護性**：改法選了「保留完整列舉 ＋ 每項都答得出何時變 ✅」而不是把清單縮短，
  方向對：這一段的讀者是照著做 init 的人，看到 ⏭ 卻在文件裡找不到它，比看到一條
  「它永遠 ⏭」更容易自己發明處置。段首那句「答不出來就別為它動手」把我的自檢判準
  轉成了給讀者的要求，段尾原有的「以檢查實際印出來的為準」也沒被動掉。

## 3. 重大瑕疵清單

無。第 1 輪唯一那項已修並實測（§1.1／§1.2）。

## 4. 次要建議

1. **`test_rule_repo.py:667` 的測試名 `test_目標專案四項印跳過而不是失敗` 已經短一項**：
   它的迴圈是 `HANDBOOK_CHECKS + ("init-copy-list", "selfcheck-names")` ＝ 5 項（`:669`）。
   **非本分支造成**——`main` 上的同一行就是這樣（MYL-91 分檔時原樣搬過來，名字更早），
   所以不擋本單。與 §4-1 是同一型（列舉與實際定義域脫節），下一個動這個檔的人順手改名即可，
   不值得為它單開一張單。
2. **（第 1 輪 §4-2 原案，仍待處置，本輪重申）**：`--staged-handbook-sync`
   （`foundry_lint.py:1453`）**完全沒有目標專案跳過**，而 `.pre-commit-config.yaml` 是
   `foundry-init` 步驟 2 整份複製過去的。目標專案改了自己那份 protocol 副本就會被 hook
   硬擋在 commit，訊息指名它沒有也不該有的四章，三條處置全部指向不存在的戳記——
   出路只有 `--no-verify`，正是本單論證要避免的失效模式，而且比本單修的那格更兇。
   依 `D3` 屬開新單的情形，**請 Scrum Master／CEO 判定**；Developer 未代開是對的。

## 5. 分支收尾檢查

| 項目 | 狀態 |
| --- | --- |
| 分支名帶工單編號 | ✅ `feat/MYL-92-stamped-chapters-skip` |
| 只有本單變更 | ✅ 4 檔 |
| commit 訊息格式 | ✅ 2 顆全合規 |
| `make check` | ✅ exit 0 |
| 與 `main` 可合併 | ✅ `main`（`b6da572`）是本分支的祖先，且 `main` 未再前進 |
| 手冊發佈四步 | 不適用——`git diff --name-only main...HEAD -- docs/handbook/` 為空 |
| 分支狀態 | 本報告 commit 後合併進 `main` 並刪除本地與遠端分支 |

## Verdict

**✅ APPROVED**

第 1 輪退回的是「這段散文與檢查的實際行為對不上」——那正是本單存在的理由，所以退得對；
這一輪它被修成了可以逐列打的形狀，我用一個新情境把三列全部打過，還順手驗了兩句最容易寫寬的
措辭（§1.3）都沒有寫寬。程式面第 1 輪已經沒有保留意見且本輪零改動。
