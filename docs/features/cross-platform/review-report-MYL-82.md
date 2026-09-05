# 審查報告：MYL-82 T9 正名遷移：`platform` → 工具軸 ＋ 新增 `ai_platform`（schema `foundry: 1` → `2`）

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-82 |
| 分支 | `feat/MYL-82-platform-rename` ＠ `475d130` |
| 審查範圍 | 單顆 commit `main`(`e52f3c5`)..`475d130`＝19 檔 +127/-65 |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |

一輪定稿，無退回。

**執行環境**：本輪在共用 workspace 直接審。判準是三項同時成立——`git status --short`
只有兩筆未追蹤項（`.codex/`、`myl69-repo-viewport.png`），**已追蹤檔零修改**；
`HEAD` ＝ `origin/feat/MYL-82-platform-rename` ＝ `475d130`；`is-shallow-repository` ＝ `false`。
三者成立時工作區內容就等於被審的那顆 commit，不存在讀到別的 run 半成品的風險（`X1`／MYL-60），
也不會撞上淺 clone 讓 `handbook-stamp` 無條件紅的那個坑。

## 0. 第 1 層機械檢查（全過）

```
make check                              → exit 0；自檢 10 項全綠、288 測試全過（132+15+34+107）
--selfcheck                             → 已登記 ID 43 個（未增減）、mirror-recon 綠（來源 27／鏡像 17）
git diff --name-only main...HEAD        → 19 檔全屬本單，無夾帶別單檔案
git log --oneline main..HEAD            → 475d130 ♻️…（gitmoji ＋繁中標題）
```

`handbook-stamp` 綠**是對的，不是漏擋**：戳記掛在 `03`／`04`／`06`／`07` 四章，
本單只動 `08-cross-platform.md`（`grep -n '最後對照 protocol' docs/handbook/*.md` 確認 08 章無戳記行），
且 `skills/foundry-protocol/SKILL.md` 在嚴格判準下零命中 ⇒ 閘門本就不該被觸發。
與 `plan` v5 §2 連帶事項第 3 點的預測一致（該點要求遷移單覆驗，此即覆驗結果）。

## 1. AC 逐條核對

| AC | 結果 | 證據 |
| --- | --- | --- |
| AC1 定名：先確認 CEO 有無轉達改名指示，否則用預設並寫明沿用舉例值 | ✅ | 拉 `GET /api/issues/MYL-82/comments` 全 3 則逐則讀完：`Mirrored-to: github#18`（登記）、blocked 期間的分流回報、交付回報。**無任何改名指示**。實作用 `devtools_platform`，且交付回報與 `config-schema.md`:176 皆寫明來源是選項標籤舉例值 |
| AC2 一次改完、不留兩套欄位名並存 | ✅ | **獨立重掃驗證**（未採信交付回報）：`grep -rnP '(?<![\w\-])platform(?![\w\-])'` 掃 `.md`／`.py`／`.yml`／`.sh`，殘留 14 行全數落在四類合法情形——AC3 保護的歷史交付物、`docs/publish-reviews/MYL-35.md`（同屬歷史證據）、`config-schema.md`:23/31/176/179 與 `08-cross-platform.md`:36/46 刻意講舊名字的沿革敘述、`test_foundry_lint.py` 四處 python 區域參數名（承載 `MirrorIssue.source_platform`，非設定欄位）。**零殘留設定欄位**。逐檔行數見下方 §4 第 1 點 |
| AC3 `docs/features/cross-platform/` 2 檔歷史交付物不回溯改 | ✅ | `git diff --name-only main...HEAD` 不含該目錄任一檔；`HLD.md`:75 的 `platform: github` 與 `gap-analysis.md`:38/41/52 原樣留存 |
| AC4 只改 `.foundry/config.yml` 三處，`gates`／`push` 一字不動 | ✅ | `git diff main...HEAD -- .foundry/config.yml`：`foundry: 1→2`、`platform:`→`devtools_platform:`、新增 `ai_platform: paperclip`。`gates`／`push` 兩段完全未出現在 diff。**第四處改動經覆核成立**——第 13 行註解「真相與喚醒面仍是上面的 platform」是對該欄位的指涉，不改即同檔內兩套名字並存，與 AC2 直接衝突；此為 AC2 強制、非擅自擴權 |
| AC5 schema 版本遞增理由與相容性影響寫進 `config-schema.md` | ✅ | `config-schema.md` 新增「版本沿革」表＋不相容論證（`1`／`2` 兩列＋為什麼不相容＋刻意不寫相容層）。論證與該檔既有「合法性總則」自洽：未知欄位忽略＋缺必填整檔非法 ⇒ 舊檔全有全無失效。**已實測驗證，見 §2 正確性** |
| AC6 手冊 `08-cross-platform.md` 同步改寫 ⇒ 觸發發佈四步 | ✅（寫）／⏭（發） | 新增「『平台』其實是兩個問題（MYL-82）」一節，含不相容警告與「`ai_platform` 目前只是宣告」警語。**四步的第 1 步是「合併進 main」，本單尚未合併 ⇒ 發佈只能在合併後做**，非本單缺漏。已列為合併者的接續義務（見 §5） |
| AC7 主版號判定並回報 CEO，不自行 tag | ✅ | 判定 `a` 位跳、下一版 `handbook-v1.0.0.0`，已寫在交付回報。**我獨立覆核 protocol `V4`（`SKILL.md`:405-406）後同意**，且成立路徑有兩條，見 §2 規格符合度。`git tag -l 'handbook-v*'` 未新增任何 tag |
| AC8 `--selfcheck` 全綠、unittest 全過、`make check` 過 | ✅ | 自己重跑一次，非採信宣稱：見上方 §0 指令輸出 |

