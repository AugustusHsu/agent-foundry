# `R5` 重啟評估：GitHub PR 作為合併閘門（MYL-53）

> 2026-09-04｜Tech Lead｜依 MYL-39 計畫 v5 §4，使用者於確認卡 `7598a79e` 整包核可。
> 上游：[`HLD.md`](HLD.md)（MYL-9）、[`gap-analysis.md`](gap-analysis.md)（MYL-35）。
> 反悔錄原條目：[`known-drift.md`](../../standards/known-drift.md) 的 `R5`。
>
> **本報告只評估，不改規則、不動 CI、不動 `.foundry/config.yml`。**
> 採用與否若要落地，需另開單並經使用者核可（改 protocol 屬規範修訂）。

## 0. 結論

**維持否決。** 但**理由與 MYL-23 當初的不完全相同**，且原重啟條件不可判定，本次一併替換。

- MYL-23 的理由是「PR 只是同一審查的第二份表單」。本次實測發現：在**審查維度**上，這條理由不但沒有弱化，還被 GitHub 自身的規則**加強**了——本 repo 只有一個 git 身分（89/89 顆 commit 同一人），而 GitHub 明文禁止 PR 作者核可自己的 PR。要求核可＝流程死鎖；不要求核可＝PR 在審查維度上**恆為零增量**。
- 唯一真實的增量在**機械檢查維度**：把 `make check` 從「合併後才跑」提前到「合併前擋下」。這個缺口是真的，**而且此刻正在發生**（main 的 CI 連三紅，見 §6）。但它的成因是一個 CI 環境缺陷，屬 `D1` 退回 MYL-44，**修那個缺陷比引入 PR 便宜一個數量級**。
- 計畫 §4 說「機械部分早就就位」——這句要修正：`on: pull_request` 只是**宣告**了觸發器，它**從未觸發過一次**（12 次 run 全是 push-on-main），而且沒有分支保護／ruleset，**PR 檢查紅燈擋不住合併**。真正要花的成本不是「補一句規則」，是一項只有使用者能做的 repo 設定變更。

原重啟條件「多人／多 agent 真併發寫 code」**現在仍未成立**；但更重要的是它**問錯了問題**——併發其實已經發生（本次評估自己就撞上一次 `X1`），只是那種併發 PR 治不到（§4.3）。故一併改為可機械判定的三條（§5）。

## 1. 證據基線

全部為 2026-09-04 本次實測，指令與結果並列，不接受憑印象。

| # | 事實 | 取得方式 | 結果 |
| --- | --- | --- | --- |
| E1 | CI 從未因 PR 觸發過 | `gh run list --limit 100 --json event,headBranch,conclusion` | 共 **12** 次 run，**全部** `event: push`／`headBranch: main`；`pull_request` 事件 **0** 次 |
| E2 | 全 repo 只開過一個 PR，且存活 16 秒 | `gh pr list --state all`、`gh pr view 1` | PR #1（MYL-31）`createdAt 05:23:21Z` → `mergedAt 05:23:37Z` |
| E3 | `on: pull_request` 比那個 PR 還晚出現 | `git log -- .github/workflows/foundry-lint.yml` | 首次進 repo 於 `c1d020b`，`2026-09-03T19:02:19+08:00`（＝`11:02:19Z`），比 PR #1 合併晚約 5.6 小時 |
| E4 | 沒有任何合併保護 | `gh api repos/.../branches/main/protection`／`.../rulesets` | 前者 `404 Branch not protected`；後者 `[]` |
| E5 | 只有一個 git 身分 | `git log --format='%an <%ae>' \| sort \| uniq -c` | **89 顆 commit 全部** `AugustusHsu <jimhsu11@gmail.com>` |
| E6 | GitHub 禁止自我核可 | GitHub Docs「Approving a pull request with required reviews」 | 原文：「Pull request authors cannot approve their own pull requests.」同頁另載：「Repository owners and administrators can merge a pull request even if it hasn't received an approving review.」 |
| E7 | main 的推進有 45% 不是 merge | `git log --first-parent [--merges\|--no-merges] main` | first-parent 51 顆＝merge **28** ＋ 直接 commit **23**（45%）；其中 **7** 顆是 `docs/publish-reviews/` 的發佈審查記錄 |
| E8 | main 的 CI 現正連三紅 | `gh run list`、`gh run view --log-failed` | `13:51:59Z`／`13:52:40Z`／`14:04:20Z` 三次 `failure`，全部倒在 `handbook-stamp` |
| E9 | 同一份檢查在本機是綠的 | `make check` | `EXIT=0`（79＋15＋34 項測試全過） |
| E10 | 工單鏡像尚未存在 | `gh issue list --state all` | GitHub issue **0** 筆——T-2 雙軌鏡像還沒建 |
| E11 | 沒有任何程式讀 `.foundry/config.yml` | protocol 第 4、7 節「違反」段自載 | 「目前沒有任何程式讀取或驗證 `.foundry/config.yml`」 |

