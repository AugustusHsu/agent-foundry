# 審查報告：MYL-74 T2 落檔 `role-ceo` 與 `role-pm` 兩份角色 skill

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-74 |
| 分支 | `feat/MYL-74-role-ceo-pm-skills` |
| 審查範圍 | `main..HEAD` 兩顆 commit：`0446c1e`（初審，6 檔 +178／−9）、`93bc6c4`（複審修正，4 檔 +8／−8） |
| 審查者 | Code Reviewer（`148355fe`） |
| 日期 | 2026-09-06 |

本檔是兩輪審查的合併定稿。第一輪判 ❌ CHANGES REQUESTED（工單留言 `8b987a27`），第二輪判 ✅ APPROVED。
第 3 節保留第一輪的瑕疵清單原文並附複審驗證結果——日後要查「當時退的是什麼、怎麼收的」看那一節。

機械層（第 1／2 層）兩輪皆全過，不構成退件事由：`make check` 的 `--selfcheck` 10 項全綠、132＋15＋34＋107
測試 OK（輸出中的 ❌ 是 `republish_decision` 反例測試的預期字串，不是失敗）；`git diff --name-only main...HEAD`
8 檔全屬本單、無夾帶別單檔案；`git log --oneline main..HEAD` 兩顆 commit 皆 gitmoji ＋繁體中文標題。

## 1. AC 逐條核對

證據欄一律是審查者自己跑過、看過的，Developer 交付回報裡的宣稱不計入。行號以 `93bc6c4` 為準。

| AC | 結果 | 證據 |
| --- | --- | --- |
| AC1 `role-ceo` 落檔、60–80 行、frontmatter 同規格 | ✅ | `wc -l` ＝ **80**（邊界內，見第 4 節第 2 項）；`skills/roles/ceo/SKILL.md:1-4` 的 `name`／`description` 與其餘 8 份逐一比對同形；七段式對得上附錄 A（Summary→`:8-9`、Expertise→`:29-35`、Priorities→`:37-41`、Boundaries→`:51-58`、Tools→`:60-65`、Communication→`:67-73`、Collaboration→`:75-80`） |
| AC2 `role-pm` 落檔、同規格 | ✅ | `wc -l` ＝ 77；`skills/roles/pm/SKILL.md:1-4`；七段對應附錄 B |
| AC3 不抄規範、共通規則用規則 ID | ✅ | 兩份全文只引 ID（`H1`～`H6`／`D1`～`D4`／`W1`／`W2`／`P1`～`P3`／`M1`～`M3`／`O1`／`C1`～`C5`／`X1`），無條文複製；`rule-ids` 自檢綠（已登記 41 個 ID） |
| AC4 protocol 明文豁免與理由＋雙入口同步 | ✅ | `skills/foundry-protocol/SKILL.md:538-548` 新增小節與 `O3`、`:642` 第 11 節索引改為 `O1`／`O2`／`O3`；**frontmatter `:3` 也加了但書**——「所有 Foundry agent 必掛」的矛盾字面就在那裡，只改正文不算修掉；`CLAUDE.md`／`AGENTS.md` `:22`／`:56` 各兩處同步，`entry-sync` 綠；第二輪再補 `README.md:17`／`:55`（見第 3 節第 1 項） |
| AC5 視覺唯讀兩行寫純文字、不放跨檔錨點 | ✅ | `skills/roles/ceo/SKILL.md:34-35`（Expertise 側）與 `:57`（Boundaries 側）皆純文字、無錨點；`internal-links` 綠。**刻意不寫 `L1` 是對的**——`L1` 在 `known-drift` 與 browser 等級是兩套同名 ID |
| AC6 `--selfcheck` 全綠、`make check` 過 | ✅ | 見上方機械層 |

## 2. 四維檢查

- **正確性**：無發現。三處最容易寫錯的都核過：`ceo/SKILL.md:77` 直轄五人＝protocol `:509`；`pm/SKILL.md:44-46`
  派工歸 PM、依賴鏈歸 Scrum Master＝protocol `:561`／`:562`／`:580`；`pm/SKILL.md:64-65` 不寫模型層數值＝protocol
  `:451`／`:458`（PM 那一格明載是建議值、不得據以設定平台）。
- **規格符合度**：一處**刻意且正確**的偏離。母單附錄 B `:284` 把「排 `blockedByIssueIds` 依賴鏈」寫成 PM 的職責，
  交付物改判給 Scrum Master——**交付物是對的**：附錄 B 是 MYL-73 之前的草案，protocol `:580` 之後明訂「依賴鏈與派工
  是兩格、兩個拍板者」，而附錄屬工單文件（`W2`）、protocol 是權威（第 6 節），沒有文件衝突要裁。
