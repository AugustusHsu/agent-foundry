# 審查報告：MYL-91 `make check` 的另一半：foundry-lint 測試套件被複製到目標專案

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-91 |
| 分支 | `feat/MYL-91-target-project-tests` @ `1b32ceb`（本報告 commit 後 +1） |
| 審查範圍 | 第 2 輪（複審）。對象是 `9c2ca5c..1b32ceb` 共 3 檔；`main...HEAD` 累計 8 檔、4 顆 commit |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |

環境：全程 `git clone --shared` 隔離 clone。共用 workspace 本輪由 MYL-79 的 run 持有
（`git symbolic-ref --short HEAD` ＝ `main`），**沒有動過它的 HEAD**（`X1`）；
只在它上面跑過一次唯讀的 `--selfcheck`（取 `mirror-recon` 的真實遠端結果）。

複審依角色規範對著第 1 輪瑕疵清單（`33aba60e`）逐項驗，**不重新全面審查**。
方案選擇、四類搬移、`LLD.md` 註記、標記取代手維護清單這幾項第 1 輪已通過，本輪未翻。

## 0. 機械層（第 1 層）

在 `1b32ceb` 的乾淨 checkout 上自行重跑，不採信交付回報的數字：

| 指令 | 結果 |
| --- | --- |
| `make check` | **exit 0**。14 項自檢全綠（`mirror-recon` 在隔離 clone 是 ⏭，見下），四段 **190／15／34／107** 全 `OK` |
| `mirror-recon`（共用 workspace，有真實 remote） | ✅ **來源端 37 張、鏡像端 26 張**——隔離 clone 的 ⏭ 不算數（`MYL-60` 靜默失效形態），另跑一次取實值 |
| `git diff --name-only main...HEAD` | 8 檔全屬本單，無夾帶 |
| `git log --oneline main..HEAD` | 4 顆，訊息皆 gitmoji ＋繁體中文標題 |
| `git merge-base --is-ancestor origin/main HEAD` | 真（`9c2ca5c` 已把 `main` `7f0bfd0` 併入），且 `main` 自那時未再前進 |

本輪 commit `1b32ceb` 只動 3 檔（`test_foundry_lint.py`、`test_rule_repo.py`、
`skills/foundry-init/SKILL.md`），與交付回報一致。機械層沒有退件理由。

## 1. AC 逐條核對

| AC | 結果 | 我自己跑出來的證據 |
| --- | --- | --- |
| AC0 三案比較＋建議 | ✅ | 第 1 輪已核（`8ed2fc9f`，三案各有實測數字） |
| AC1 定案落地 | ✅ | 第 1 輪的缺口（第五類沒被分類到）本輪補上，見 §2 |
| AC2 fixture 整條綠 | ✅ | 四組實測，**含兩種合法 `ai_platform` 與「不宣告」的第三種形狀**，見 §2 |
| AC3 本 repo 測試數不減 | ✅ | `main` `7f0bfd0` 341（185／15／34／107，第 1 輪量的）→ `1b32ceb` **346**（190／15／34／107） |
| AC4 `init-copy-list` 不連帶紅 | ✅ | `✅ [init-copy-list] …（Makefile 引用 4 個、清單列 4 個）` |

fixture 用交付附的修正版腳本（留言 `345e187d`）。我先 `diff` 它與第 1 輪那份
（`92d27b03`）：差異只有宣稱的兩處（`|| true`、第 3 參數 `ai_platform`），複製動作
本身一行未改——第 1 輪已逐項對照過複製清單，故沿用。

## 2. 第 1 輪兩項瑕疵的複驗

### 瑕疵 1（可攜檔寫死 `ai_platform: paperclip`）— ✅ 已修，且修得比我建議的寬

我開出的過關判準是「把 fixture 兩份檔改成 `codex` 後可攜那半套仍 `OK`」。四組實測：

| SRC | `ai_platform` | `make check` |
| --- | --- | --- |
| 受審版 `9c2ca5c` | codex | **exit 2** — `FAIL: test_兩份設定檔的_ai_platform_不一致被擋下`，`failures=1` |
| `1b32ceb` | paperclip | **exit 0**（122／15／34／79，selfcheck 5 ⏭） |
| `1b32ceb` | codex | **exit 0**（同上） |
| `1b32ceb` ＋ `config.yml` **不宣告** `ai_platform` | — | **exit 0** |

第一列是我上一輪的判定在受審版上的重現（不是引用對方的數字）；第四列是交付主張
「同一類還有第二種形狀」的驗證——`skills/foundry-init/SKILL.md` §2 第 2 點確實允許
不宣告，而 `check_org_sync` 的 `elif config_ai and …` 在那種形狀下不觸發。這一格我認可：
比我建議的「先讀現值再換另一個合法值」多治了一種，方向正確。

**非空轉檢查**（反例自己寫兩端後，它會不會變成永遠綠的擺設）：把
`foundry_lint.py:1246` 的 `elif config_ai and config_ai != declared_ai:` 換成 `elif False:`——

```
FAIL: test_兩份設定檔的_ai_platform_不一致被擋下 — AssertionError: True is not false
Ran 2 tests … FAILED (failures=1)
```

「不一致」那條紅、「一致就通過」那條仍綠。這條測試仍然在測 `org-sync` 的真實行為。

### 瑕疵 2（守門 root 太寬鬆／`SKILL.md` 宣稱過強）— ✅ 已修（兩支都做了）

