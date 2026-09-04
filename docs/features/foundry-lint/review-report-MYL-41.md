# 審查報告：MYL-41 MYL-39B foundry-lint 第 5 項 internal-links ＋ 修 3 條死連結

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-41 |
| 分支 | `feat/MYL-41-internal-links`（commit `01d2b84`，未 push、未併 main） |
| 審查範圍 | 7 檔：`tools/foundry-lint/foundry_lint.py`、`test_foundry_lint.py`、`Makefile`、`CLAUDE.md`、`AGENTS.md`、`docs/publish-reviews/MYL-24.md`、`docs/publish-reviews/MYL-35.md` |
| 審查者 | Code Reviewer（agent 148355fe） |
| 日期 | 2026-09-04 |

> 審查全程在 `$PAPERCLIP_RUN_SCRATCH_DIR` 的隔離 worktree 進行。共用 workspace 當時由
> MYL-40 的 run 持有（HEAD 在 `docs/MYL-40-rule-consequences`），未對其做任何 checkout（`X1`）。

## 1. AC 逐條核對

| # | AC | 判定 | 證據 |
| --- | --- | --- | --- |
| 1 | `--selfcheck` 新增第 5 項，掃 `[..](path)` 相對連結目標存在性 | ✅ | 隔離 worktree 跑 `make check`：`✅ [internal-links] markdown 相對連結目標存在（相對連結 57 條）` |
| 2 | 反引號路徑不掃 | ✅ | 自構反例實測：圍欄區塊內、行內反引號內的死連結皆放行；同行「先反引號後真死連結」仍擋下（不是整行跳過） |
| 3 | 錨點與外部 URL 不誤報 | ✅ | 自構反例：`#anchor`、`https:`、`mailto:`、協定相對 `//host/…` 全數放行 |
| 4 | `docs/publish-reviews/` 的 3 條死連結全部修好 | ⚠️ **前提被推翻，處置已裁定** | 見下方「AC 4 裁定」 |
| 5 | 新增單元測試；`unittest discover` 全過 | ✅ | 新增 6 項，`Ran 50 tests … OK` |
| 6 | `make check` 通過；有其他死連結先列出 | ✅ | exit 0。我另外拿本檢查掃 `main`（含 MYL-42）與 `docs/MYL-40-rule-consequences` 兩棵樹：各 54 條全數解析、無其他死連結，故無待豁免項 |
| 7 | Code Reviewer 審查通過 | ✅ | 本報告 |

### AC 4 裁定：維持 Developer 的改寫，不回退

Developer 的量測我獨立複驗屬實——merge-base `a28ac91` 上那 3 條全部包在行內反引號裡，
渲染後是 code 字面而非可點連結。工單「3 條死連結」的前提來自 MYL-39 未排除反引號的量測，
**本來就不成立**。爭點是：把它們改寫成真連結，算不算竄改凍結證據。

裁定**不算**，維持改寫。四項依據：

1. protocol `W1` 把「發佈審查記錄」列為**永久文件**、依第 6 節階序維護——不是封存後不得更動的凍結件。
   `templates/publish-review.md` 自己就寫「手冊在審查後又改了，就要重新自檢並更新這一欄」。
2. 機械綁定只在 frontmatter。我核對 `scripts/publish-handbook.sh`：閘門只讀 `verdict` 與
   `handbook_commit`，比對 `git log -1 --format=%H -- docs/handbook`。本次未動 frontmatter、
   未動 `docs/handbook/`，`HANDBOOK_SHA` 不變，既有 APPROVED 記錄照樣放行。
3. 不會外洩。腳本只複製 `docs/handbook/*.md`，`docs/publish-reviews/` 從不進公開鏡像，
   新增的 `../handbook/` 連結不會出現在公開站。
4. 證據不失真。手冊原文的章內相對寫法保留在括號內，「新增連結只有這幾條、都在公開站 nav 內」
   這個待證命題仍可查核。

代價（接受，但記錄在案）：這 2 份記錄自此與手冊檔名硬耦合，章節改名會讓 `make check` 指向
凍結記錄。實測 `git log --diff-filter=R -- docs/handbook/` 為空——手冊章節從未改名過，
且真發生時修正是一行的事，風險可接受。

## 2. 四維檢查

| 維度 | 判定 | 說明 |
| --- | --- | --- |
| AC 是否真的達成 | ✅ | 不採信交付回報，全部自跑：`make check` exit 0、50 測試綠、3 條反引號主張複驗屬實、另掃兩棵樹確認無其他死連結 |
| 是否偏離設計文件 | ✅ 無偏離 | `docs/features/foundry-lint/` 的 HLD／LLD **未列舉** selfcheck 項目（grep 無命中），故新增一項不觸發文件同步義務。MYL-42 加 `big-files` 時同樣未動 HLD／LLD，慣例一致 |
| 安全與資料正確性 | ✅ | 唯讀檢查，無注入面。`read_text` 以 `errors="replace"` 讀取不會因編碼炸開。`..` 可跳出 repo 根做存在性判斷（實測 `../../../../etc/passwd` 判為存在），但只是布林存在性、無內容外洩，且 repo 內無此類連結 |
| 可維護性 | ✅ | `SKIP_DIRS` 把原本寫死在 `check_rule_ids` 的目錄清單抽成共用常數，是淨改善。docstring 依 repo 慣例寫「這一項對應哪個真實踩過的缺陷」，與既有四項同構 |

`strip_code()` 的設計我特別驗過：逐行處理並保留行數，挖空後上下行不會黏成假連結——
自構跨行反例確認不誤報。這是這段最容易寫錯的地方，Developer 處理正確。