## 2. 第一題：PR 能擋住什麼是工單鏈擋不到的？

要分兩個維度回答，因為兩者的答案相反。

### 2.1 審查維度：零增量，且這不是程度問題

`R5` 的否決理由是「PR 只是同一審查的第二份表單，會製造兩份真相」。計畫 v5 預期這條在工單改掛
GitHub（T-2 鏡像）後會弱化。實測結果是**沒有弱化，反而被封死**：

- 由 `E5`，本 repo 只有一個 git 身分，agent 全部以使用者身分 commit。
- 由 `E6`，GitHub 禁止 PR 作者核可自己的 PR。

於是只有兩種配置，都不產生審查增量：

| 配置 | 結果 |
| --- | --- |
| ruleset 要求 ≥1 個核可 | **永久死鎖**——唯一存在的身分就是開單者，沒有第二個帳號能按核可 |
| 不要求核可 | PR 淪為狀態檢查的載體，Verdict 仍然出自 Code Reviewer 的工單鏈；**「第二份表單」的原始批評原封不動成立** |

即使將來補上第二個 GitHub 帳號，`E6` 的後半句仍在：repo owner 可以在沒有核可的情況下直接合併。
所以 PR 的審查強制力，對本 repo 唯一的人類而言**是可以繞過的**——它擋不住任何一件工單鏈擋不住的事。

### 2.2 機械維度：有增量，但比看起來小

這裡 PR 確實能擋住工單鏈擋不到的東西：**把 `make check` 從合併後移到合併前**。目前的防線是

1. `.pre-commit-config.yaml`：本機、commit 時擋，但可用 `--no-verify` 繞過——而 protocol 第 7 節
   「手冊同步戳記」的第 3 條處置**明文授權**了這條繞道；
2. `.github/workflows/foundry-lint.yml` 的 `push: branches: [main]`：**合併後**才跑，紅燈直接落在 main 上。

`E8` 證明第 2 條的失效模式不是假想：main 此刻正紅著，三次失敗橫跨 13 分鐘，期間工作照常推進，
**沒有任何人或 agent 因此停下**。工單鏈確實擋不到這件事——沒有哪張工單的 AC 是「CI 要綠」。

但增量的**尺寸**要誠實估：

- `E9` 顯示同一份檢查在本機是綠的，也就是說 pre-commit 已經攔下了絕大多數內容型漂移。
- 真正漏過去的只有兩條路：**`--no-verify` 的授權繞道**，以及**本機與 CI 環境不一致**。
- `E8` 這次紅燈屬於後者，而且成因與規則無關：workflow 用 `fetch-depth: 1`，淺 clone 裡
  `git rev-parse --verify <戳記 sha>^{commit}` 必然失敗，於是四章戳記全被判成「不是本 repo 的 commit」。
  這同時讓 workflow 自己的註解——「CI 紅燈一定能在本機重現，不會出現『只有 CI 會壞』的情況」——**變成假的**。

於是機械維度的增量收斂成一句：**PR 能擋下的，是「`--no-verify` 繞道後直接合併進 main」這一種情形**；
而 `E8` 這種環境分歧，PR 不但擋不下，還會**反過來把所有合併鎖死**（見 §4.2）。

### 2.3 T-2 鏡像對這一題的影響：是未來式，且是單向的

計畫的「工單改掛 GitHub 後理由弱化」有兩個前提現在都不成立：