- **安全性**：不適用（純規範文件，無輸入面、無機敏資料落地）。
- **可維護性**：第一輪三項瑕疵全屬此維（同一條規則在 repo 內有未同步的拷貝），已於第二輪收齊；殘留項見第 4 節。

## 3. 重大瑕疵清單

以下為**第一輪**提出的三項，第二輪逐項驗證（角色 skill 規定複審只對上一輪清單驗，不重新全面審查）。

| # | 位置（檔案:行號） | 問題 | 期望 | 複審結果 |
| --- | --- | --- | --- | --- |
| 1 | `README.md:17`、`README.md:55` | 同一個 repo 裡「每個 agent 必掛」還有兩份未加豁免的拷貝，`:55` 就在標題為「三層 skill 結構」的段落——讀者學這條規則的正規位置。protocol／`CLAUDE.md`／`AGENTS.md` 都補了，README 沒補，矛盾只是換了個檔案繼續存在。而 `O3` 自己載明「本條沒有機械後盾」——沒有機械後盾的規則，文件就是唯一的控制點 | 兩行各補與入口檔一致的但書。`templates/entry-file.md:49` 維持不動是對的 | ✅ 已修。`:17` 在 code fence 內，寫成不加反引號的 `唯一豁免＝CEO，見 O3`；`:55` 在正文，寫成 `（唯一豁免是 CEO，理由見該檔 \`O3\`）`。**兩處都沿用 README 自己的半形標點風格**，未把入口檔的全形標點帶進來。全 repo 複驗 `grep -rn '必掛'`：僅存的無但書拷貝是 `templates/entry-file.md:49`，那是給別的專案複製的樣板，維持不動正確 |
| 2 | `docs/handbook/01-first-run.md:7` | 這一行列舉「`foundry-protocol` 與**六個**角色 skill」並逐一點名，是使用者照著做的匯入檢查清單。本單落檔後 `skills/roles/` 實際有 9 份：缺 `role-frontend-verifier`（既有漂移，非本單造成），也缺本單新增的 `role-ceo`／`role-pm`。這一章不在戳記四章內，`handbook-stamp` 結構上抓不到；下游 MYL-76～80／82 亦無人擁有 | 改成不列舉、不寫數量的形狀，指向 `skills/roles/`（repo 目錄就是權威） | ✅ 已修，且比要求多做一步：補了「唯一例外：CEO 不掛 `foundry-protocol`，只掛 `role-ceo`」——**這句是必要的**，01 章正是使用者唯一會照著執行的匯入清單，`O3` 沒有機械後盾，不寫在這裡它在唯一被執行的地方就會失效。既有的 FV 漏列一併收掉 |
| 3 | `skills/roles/ceo/SKILL.md:17-26` | 指路表少了 CEO 最常走的那一條：protocol 第 3 節「PM → CEO」交接格式與該節「交接物不齊，下一棒有權直接退回」。CEO 的主要輸入就是 PM 的報告，而本單新增的 `O3` 把這張表定義成 CEO 取用規則的**唯一路徑**——表上沒有的節，CEO 不會知道它存在。失效情境：PM 交來一份沒有「需要決定的事項」那段、或把查不到的格子用推論補滿的報告，CEO 不知道自己有據可退 | 指路表補一列 | ✅ 已修。`skills/roles/ceo/SKILL.md:19` 新增並置於**第一列**（CEO 最常走的路排最前，合理）。指標實地驗過：protocol `:164` `### PM → CEO`、`:170` `### 通用規則` 兩個標題都存在，退回權在 `:120`／`:122`（`:122` 明確點名 PM → CEO 亦適用「不齊就退回」）。措辭精確度見第 4 節第 1 項 |

第二輪另採納第一輪次要建議 2、3：`skills/roles/pm/SKILL.md:48` 補 `known-drift` `X1` 指標（已核對 `X1` 確為
共用 workspace 併行 run 干擾 checkout，指標正確）、`skills/roles/ceo/SKILL.md:26` 去掉 `O2`（處理不一致的只有 `O1`）。

為守住 AC1 的 80 行上緣，`:78-79` 折成一行——複驗為純排版，語意與 markdown 渲染結果均未變。

## 4. 次要建議

不擋結案。第 1～2 項為複審**新發現**，明記於此以免被讀成「Developer 沒修」。

