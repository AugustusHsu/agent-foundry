# 審查報告：MYL-90 清掉「軸 A 沒有動詞」的過期宣稱：foundry-init／foundry-adopt 四處

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-90 |
| 分支 | `feat/MYL-90-stale-axis-a-claims` |
| 審查範圍 | 第 2 輪（複審）。本輪標的＝`8f358ef..cfae578`，`2 files changed, 7 insertions(+), 3 deletions(-)`；全單累計 `main...HEAD` 兩顆、`2 files changed, 31 insertions(+), 11 deletions(-)` |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |

> 本輪依角色規範**對著第 1 輪瑕疵清單逐項驗**（留言 `739030d1` §3 三項），不重新全面審查。
> AC1～AC3 的四個標的第 1 輪已逐句核對過且本輪未再變動（`git diff 8f358ef..cfae578` 不含那四處），
> 結論沿用。AC6 因基底移動而重驗，見下。

## 0. 機械層（第 1 層）

| 指令 | 結果 |
| --- | --- |
| `make check` | **exit 0**。`--selfcheck` 13 項全綠（含 `mirror-recon`），測試 175／15／34／107 四組 OK |
| `git diff --name-only main...HEAD` | 只有 `skills/foundry-init/SKILL.md`、`skills/foundry-adopt/SKILL.md`，無夾帶別單的檔案 |
| `git log --oneline main..HEAD` | 兩顆，皆 gitmoji ＋繁中標題，符合第 7 節 |

⚠️ **`make check` 第一次跑是紅的，而紅的原因不在本單的 diff**。詳見 §2「正確性」下的說明與 §5。

**基底移動的補驗**：審查期間 MYL-89 併入 main（`e2358e4`），本分支的基底 `107bdaf` 因此落後 5 顆，
而 MYL-89 新增了第 14 項自檢 `selfcheck-names`——**本分支自己跑的 13 項不含它**。
依「看證據不看宣稱」在隔離 clone（`clone --shared`，不動共用 workspace）實驗合併：

```
git merge origin/main   → 乾淨，無衝突
--selfcheck             → 14 項全綠（mirror-recon 因隔離 clone 無 GitHub remote 而 ⏭，符合預期）
unittest discover       → Ran 185 tests, OK
```

無衝突的原因可查證：`selfcheck-names` 的四個抄寫點是 `Makefile`／`.pre-commit-config.yaml`／
`CLAUDE.md`／`AGENTS.md`（`foundry_lint.py` 的 `SELFCHECK_COPY_SITES`），與本單改的兩份 skill 零交集；
`git diff --name-only 107bdaf origin/main` 與本單檔案清單取交集為空。

## 1. AC 逐條核對

| AC | 結果 | 證據（自己驗的） |
| --- | --- | --- |
| AC1 `foundry-init` 兩處改寫 | ✅ | 第 1 輪已逐句核對（`:43-51`、`:142-146`）。本輪 `git diff 8f358ef..cfae578` 未觸及這兩處，結論沿用 |
| AC2 `foundry-adopt` 兩處改寫 | ✅ | 同上（`:74-77`、`:131-135`） |
| AC3 與三份權威一致、四處不貼罐頭 | ✅ | 同上。本輪新增的三處**不複寫分岔內容、只指向來源**，因此不引入新的一致性風險 |
| ~~AC4／AC5~~ 作廢 | ✅ | `git diff --name-only main...HEAD` 仍只有兩份 skill；`skills/foundry-protocol/` 與 `docs/handbook/` 一字未動，`handbook-stamp` 綠 |
| AC6 `--selfcheck` 全綠、`make check` 過 | ✅ | 本分支 `make check` exit 0（13 項）；合併到現行 main 後 14 項全綠、185 測試 OK。**達成過程見 §5 的鏡像補做** |

## 2. 四維檢查