## 2. 四維檢查

- **正確性**：無重大瑕疵。**構造反例實測過相容性論證**（AC5 的宣稱不能只看散文）：
  以舊 `foundry: 1` 設定檔（欄位仍叫 `platform`）餵給新讀取者，`cfg.get("devtools_platform", "")`
  取得空字串，再呼叫 `reconcile_mirror(src, mir, '')`，得到
  「`MYL-58`：鏡像 issue #1 的標記寫的來源平台是 `paperclip`，設定檔的 `devtools_platform` 是 ``」。
  **失效是響亮的、且訊息直接點名新欄位**，不是靜默錯判——這正是不相容變更該有的行為，
  也反證了「舊檔會整份失效」不是紙上宣稱。另確認全 repo 無任何程式讀 `foundry:` 版本號
  （`grep` 僅命中測試 fixture），故 schema 升版不會打到既有程式路徑。
- **規格符合度**：與 `plan` v5 §2／§3 一致，無偏離。三點覆核：
  ① §3 的 A 案形狀（獨立單、插在 T3 與 T4 之間）與本單交付一致；
  ② §2 連帶事項四點全數落地（動真檔、升 schema、改手冊、判主版號）；
  ③ **AC7 的 `a` 位判定我自己回讀 `V4` 原文覆核**，兩條路徑獨立成立——
  一是 `V4` 對 `a` 的明文「此判準與 `.foundry/config.yml` 的 `foundry` schema 版本**同義**」，
  二是 `a` 的一般判準「**照舊版做事會變成違規**」：照舊版手冊寫 `platform:` 的設定檔現在整份非法，
  字面即成立。兩條都指向跳 `a`，判定穩固。
- **安全性**：無發現。變更全屬文檔與設定欄位改名，無輸入驗證面、無注入面。
  `.foundry/config.yml` 未新增任何憑證或私有識別碼；手冊新增段落經檢視不含 `project_id`／`company_id`
  等私有欄位（沿用 `MYL-35.md`:31 的同一條判準）。
- **可維護性**：無發現，且有兩處**優於最低要求**：
  ① `mirror_platform`／`platform_options` 維持原名的判準被寫進 `config-schema.md` 而不只留在工單，
  下一個 agent 讀 schema 就看得到，不會順手改；
  ② `.foundry/config.yml` 與 `config-schema.md` 兩處都寫死
  「`ai_platform: paperclip` 與 `devtools_platform: paperclip` 同值是巧合不是同義」——
  這一格正是日後最容易被「化簡」掉的地方，重複寫兩次是對的。

### 對 Developer 標記之「唯一設計判斷」的裁定：`ai_platform` 設為選填 —— 同意

交付回報把這一格列為審查重點，我單獨查證後**同意**，依據不是同意其理由陳述，而是回讀上游規格：

- `plan` v5 §3 說明 T9 存在的理由是「T4 要加的那一欄名字就是 `ai_platform`，它在正名做完前不存在」。
  T4（MYL-76）要的是**這個名字有定義**，落點在 `.foundry/org.yml` 自己的欄位；
  `plan` v5 全文**未要求** `config.yml` 的 `ai_platform` 必填。設為選填不阻擋 T4。