- `E10`：GitHub issue 現為 0 筆，鏡像尚未建立。
- 計畫 §3 自載的硬約束：**「指派 Paperclip 工單＝喚醒 agent，GitHub issue 不會」**，且真相面與喚醒面
  仍是 Paperclip。鏡像是**單向展示面**。

推論：即使 T-2 落地，PR 上的審查留言也**叫不動任何 agent**。把審查搬到 PR 會製造一個
「寫得下、但沒人會被通知」的介面——那比「兩份表單」更糟，是一份**看起來有人在看、實際沒有**的表單。

## 3. 第二題：與 `R4`／`GAP-3` 怎麼交互？

**答案是正交，而且「順便關掉 `GAP-3`」是採用 PR 的錯誤理由。**

`R4` 裁定 `push.main_push` 的 schema 維持只允許 `user`；`GAP-3` 是其代價——本 repo 依 `P1`
授權「合併回 main 後 push origin 由執行者自行」，這件事**寫不進設定檔**。

表面上 PR 像是解法：若 main 只能經由合併 PR 前進，就沒有人「push main」了，`push.main_push: user`
於是字面成立。這個推論有三個破口：

1. **身分沒變，決定者沒變。** agent 用同一個 token 按下 merge，main 仍然是被 agent 推進的。
   把 `git push origin main` 改名成「點一下合併」不改變誰做的決定——`GAP-3` 會從**被記載的缺口**
   變成**被掩蓋的缺口**，比現況差。現況至少 `known-drift` 寫著它、下一個人讀得到。
2. **唯一能讓它變真的機制是死的。** 要讓合併真正需要「使用者」，得靠 ruleset 要求核可，
   而 `E5`＋`E6` 已證明那條路是死鎖，且 owner 可繞過。
3. **`GAP-3` 根本不在這條軸上。** 由 `E11`，沒有任何程式讀取 `.foundry/config.yml`，
   `push.main_push` 被改掉不會有任何反應。`GAP-3` 是**驗證器缺口**，不是流程缺口；
   要關它得寫一個 config 驗證器，PR 做不到這件事，也不需要 PR。

**結論**：`R5` 與 `R4`／`GAP-3` 互不影響。採用 PR 不會關掉 `GAP-3`，維持否決也不會加深它。
任何以「順便讓設定檔說真話」為由重提 PR 的提案，前提是錯的。

## 4. 第三題：一單一分支＋實質單人開發下，PR 是不是只是多一次點擊？

**比一次點擊多——多的部分還都是成本，不是收益。**

### 4.1 「多一次點擊」有直接量測值

`E2`：本 repo 史上唯一的 PR #1，從開啟到合併存活 **16 秒**。它沒有承載任何審查——當時
`on: pull_request` 甚至還不存在（`E3`）。那 16 秒就是「多一次點擊」的實測值。

### 4.2 三項結構成本

| 成本 | 依據 |
| --- | --- |
| **45% 的 main 推進不是 merge** | `E7`：51 次 first-parent 推進裡 23 次是直接 commit。要嘛全部改走 PR（把 23 次 16 秒點擊制度化），要嘛開例外——而例外要靠人判斷「這顆算不算例行」，**閘門就不再是機械的** |
| **發佈流程被插進一次往返** | `E7` 的 23 顆裡有 7 顆是 `docs/publish-reviews/` 的 APPROVED 記錄。protocol 第 7 節要求該記錄**先在 main 上**，`scripts/publish-handbook.sh` 的證據閘門才放行；而該節明定這段**沒有使用者介入點**（`P2`）。把它塞進 PR，等於在一條刻意設計成全自動的流程中間加一道人工關卡 |
| **閘門要先可信才能有約束力** | `E8`＋`E9`：檢查此刻對 main 是紅的、對本機是綠的。若今天就開啟必要狀態檢查，**每一次合併都會被一個環境假陽性擋死**。順序只能是「先修 CI，再談 PR」，不能反過來 |

另有一項不在成本表但要記：`E4` 顯示沒有分支保護也沒有 ruleset，所以「規則要求走 PR」目前是
**純自律**條款——`【自律】` 而非 `【機械】`。要拿到機械執行力，得由使用者去 repo 設定開啟必要狀態檢查
（`H6` 平台權限之外／`P3` 級的動作），這件事 agent 做不到，也不該替使用者決定。

### 4.3 重啟條件未成立——但它問錯了問題