- **正確性**：第 1 輪 §3 的三處**全數修正，且指標都解得開**——這是本輪的關鍵，因為三處的修法一律是
  「指過去、不複寫」，指錯就等於沒修。逐一驗證：

  | # | 修正處 | 指標 | 解析結果 |
  | --- | --- | --- | --- |
  | 1 | `foundry-init:231-233`（§5 步驟 5 第 4 點待辦） | 「§2 第 5 點最後一顆 bullet」 | §2 標題在 `:73`、第 5 點在 `:123`、其最後一顆 bullet 是 `:142-146`（下一行 `:147` 已是編號第 6 點）⇒ **精確命中** |
  | 2 | `foundry-init:248-249`（§6 驗收自查第 3 條） | 「§2 第 5 點」 | 同上目標 ⇒ 命中 |
  | 3 | `foundry-adopt:170-172`（§6 驗收自查 M4 那條） | 「§3.4 第 3 點」 | §3.4 標題在 `:111`、第 3 點在 `:115`、其最後一顆 bullet 是 `:131-135`（下一行 `:136` 已是 `- **查證**`）⇒ 命中 |

  第 1 輪給的判準是「`paperclip` 的專案照新正文做完，這個勾要打得下去」——現在打得下去：
  `:142-146` 要求報告寫「還要跑一次 `provision_team`」，`:248` 要的正是「依 `ai_platform` 列出對應的組織待辦」。
  三處另加的護欄句（「『待人工建立的 agent』兩支都不對」）也確實堵住了我當時點名的失效路徑
  ——純指標救不了「為了打勾而把清掉的宣稱寫回報告」，要有一句明說舊講法不對。

  **重跑第 1 輪的掃描指令**，兩份檔內剩下的命中全是中性提及或護欄句本身：

  ```
  grep -n "人工建\|待人工\|建立的 agent\|建 agent\|建人\|建團隊\|建出來\|建成員" \
    skills/foundry-init/SKILL.md skills/foundry-adopt/SKILL.md
  ```

  → `init:33`／`:43`／`:48`／`:106-110`／`:123`／`:142`、`adopt:123` 中性；
  `init:249`／`adopt:172` 是護欄句（**刻意保留字面，因為那一句的作用就是否定它**）。**無殘留的過期宣稱**。

  再依 R8（MYL-93 裁定的新慣例：訂正宣稱要連下游一起 grep）往外掃一層
  `grep -rn "組織待辦\|org.yml.*待辦\|待辦.*org.yml" --include=*.md skills/ docs/handbook/ templates/`：
  只命中本次改的三行，`docs/handbook/`／`templates/` 無同類下游。`foundry-adopt` 沒有 init §5 那種
  「報告內容清單」小節（`grep -n 報告 skills/foundry-adopt/SKILL.md` 逐條看過），所以 adopt 側只有一處下游，
  與第 1 輪清單一致，**沒有第四處漏網**。

  **第一次 `make check` 紅的三條與本單 diff 無關**，我逐條追過來源：`MYL-93`（本單上一輪的
  溢出收尾，Tech Lead 已在留言 `61ecf300` 揭露 GraphQL 額度爆掉未完成）、`MYL-89`／`MYL-91`
  （MYL-89 合併結案 ⇒ MYL-91 自動轉 `in_progress`，鏡像未跟，屬 MYL-89 審查報告 §5 自己記下的接續義務）。
  三條都是**看板狀態漂移**而非 diff 造成，我已就地補齊，處置與證據見 §5。

- **規格符合度**：本輪三處不新增規範內容、只建立指向，與 `foundry-ai-platform` §6、`foundry-platform` §8、
  `config-schema.md` 的 `ai_platform` 欄位段無新的接觸面。不動 `provision_team` 規格本體的邊界守住。
  `.foundry/` 未動（同類第 5 處 `.foundry/config.yml:14` 依規留給使用者裁定，本單正確排除）。

- **安全性**：無發現。純文件改動，不含指令、憑證、對外動作。

- **可維護性**：本輪修法值得記一筆——`foundry-init:232` 明文寫「**這裡不再寫一份**：同一組分岔寫兩處，
  改的時候只會改到一處」，與 `CLAUDE.md` 對「第二份規範拷貝」的立場一致，也與 `foundry-adopt:89`
  既有的「此處不重列清單」同型。**修的方式本身沒有製造下一個 MYL-90**。
  唯一可再收斂的是一個位置限定詞，見次要建議 1。

## 3. 重大瑕疵清單

**無。** 第 1 輪 §3 三項全數修正並經上表逐項驗證；本輪未發現新的重大瑕疵。

## 4. 次要建議

