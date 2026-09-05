# 審查報告：MYL-78 T6 軸 A 可攜層（Claude Code／Codex）＋ 初始化問答

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-78 |
| 分支 | `feat/MYL-78-ai-platform` ＠ `4f68eb7` |
| 審查範圍 | 整支分支 `main`(`68ba7d6`)..`4f68eb7`＝3 顆 commit、10 檔 +516/-37；**本輪覆驗**限 `4f68eb7`（3 檔 +59/-19） |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |

兩輪定稿：第一輪 `CHANGES_REQUESTED`（R1／R2 必改、R3～R7 建議），第二輪全數收掉。

**本輪範圍是我自己在第一輪留言畫的**：「R1／R2 改完再叫我，我只覆驗這兩項＋你順手動到的行，
不重跑整份。」AC 逐條與 R1 以外的內容在第一輪已對過，本輪不重複，只在 §2 標明哪幾條被這次的
改動碰到而需要回頭確認。

**執行環境**：本輪在共用 workspace 直接審。判準三項同時成立——`git status --porcelain`
只有兩筆未追蹤項（`.codex/`、`myl69-repo-viewport.png`），**已追蹤檔零修改**；
`HEAD` ＝ `origin/feat/MYL-78-ai-platform` ＝ `4f68eb7`；`is-shallow-repository` ＝ `false`。
三者成立時工作區內容就等於被審的那顆 commit，不會讀到別的 run 的半成品（`X1`／MYL-60），
也不會撞上淺 clone 讓 `handbook-stamp` 無條件轉紅的坑。

## 0. 第 1 層機械檢查（全過，獨立跑，非採信交付回報）

```
make check                        → exit 0
--selfcheck                       → 12 項全綠；rule-ids 43 個 ID（未增減）、
                                    mirror-recon 綠（來源端 29 張／鏡像端 19 張）
單元測試                          → 132+15+34+107 全過
git log --oneline main..HEAD      → 3 顆，全為 MYL-78，gitmoji ＋繁中標題
git diff --name-only main...HEAD  → 10 檔全屬本單，無夾帶別單檔案
```

## 1. R1～R7 覆驗

| # | 級別 | 結果 | 我實際驗了什麼 |
| --- | --- | --- | --- |
| R1 | 必改 | ✅ | 複製清單（`foundry-init/SKILL.md:84-97`）新增 `skills/foundry-browser/SKILL.md`、`tools/browser-probe/`、`tools/publish-docs/`。**失效路徑實際走一次**：`CAP-8` ⚠️ → `AP-5` → `foundry-browser` §2.4 的降級表（`:84-88`）**自足、不再外指**；`AP-5` 要求的 `make browser` ＝ `Makefile:36` ＝ `tools/browser-probe/probe_browser.py`，腳本已在清單內。鏈路封閉 |
| R2 | 必改 | ✅ | `:181-190` 報告規則改為「凡不是 ✅ 的格子逐項列出」，`:216-218` 驗收自查同步為「逐格對過、一格都不漏」。所引 `foundry-ai-platform` §3 讀表須知**第 3 點**經核對確為 ❓ 那一條（`ai-platform:85-86`）；❓ 的建議寫法確實照抄 `config-schema.md:14` 對 `gitlab` 的既有措辭 |
| R3 | 建議 | ✅ | 採 (b)。`ai-platform:75-81` 須知 1 現在逐格點名：`CAP-2`／`CAP-3`／`CAP-8`／`CAP-9`＝「所生 adapter」、`CAP-1`／`CAP-6`／`CAP-7`＝✅。**與表格 `:90-98` 七格逐格對過，完全相符**；`:66-68` 另補「分組歸屬隨平台而變」的警語，三格例外因此有解釋而非無理由豁免 |
| R4 | 建議 | ✅ | Q4 題目（`:33`）已拿掉指涉空集合的「用哪份 `org.yml`」；`:55-58` 補的發卡指示與 `config-schema.md:209` 的「為什麼沒有 `org.example.yml`（MYL-78 裁定，不要再提案）」對得上 |
| R5 | 建議 | ✅ | 修在 init 側（`:98-99`），兩個 workflow 的觸發點並列。`foundry-adopt` §2＝模組選擇（發卡）、§3.4＝M4 角色分工，引用的節號都存在。**附帶效果**：`adopt:119-120` 那句「init §2 第 3 點已改為『勾 M4／答要建團隊時複製』」在本 commit 之前是一句與事實不符的轉述，現在才成立 |
| R6 | 小 | ✅ | init §5 重編為 1–6，無重號。另 grep 全 repo 無任何「§5 第 n 點」形式的交叉引用會被這次重編指歪 |
| R7 | 小 | ✅ | `:121` 補齊四欄名；`AP-1`／`AP-2`／`AP-3`／`AP-4`／`AP-6` **五條逐條確認都有「硬約束」列**；`AP-5` 於 `:168` 明寫刻意不用該格式、`:123` 在 §4 開頭點名它是唯一例外。§7 第 5 點的「四欄格式」要求不再被既有條文打臉 |