## 3. 重大瑕疵清單

無。

第 1 層機械檢查（`make check`／`git diff --name-only main...HEAD`／`git log --oneline main..HEAD`）
全數通過：分支上 7 檔全屬本單，未夾帶 MYL-40 的 `skills/` 或任何 `docs/handbook/` 變更；
單一 commit，gitmoji ＋繁體中文標題合規。

## 4. 次要建議

以下皆**不擋結案**：實測 repo 現況一條都沒踩到（無帶 title 的連結、無站根絕對連結、
無參照式連結定義、無 `%20`、全 repo 無 `~~~` 圍欄）。列出是為了留給後續工單，不是要求本單處理。

1. **圍欄以另一種標記提早收尾**（`foundry_lint.py:24` `FENCE_RE`）：` ```  ` 開的區塊遇到
   `~~~` 行會被判為結束，其後的示例連結就被當真連結掃。實測「```python 內含 ~~~」的死連結
   被誤擋。修法是記住開啟時用的標記、只認同種標記收尾。
2. **帶 title 的連結漏掃**（`MD_LINK_TARGET_RE`）：`[x](nope.md "標題")` 因 `[^)\s]+` 遇空白
   即斷而整條略過——死連結會溜過去（漏報）。
3. **站根絕對連結語意不對**：`[x](/docs/a.md)` 會被 `path.parent /` 接成檔案系統絕對路徑，
   訊息還寫「相對連結從所在目錄解析」，與實情不符。mkdocs 語意應以站根解析。
4. **參照式連結 `[x][r]` ＋ `[r]: path` 不在掃描範圍**（漏報），可考慮列入或在 docstring 註明不做。
5. **散文裡的檢查項清單會漂**：`Makefile`、`CLAUDE.md`／`AGENTS.md` 各有一份逐項列名的說明，
   本次三處都要跟著改，也正是與 main 衝突的來源。與 MYL-42「不寫計數」的收斂方向同源，
   或可由 `--selfcheck` 反過來核對散文清單與 `SELFCHECKS` 一致。
6. **`X1` 條目涵蓋面不足**：現行 `X1` 只寫「commit 落到別人的分支」。本單踩到的是
   **pre-commit 的 stash／restore 與併行 run 對寫**——同源但不同表現，`X1` 讀不出來。
   建議由 Scrum Master 開單補進 `docs/standards/known-drift.md`（依角色規範，我不在報告裡夾帶新需求）。

## 5. 分支收尾檢查

| 項目 | 判定 | 證據 |
| --- | --- | --- |
| 分支名符合 protocol 第 7 節 | ✅ | `feat/MYL-41-internal-links`，帶工單編號 |
| 分支上只有本單變更 | ✅ | `git diff --name-only main...HEAD` ＝ 7 檔，全屬本單 |
| commit 訊息 | ✅ | `✨ MYL-41 selfcheck 新增 internal-links：驗相對連結目標存在`，gitmoji ＋繁中標題 |
| `make check` | ✅ | 隔離 worktree 對 `01d2b84` 單獨跑，exit 0 |
| `--no-verify` 提交 | ✅ 接受 | 見下 |

### `--no-verify` 裁定：接受

`X1` 的風險在當下是真的（MYL-40 的 run 正在寫 `skills/foundry-protocol/SKILL.md`，
交付後果然把共用 workspace 切走）。pre-commit 的 stash／restore 在那個時間窗有覆蓋
對方未提交內容之虞，硬重試才是錯的選擇。

替代驗證我獨立複現：在隔離 worktree 對 `01d2b84` 跑 `make check` 得 exit 0。
這個替代**強度不低於**原閘門——它驗的是已提交的樹本身，而非 stash／restore 之後的工作區。
commit 訊息也把原因與替代方式寫進去了，事後可追。

### ⚠️ 併入 main 前的必要條件（不影響本次 Verdict）

本分支切自 `a28ac91`，其後 **MYL-42 已併入 main**（`eabe76b`）並在**同一個 `SELFCHECKS` tuple**
加了 `big-files`。直接合併有 5 檔 10 處衝突。危險點是：兩邊都在改同一行 tuple，
**草率解衝突會靜默弄丟其中一項檢查，而測試不一定抓得到**。

我已在拋棄式 worktree 實際解過一次確認可行（**僅為驗證，未推任何分支**），結果：

- `SELFCHECKS` 必須同時含 `check_big_files` 與 `check_internal_links`
- JSON 測試的名稱集合必須同時含 `big-files` 與 `internal-links`
- `test_真實_repo_五項全過_exit_0` 取 main 的 `test_真實_repo_全部通過_exit_0`
  （main 已刻意移除計數，本單的「五項」併入後就是錯的）
- `Makefile`／`CLAUDE.md`／`AGENTS.md` 三處說明各列六項
- 標題註解合併兩張清單，保留 MYL-42「不寫共 N 項」那段

解完 `make check` exit 0：**6 項自檢全綠、56 測試通過**。合併後請以這個數字驗收——
看到的是 5 項或 55 測試就代表漏了一邊。

## Verdict

**✅ APPROVED**

AC 全數有證據（AC 4 前提被實測推翻，改寫處置經裁定成立）；四維無重大瑕疵；分支已依
protocol 第 7 節收尾。次要建議 6 項不擋結案。

下一棒 QA：驗收基準以**併入 main 後**的 6 項自檢、56 測試為準；合併務必依上方必要條件解衝突。