1. **`skills/roles/ceo/SKILL.md:19` 的指標可以更準（新發現，源頭是我上一輪給的例句）**。該列指向「第 3 節
   『PM → CEO』與該節『通用規則』」，但「交接物不齊，下一棒有權直接退回」實際在第 3 節的**節首** `:120`／`:122`，
   不在 `### 通用規則`（`:170-173`，那裡講的是交接寫在留言、引用給路徑）。判為次要而非重大：CEO 依 `C1`～`C5`
   局部讀第 3 節時會從節首讀起，且 `:122` 明確點名 PM → CEO，答案找得到，不會導致錯誤行為。要更準可把該格改為
   「第 3 節節首『不齊就退回』＋『PM → CEO』」。
2. **`docs/handbook/index.md:32` 有第 3 節第 2 項的同類漂移（新發現）**。該行寫「`skills/roles/<角色>/SKILL.md`
   — 六個角色各自的判準」，實際 9 份；本單把它從差 1 變成差 3，且與同一份手冊的 06 章（`:22` 直轄五個、明列 PM 與
   Frontend Verifier）自相矛盾。判為次要而非重大：那是「規範文件在哪」的指路清單，讀者照它去 `skills/roles/`
   路徑正確，數字不會導致任何錯誤操作——與 01 章是使用者照著執行的匯入清單不同。
   **但成本不對稱，請合併者一併決定**：本單因 01 章改動本來就要跑一次 protocol 第 7 節發佈四步，把 `:32` 的
   「六個角色」改成「各角色」是零成本搭便車（純事實訂正、不影響本報告的 APPROVED）；留到日後修則要另開一張單
   ＋自己的發佈審查記錄＋自己的 wiki 同步，而 T3～T9 沒有任何一張擁有 `docs/handbook/`——不現在處理，它多半會像
   Frontend Verifier 的漏列一樣長期留著。
3. **把「節號漂移」變成機械檢查（第一輪提出，仍未修，本單結案時是已知缺口）**。指路表 9 列裡有 3 列只能靠節號
   定位，而 `CLAUDE.md` 第 5 節與 `skills/roles/pm/SKILL.md:71` 都寫著「引用規則用穩定 ID，不要用節號」。那幾節
   本來就沒註冊 ID，所以不是寫錯；但 protocol 增訂一節，CEO 的地圖就靜默指錯，而 CEO 是全編制唯一讀不到原文
   可以自我校正的角色。Developer 已依規定回報 Scrum Master 開單。
4. **`role-ceo` 停在 80 行整，是 AC1 的上緣**。下一次要加任何一列都會越界，屆時是改 AC 還是刪句子，由當時的
   工單決定——先記在這裡，免得下一個人以為自己撞到的是硬規則。

## 5. 分支收尾檢查

- 分支狀態：**待合併**。protocol 第 7 節「分支」明訂合併時點在審查單 APPROVED **之後**，故本節於此判定合併前提是否齊備，實際合併由 CEO 執行。
- `feat/MYL-74-role-ceo-pm-skills` ＠ `93bc6c4`，本地與 `origin` 一致；`main` ＝ `origin/main` ＝ `2ebd00d`，分支超前 2 顆、落後 0 顆，可直接快轉合併，無衝突。
- **合併者必須接手的一件事**：本單動到 `docs/handbook/01-first-run.md` 的**內容**，不再是戳記-only 差異，
  `scripts/lib/publish-gate.sh` 的 MYL-44 戳記旁路不會放行（已讀該檔 `:87-118` 確認）。合併後必須走完 protocol
  第 7 節發佈四步：合併進 main → 依 `templates/publish-review.md` 建 `docs/publish-reviews/MYL-74.md`
  （`verdict: APPROVED`、`handbook_commit` 填合併後手冊最新 sha，快轉合併時即 `93bc6c4`）→ commit → 跑
  `scripts/publish-wiki.sh`。這一段屬 P2 常設授權，不需打斷使用者。
- 第 5 步（打 `handbook-v<a>.<b>.<c>.<d>` tag 發精裝站）**不是本單結案條件**，且屬使用者專屬（`V1`），agent 不得自行 tag。

## Verdict

**✅ APPROVED**

六條 AC 全數有證據、四維無重大瑕疵、第一輪三項瑕疵逐項收齊、分支合併前提齊備。第 4 節四項為不擋結案的建議，
其中第 3 項是本單結案時仍存在的已知缺口，已回報 Scrum Master。