原條件「多人／多 agent 真併發寫 code」按字面**未成立**：`E5` 顯示只有一個身分。

但更值得記下的是：**併發其實已經發生**。本 repo 的 workspace 是共用的，`known-drift` 第 5 節的
`X1`（commit 落到別人的分支）、`X2`（發佈互蓋）都真的踩過。**本次評估自己就撞上一次**——
開工時 `HEAD` 還在 `main`，準備建分支時已被併行的 MYL-39 run 切到 `feat/MYL-52-publish-docs`
（兩者當時同 commit、工作區乾淨，故無損失）。

關鍵在於：這種併發 **PR 治不到**。`X1` 發生在**共用工作目錄的 checkout 時刻**，`X2` 發生在
**發佈推送時刻**，兩者都在合併之外；PR 是合併時刻的閘門。所以

> 「本 repo 已經有併發了」**不構成**採用 PR 的理由。

真正會讓 PR 有意義的併發，是**兩個獨立身分在各自的 clone 上改同一批檔案**——那才需要合併前的
第三方檢視。這正是 §5 把重啟條件改寫成身分數量的原因。

## 5. 結論與重啟條件

**維持否決**（2026-09-04，MYL-53）。

否決的是「**把 PR 定為合併的必經路徑**」。不否決的是：需要時個案開 PR（如 PR #1）仍然可以，
`on: pull_request` 觸發器**維持原狀不必移除**——它零成本，且在下述條件成立時就是現成的地基。

原條件「多人／多 agent 真併發寫 code」不可判定，改為下列**三選一**，滿足任一即重開評估：

| # | 重啟條件 | 判定指令 |
| --- | --- | --- |
| `R5-a` | main 近 90 天出現 ≥2 個 git 作者身分 | `git log --since=90.days --format=%ae main \| sort -u \| wc -l` ≥ 2 |
| `R5-b` | repo 出現 owner 以外具 write 權限的協作者 | `gh api repos/AugustusHsu/agent-foundry/collaborators --jq '[.[] \| select(.permissions.push)] \| length'` ≥ 2 |
| `R5-c` | CI 已可信（§6 缺陷修復）之後，main 仍在 30 天內出現 ≥3 次 `push` 事件的 CI 紅燈 | `gh run list --limit 100 --json event,headBranch,conclusion,createdAt` |

`R5-a`／`R5-b` 對應「審查維度出現真實對象」；`R5-c` 對應「機械維度的缺口修了成因仍復發」。
三條都不成立時，重提 PR 需要提出本報告未涵蓋的新論據，不得只援引「別人都這樣做」。

## 6. 附帶發現：main 的 CI 正紅著（不在本單範圍，另循 `D1` 回報）

- **現象**：`E8` 三次 `failure`，全部倒在 `handbook-stamp`，訊息為四章戳記 sha `8433b97`
  「不是本 repo 的 commit」。`E9` 顯示同一檢查在本機通過，`8433b97` 在本機是合法 commit。
- **成因**：workflow 用 `fetch-depth: 1`，淺 clone 只有 tip 一顆 commit 物件，
  `check_handbook_stamp` 的 `git rev-parse --verify <sha>^{commit}` 因此必然失敗。
  workflow 註解寫「fetch-depth: 1 就夠」是 MYL-36 P8 當時的正確判斷，
  但 MYL-44 新增的 `handbook-stamp` **需要 git 歷史**，兩者相撞。
- **判定**：`D1`（成因工單 AC 正確、實作未達成），成因工單為 **MYL-44**，
  依 `D1` 應退回原單而非開新單；MYL-44 已結案，由 Scrum Master 重開。
- **本單不修**：修它要改 `.github/workflows/foundry-lint.yml`，落在本單「明確不做：不動 CI 設定」。
- **影響本報告的結論嗎？** 不。它同時是「合併後才擋」的實例（支持 PR）與「閘門不可信時不能有約束力」
  的實例（反對現在採用 PR），兩相抵銷後，§5 的判斷不變。

## 7. 回寫反悔錄

依 AC 3，本次評估的日期與結論已回寫 [`known-drift.md`](../../standards/known-drift.md) 的 `R5` 條目，
包含「維持否決」與 §5 的三條可判定重啟條件，避免下一輪從零重來。