- 反向若設必填：三家平台的能力對照、降級規則與 `foundry-init`／`foundry-adopt` 要不要多問一題
  明列在 T6（MYL-78）的 AC 內。必填等於在 T6 之前替它決定 init 問卡要改，
  屬**跨單越權**，比選填的代價高。
- 實作把語意留白寫得夠死（schema 一句「在那之前**不要拿本欄的值去改變任何行為**」＋
  手冊一句「目前只是宣告」＋config 註解一句「目前沒有任何動詞依本欄分派」），
  三處一致，不會被讀成已生效的開關。

## 3. 重大瑕疵清單

無。Verdict ✅，本節不適用。

## 4. 次要建議

不擋結案，Developer／合併者自行斟酌。

1. **行數三處不一致，數字別再被引用**。commit 訊息寫「61 行」、交付回報散文寫「65 行」、
   回報的逐檔表加總為 64。我機械重數 `git diff main...HEAD | grep -c '^+.*devtools_platform'` ＝ **65**。
   三者差異有正當來源——「改名行數」與「含新名字的新增行數」本就不同度量（例如 `08-cross-platform.md`
   是 1 行改名＋2 行新敘述）——**AC2 真正要求的逐檔清單存在且正確，故不構成瑕疵**。
   建議：已 push 的 commit 不必為此 amend，但後續文件別再轉引「61 行」這個數字。
2. **17 檔 → 19 檔的差異說明前後不一**。交付回報歸因於「MYL-73/74/75 其後併入 main」，
   但同單前一則偵察留言歸因於「我的 regex 與 `plan` v5 §2 判準不同」。
   查 `plan` v5 §2 **從未列出逐檔清單**（只給總數與三個最重的檔），因此兩種歸因都無法證實或證偽。
   建議措辭改為「`plan` v5 §2 未列逐檔清單，故以獨立重掃結果為準」——更誠實，
   且方向安全（多改的兩份 fixture 若不改，就會對著不存在的欄位斷言，正是 AC2 要防的並存）。
3. **本單暴露的機械缺口值得開新單**（依角色 skill「同一個缺陷不該被人工抓第二次」）。
   Developer 自陳風險 4：沒有任何檢查在驗設定欄位名，本次全靠人工正則掃描。
   現在多了第二格：schema 有了 `1`／`2` 兩個版本，而 `config-schema.md` 寫「讀取者遇到不認得的版本
   應停下報錯」，實際上**沒有任何程式讀那個欄位**，該條目前是純自律。
   一項 `--selfcheck` 可同時兜住兩格：斷言 `.foundry/config.yml` 的 `foundry:` 是工具認得的版本、
   且檔內不存在 `^platform:` 鍵。**這是新需求，依角色 skill 不夾帶進本報告當放行條件**——
   請 Scrum Master 評估是否開單（規模約一項自檢＋一則反例測試）。

## 5. 分支收尾檢查

- 分支狀態：**待合併**。`HEAD` ＝ `origin/feat/MYL-82-platform-rename` ＝ `475d130`，已推送、無未推提交、
  工作區無已追蹤檔修改。Code Reviewer 不執行合併（合併屬 CEO）。
- **合併者的接續義務（本單未完、不可遺漏）**：
  1. **AC6 的手冊發佈四步**（protocol 第 7 節）——合併進 main → 用 `templates/publish-review.md`
     寫審查記錄（`handbook_commit` 填合併後實際 sha）→ commit → `scripts/publish-wiki.sh` 同步主閱讀面。
     P2 常設授權、無使用者介入點，但漏做即公開面與 repo 不一致。
  2. **鏡像 github#18 依「時機 3」結案**（現況 OPEN，已查證）。
  3. **AC7 轉呈使用者**：`handbook-v1.0.0.0` 的 tag 屬 `V1` 使用者專屬，且推 tag 前要先把
     `handbook-version-tags` ruleset 切 Disabled、推完切回 Active。**不是本單結案條件。**
  4. ⚠️ **鏈頭結案會讓下一張（MYL-76，鏡像 github#13，現況 `blocked`）自動轉 `in_progress`，
     但鏡像不會跟著動** ⇒ `mirror-recon` 會立刻轉紅並擋住全 workspace 的 commit。
     此現象在 MYL-73／MYL-75 各驗證過一次，已可當通則：結案時順手把 #13 的 Status 一併同步。

## Verdict

**✅ APPROVED**