1. **`foundry-init:232` 的「最後一顆 bullet」是位置限定詞，建議收掉**。同一個目標在 `:248` 只寫
   「§2 第 5 點」——粒度不一致，而較細的那個是會漂的：往第 5 點尾端再補一顆 bullet，`:232` 會**靜默**
   指到新的那顆，`:248` 不受影響，於是兩處對同一目標的解析從此分岔。改成內容定位
   （例：「§2 第 5 點談『不等於團隊建好了』那顆」）或直接對齊 `:248` 都行。
   這是 MYL-77 複審「序位引用改內容引用」的同一條，只是粒度較粗、可見度較高，**不擋結案**，
   也不值得為它單開一單——下次動到那一段時順手改即可。

2. **給後續補做鏡像的人一個更正**：MYL-89 審查報告 §5「接續義務」把 MYL-91 的鏡像寫成 `#24`，
   實際是 **`#25`**（`#24` 是 MYL-90 自己的鏡像，Status 本來就對）。照那行字做會改錯一格。
   本輪補做時已按 project item id 實際查對，未沿用該行；**該報告已在 main 上，屬凍結交付物，不追改**。

3. 第 1 輪次要建議 1（`8f358ef` 訊息裡「§2 步驟 3」的位置筆誤）——**處置正確**。已推上 origin 的 commit
   改訊息＝force push＝`P3` 使用者專屬，在 `cfae578` 訊息裡訂正而不 amend 是對的。我當時寫「下一輪反正要
   amend，順手改掉即可」是我沒把 `P3` 想進去，這一點是 Tech Lead 判斷正確。

4. 第 1 輪次要建議 2（機械化判定不成立、改記為慣例）已由 Tech Lead 轉出成 MYL-93，
   Scrum Master 當場裁定立案 ⇒ `known-drift` 新增 `R8`、實作單 MYL-94（`backlog`）。**不夾帶進本單**，
   處置符合角色規範「順手發現的新需求回報 Scrum Master」。

## 5. 分支收尾檢查

- **分支狀態**：**已合併並刪除**。本報告 commit 進 `feat/MYL-90-stale-axis-a-claims` 後
  `--no-ff` 併入 `main`、push（`P1`），刪本地分支與遠端分支（`P1` 明文含「刪已合併的遠端分支」）。
  合併後在 `main` 上重跑 `make check` 覆驗。
- **手冊發佈四步：不觸發**。`git diff --name-only main...HEAD` 兩檔皆不在 `docs/handbook/`，
  protocol 未動，`handbook-stamp` 綠。AC4 作廢後這一格就沒有標的，工單描述的判定屬實。
- **本輪就地補做的鏡像同步（三格，皆非本單 diff 造成）**：`make check` 的 `mirror-recon` 紅在
  MYL-93／MYL-89／MYL-91，而 AC6 要求綠，所以不補做就驗不了 AC6。三格都是 Projects v2 的
  Status 欄，走 GraphQL `updateProjectV2ItemFieldValue`：

  | 來源單 | 鏡像 | 改法 | 出處 |
  | --- | --- | --- | --- |
  | MYL-93 `done` | `#27` | `Todo` → `Done` | Tech Lead 留言 `61ecf300` 附的指令，額度恢復後照跑 |
  | MYL-89 `done` | `#23` | `In Progress` → `Done` | MYL-89 審查報告 §5 記下的接續義務 |
  | MYL-91 `in_progress` | `#25` | `Todo` → `In Progress` | 同上（該報告誤寫成 `#24`，見次要建議 2） |

  補做後 `mirror-recon` 綠（來源端 37 張、鏡像端 26 張），`make check` exit 0。
  **上一輪擋住這件事的 GraphQL 限流已恢復**——但 Tech Lead 記的那條踩點仍然成立且值得留著：
  `gh api rate_limit` 回報的 graphql 額度與 Projects v2 自己那套點數制**是兩套**，
  前者顯示 `5000/5000` 時後者照樣可以在擋，別拿它判斷寫不寫得進去。

## Verdict

**✅ APPROVED**

第 1 輪退件的三處下游全部跟上，且三個指標我逐一解析到具體行號、都命中預期目標；
護欄句堵住了我當時點名的失效路徑（為了打勾把清掉的宣稱寫回報告）。
關鍵詞掃描與 R8 的下游掃描各跑一輪，兩份檔內無殘留過期宣稱、外圍無第四處漏網。
基底移動後在隔離環境驗過合併乾淨、14 項自檢與 185 測試全綠。
MYL-79（T7）現在讀 `foundry-init` 不會再讀到否認它自己要做的事的句子——本單的開單目的達成。

—— Code Reviewer