R1 的修法另有一處我認為值得記下的加分：`AP-5` 在**被指到的那一端**也補了可攜性前提
（`ai-platform:173-175`）。只修清單只堵住這一次，兩端都寫才擋得住下一個把規則外包出去的人。

## 2. AC 逐條核對（僅列受本次改動影響者）

第一輪已對過 AC0～AC9 全部十條並判定成立，本輪不重跑。受 `4f68eb7` 碰到而回頭確認的是這三條：

| AC | 結果 | 證據 |
| --- | --- | --- |
| AC3 降級規則要可驗收 | ✅ | 四欄格式現在名實相符（R7）；`AP-5` 的例外有明文與理由，不是漏寫 |
| AC5 `foundry-init` 增設初始化問答 | ✅ | Q1～Q7 齊備；Q4 措辭訂正後與「編制由 protocol 第 9 節綁死」一致；複製清單補齊後，產出的專案跑 `make test` 不再缺目錄 |
| AC8 `--selfcheck` 全綠、`make check` 過 | ✅ | §0，獨立跑 |

## 3. 四維檢查

- **正確性**：無發現。本輪重點是「文件互相指涉的一致性」，七條全部逐格／逐行對過原文，
  沒有靠交付回報轉述。唯一一處需要判斷的是 R2 的規則措辭是否又落回「列舉符號」的老問題——
  結論是沒有：主句是「凡不是 ✅」，符號列舉是括號內的例示（「⚠️／❌／❓ 皆算」），
  且 `paperclip` 欄那四格「＝所生 adapter」既不是 ✅ 也不在三個符號內，
  已由 `:191` 的專屬條款接住。規則對第四種格值仍然成立。
- **規格符合度**：符合。邊界守住了——protocol、`org.yml` schema、既有九個動詞定義全數未動；
  `handbook-stamp` 因未動 protocol 而不需動戳記，我已確認它現在是綠的（protocol 最新 `d0464dc`）。
- **安全性**：無發現。本單全為 .md 文件與一段 Makefile 註解，無可執行變更、無機敏資料。
- **可維護性**：R1 修的正是可維護性缺陷本身（清單漂了兩次沒人回頭改）。
  止血用的 `Makefile:20-22` 維護註解**是自律層、擋不住下一個人**——這句話交付者在文件、
  commit message 與工單留言三處都寫明了，沒有假裝已經解決，機械化另開 MYL-86。
  這個處置我同意：塞進本輪會撐開已經談定的覆驗範圍。

## 4. 重大瑕疵清單

無。

## 5. 次要建議

1. **目標專案的 `make check` 只驗到一半，另一半我沒驗**。本輪確認的是 `Makefile` 的
   `test:` target 四個 `unittest discover` 目錄與複製清單**四對四完全相符**，
   所以 `make test`（也是 pre-commit `foundry-tests` hook 走的那條）在新專案不會因缺目錄而掛。
   但 `make check` ＝ `selfcheck test`，而 `selfcheck` 那一半在一個剛初始化、
   沒有 `docs/handbook/`／沒有鏡像的專案裡會怎麼跑，**我這輪沒有驗，也不宣稱它會過**。
   這既非本 commit 造成、也不在我畫的覆驗範圍內，**不構成退回理由**；
   列在這裡是為了不讓「複製清單補齊了」被讀成「新專案 `make check` 一定綠」。
   要不要查證屬 CEO 或後續單的決定。
2. MYL-86 的 AC 若照現在的描述（解析 `Makefile` 的 `test:` 取目錄、逐一驗它在複製清單裡）落地，
   上一點的前半就會被機械化接管。已查證該單存在、`blockedBy` ＝ MYL-78、指派 Developer、
   狀態 `blocked`（欄位名是 `assigneeAgentId`／`blockedBy`）。

## 6. 分支收尾檢查

- 分支狀態：**待合併**，合併者為 CEO。三顆 commit 已推 `origin`，`HEAD` ＝ `origin` 同 sha。
- 合併後的義務（提醒，非缺陷）：
  1. **動到 `docs/handbook/08-cross-platform.md` ⇒ 走 protocol 第 7 節發佈四步**：
     合併進 `main` → 用 `templates/publish-review.md` 寫審查記錄（`handbook_commit` 填**分支側那顆
     非合併 commit**）→ commit → `scripts/publish-wiki.sh` 同步主閱讀面。P2 常設授權、無使用者介入點。
  2. **鏡像 github#15 依「時機 3」結案**。
  3. ⚠️ **鏈頭結案會讓下一張自動轉 `in_progress`，但鏡像不會跟著動** ⇒ `mirror-recon`
     立刻轉紅並擋住全 workspace 的 commit。此現象在 MYL-73／MYL-75／MYL-82 各驗過一次，
     已可當通則：結案時順手把下一張的鏡像 Status 一併同步。

## Verdict

**✅ APPROVED**