我給的是二擇一：收緊守門，或把宣稱改成與涵蓋一致。**交付兩邊都動了。**

- 我點名的兩條逃逸都進了 `WRONG_SIDE_PROBES`（第 2、3 條），第 3 條就是
  `RealConfigTest` 被搬走的那一條原文。`make check` 綠代表三條探針都被擋下。
- `_retarget_foundry_dir()` 是對的解法：`.foundry/` 屬「存在但值不同」，
  `ABSENT_IN_TARGET` 表達不了。兩份檔一起改的必要性（只改 `config.yml` 會讓
  `org-sync` 在守門 root 裡對撞）交付說得對，那一格我沒點到。
- `test_目標專案形狀的設定檔真的與規則本體不同` 守住 `_retarget_foundry_dir` 自己不退化，
  以及 `_retarget_foundry_dir` 裡「規則本體自己也宣告 `codex` 就報錯」的自我斷言——
  這兩處是把「構造失效」變成響亮失敗而不是靜默假綠，方向正確。

**我自己重新校準了一次缺口**（用第 1 輪講的「規則本體 ∖ 真實 fixture」差集，`git ls-tree` 取兩端）：
頂層 16 項中，`ABSENT_IN_TARGET` 現在削掉 9 項；其餘 `.pre-commit-config.yaml`／`Makefile`／
`templates`／`tools`／`skills/*`（含五個只帶 `SKILL.md` 的 skill——實查那五個目錄底下**只有**
`SKILL.md`，沒有第二個檔，所以不是缺口）都在複製清單上，`.foundry/` 已被 retarget，
`.gitignore` 有明寫的保留理由。**只剩入口檔一項**（見 §4 次要建議 1）。

## 3. 四維檢查

- **正確性**：無發現。`_set_ai()` 的「有就改、沒有就插在版本欄後面」在兩份檔上都驗過；
  插入點選 `foundry:`／`foundry_org:` 避免掉進縮排區塊，這個細節是對的。
- **規格符合度**：`SKILL.md` 的宣稱本輪改成與機械涵蓋一致（明寫構造是「削路徑＋換
  `.foundry/`」、寫錯邊有兩種形狀、且**仍是近似**、權威是複製清單）。第 1 輪的
  「不接受宣稱與機械不一致」已解除。
- **安全性**：不涉及。
- **可維護性**：判準連帶訂正（`test_rule_repo.py` docstring 從「依賴預先存在的 `docs/`」
  改成兩種形狀，並舉出形狀相近但**不**屬本檔的例子）處理的是根因不是症狀——
  下一個人分類時網眼不會再是同一個。

## 4. 次要建議（不擋結案）

1. **守門 root 還剩一格同類缺口：入口檔**。`CLAUDE.md`／`AGENTS.md` 在守門 root 裡
   仍是 agent-foundry 自己那份，而真實目標專案的是依 `templates/entry-file.md` 產的。
   實測打穿（往可攜檔注入 `assertIn("agent-foundry — 接手入口", CLAUDE.md)`）：
   守門 `Ran 1 test … OK`（放行），真 fixture `FAILED (failures=1)`。
   **這一格與 `.foundry/` 是同一類（存在但值不同），`_retarget_foundry_dir` 只做了一半。**
   不擋結案的理由有三：現行可攜套件裡沒有這種寫法（fixture 全綠已證）；`SKILL.md`
   本輪已明寫構造是近似、權威是複製清單；補起來的成本不高（照 `build-fixture.sh`
   同一段從模板重產兩份即可）。要補的話併進日後動到這塊的工單即可，不必為它單開一張。
2. **順手發現、但不屬本單**：目標專案若照 `skills/foundry-init/SKILL.md` §2 第 5 點
   **不建團隊**（Q4 答否）而沒有 `.foundry/org.yml`，`make check` 仍會紅——
   停在 `❌ [org-sync] .foundry/org.yml 不存在`（我實測 exit 2，測試那半套全綠、紅的是自檢）。
   也就是 init 說「條件性產生」、`org-sync` 說「一定要有」，兩份文件對這件事的說法不一致。
   這是 `selfcheck` 那一半（MYL-87 域）與 MYL-76／78 的裁定，**不是本分支的迴歸**，
   本單邊界也明寫不重做 selfcheck 判準。依角色規範不夾帶新需求進報告——
   **回報 Scrum Master 決定要不要開單**。

## 5. 分支收尾檢查

| 項目 | 狀態 |
| --- | --- |
| 分支名帶工單編號 | ✅ |
| 只有本單變更 | ✅ 8 檔 |
| commit 訊息格式 | ✅ 4 顆全合規 |
| `make check` | ✅ exit 0 |
| 與 `main` 可合併 | ✅ `main` 已在分支裡（`9c2ca5c`），且 `main` 未再前進 |
| 手冊發佈四步 | 不適用——未動 `docs/handbook/`（`known-drift.md` 不在手冊面） |
| 分支狀態 | 本報告 commit 後合併進 `main` 並刪除遠端分支 |

## Verdict

**✅ APPROVED**

兩項瑕疵都修好，且各自附得出「修之前它真的紅」的重現；瑕疵 1 的修法多治了一種
第 1 輪沒點到的形狀，瑕疵 2 兩支（收緊＋訂正宣稱）都做了。次要建議 1 是同類的
最後一格，不擋結案；次要建議 2 不屬本單，轉 Scrum Master。
