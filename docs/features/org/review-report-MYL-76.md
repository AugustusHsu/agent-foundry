# 審查報告：MYL-76 T4 可攜性級 2：`.foundry/org.yml` ＋ `org-sync` 自檢

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-76 |
| 分支 | `MYL-76-org-yml`（commit `ca9b22e`，已推 origin） |
| 審查範圍 | `main...HEAD` 共 9 檔、+824/-12：`.foundry/org.yml`（新）、`foundry_lint.py`、`test_foundry_lint.py`、`config-schema.md`、`known-drift.md`、`CLAUDE.md`／`AGENTS.md`、`Makefile`、`.pre-commit-config.yaml` |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |

## 0. 機械層（第 1 層）

三條全過，不進退件路徑：

| 指令 | 結果 |
| --- | --- |
| `make check` | `--selfcheck` 12 項全綠（含新增的 `table-shape`、`org-sync`）；`unittest discover` 155＋15＋34＋107 項全過 |
| `git diff --name-only main...HEAD` | 9 檔，全屬本單範圍，未夾帶別單檔案 |
| `git log --oneline main..HEAD` | 單一 commit，gitmoji ＋繁體中文標題 |

收件檢查：三段式交付回報齊（留言 2026-09-05T20:55:36）、commit 訊息草案在、分支上只有本單變更。

## 1. AC 逐條核對

證據一律為本次自行執行的結果；Developer 回報中的宣稱不計入。

| AC | 結果 | 證據 |
| --- | --- | --- |
| AC1 schema 寫進 `config-schema.md`，欄位含 id／`title`／`reports_to`／`skills[]`／`permissions[]`／`model_tier`／`ai_platform`，體例與既有四段一致 | ✅ | `config-schema.md:192-258` 新增 `## .foundry/org.yml（組織宣告）`：頂層欄位表、角色欄位表、`permissions` 值域與平台欄位對應表、「誰能改」、「合法性」。七個欄位全數在表內。體例比對既有四段——`gates`（77）／`push`（96）／`model_routing`（103）／`docs`（123）皆為 `##` 級、皆有「寫入者」段，新節同構（`:247` 有「寫入者」）。H1 正名為「`.foundry/` 設定檔 schema」並在導言劃出 `config.yml`／`org.yml` 的分界（`:1-6`） |
| AC2 依 T1 定案組織填出 9 名（現有 8 ＋ PM） | ✅ | `.foundry/org.yml` 9 個 role。逐一比對 protocol `SKILL.md:507-518` 組織圖：CEO 直轄五（Product Analyst／PM／Scrum Master／Frontend Verifier／Tech Lead）、Tech Lead 轄三（Developer／Code Reviewer／QA Engineer），`reports_to` 全數對得上。`ai_platform: paperclip` 與 `config.yml:15` 同值。**`permissions[]` 另以平台實況交叉核對**：`GET /api/companies/{cid}/agents` 回 8 名，全部 `canCreateSkills: true`、`canCreateAgents: false`，只有 CEO `canAssignTasks: true`——與宣告完全一致（PM 未建，符合 AC7） |
| AC3 `org-sync` 比對 org.yml ↔ §9 組織圖 ↔ §8 分層表 | ✅ | `foundry_lint.py:1076-1233`。三個方向都實測打過：見下方「反例實測」15 組 |
| AC4 每項檢查配一個擋得住的反例測試 | ✅ | `test_foundry_lint.py` 新增 `TableShapeTest`(6)／`ParseOrgTest`(5)／`OrgSyncTest`(11)。兩項新檢查各有多個擋得住的反例；**我另外自建 15 組反例逐分支打**，全部如預期報紅（見下節） |
| AC5 入口檔 §6 自檢描述同步、兩份逐字相同、不寫「共 N 項」 | ✅ | `CLAUDE.md:131`／`AGENTS.md:131` 同步加入「表格連續性、組織宣告」，`entry-sync` 綠＝逐字相同。全文無「共 N 項」。同一份清單散落的另兩處（`Makefile:14`、`.pre-commit-config.yaml:33`）一併更新——`grep -rn "鏡像對帳"` 全 repo 只有這四處 |
| AC6 寫明改動權、判定是否延伸自 `config.yml` | ✅ | `config-schema.md:240-251` 專節「誰能改 `org.yml`」：判定**延伸適用**並給了比 `config.yml` 更強的理由（改得動編制與權限＝自我授權，且 `org-sync` 只驗三處一致、宣告與規範一起改照樣全綠）；寫入者、改動路徑（同 §9 結構調整＝發卡提案＋使用者裁定）、規範優先於宣告（依 `O1`）三項齊備。入口檔 §2 第 4 點同步為「兩份**都**不得自行改動」 |
| AC7 寫明「應然不是實然」、`org-sync` 刻意不比對平台實況 | ✅ | 三處＋一個回歸守衛：`org.yml:6-10` 檔頭、`config-schema.md:200-206`、`check_org_sync()` docstring（`foundry_lint.py:1077-1086`），三處都用 PM 當具體例子並帶「不要順手補一個比對平台的檢查」警語；`test_不比對平台實況` 為守衛。**實測**：宣告了平台上不存在的 PM，`check_org_sync` 仍 `passed=True` |
| AC8 `--selfcheck` 全綠、測試全過、`make check` 過 | ✅ | 見第 0 節 |
| AC9 `table-shape` 偵測被空行切斷的表格續列 | ✅ | **用當年那個真缺陷回放驗證**：`git show bd3ad2f^:docs/standards/known-drift.md` → `table_breaks()` 回 `[44]`，正是 MYL-73 當時被切出表外的 `L23` 那一列。這是「不是恆真」的直接證據，不是重寫一個像的案例 |
| AC10 判定值不值得做、若不做寫進 known-drift ＋ docstring | ✅ | 判定**不做**，理由（protocol 節與手冊章非一對一，硬做對應表＝第二份人工映射）寫在 `known-drift.md:154` `GAP-6` 與 `check_handbook_stamp()` docstring（`foundry_lint.py:1260-1268`）。兩處措辭一致，且都寫明這是刻意的覆蓋範圍。判定本身有工單授權（「先判斷值不值得做」），屬 Developer 權責 |

### 反例實測（自建，非採信交付回報）

在 repo 副本上逐分支打，全部如預期報紅：

| 反例 | 結果 |
| --- | --- |
| 宣告組織圖沒有的角色（加 `Intern`） | ❌ 「宣告了 `Intern`，但 protocol 第 9 節組織圖沒有這個節點」 |
| 組織圖多一個節點、org.yml 未宣告 | ❌ 「組織圖有 `Intern`，但 org.yml 沒有宣告它」 |
| `reports_to` 與組織圖不符 | ❌ 「宣告匯報給 `CEO`，但組織圖把 `Developer` 掛在 `Tech Lead` 底下」 |
| `reports_to` 指到不存在的 id | ❌ 「既不是本檔的角色 id 也不是 `user`」 |
| `model_tier` 與 §8 不符／值域外／缺席 | ❌ 三種各自報對訊息 |
| 同一角色在 §8 出現於兩層 | ❌ 「有 2 層（高、中）都提到 `Developer`」 |
| §8 分層表標題改名（比對基準消失） | ❌ 「表的形狀變了就要一起改本檢查」——**不是靜靜通過** |
| §9 組織圖標題改名 | ❌ 同上 |
| `id` 重複／形狀不合／`title` 重複／缺 `title` | ❌ 四種各自擋下 |
| `skills: []`／`skills` 欄位缺席／路徑失效 | ❌ 三種各自擋下 |
| `permissions` 缺席／值域外 | ❌ 兩種各自擋下 |
| 缺 `ai_platform`／兩檔值不一致 | ❌ 兩種各自擋下 |
| `foundry_org: 2`（版本不認得） | ❌ 停下報錯，不猜著解析 |
| 宣告平台上不存在的 PM | ✅ 通過（AC7 要的行為） |
| 表格續列被空行切斷（含縮排在清單裡的） | ❌ 報出行號；相鄰兩張表、圍欄內示例、無分隔列的段落皆不誤殺 |

## 2. 四維檢查

- **正確性**：無重大發現。逐一驗過三個容易寫壞的地方：(a) `parse_org_tree` 的 depth 用 `len(prefix)//4`，對 `└── `／`    ├── `／`        ├── ` 三層各算出 1／2／3，正確；(b) `table_breaks` 的「新表 vs 續列」分支——相鄰兩張表不誤殺是這項檢查活得下去的前提，實測正確；(c) `parse_org` 對不支援的寫法**拋 `LintError` 而不是忽略**，與 `parse_config` 相反的設計在 docstring 裡有理由（整份都是輸入，靜靜漏掉一行等於漏檢一個角色），並配了測試。一處**訊息**瑕疵見次要建議 4。
- **規格符合度**：無偏離。AC9 字面要求「掃 `docs/` 與 `skills/` 的 `.md`」，實作 `TABLE_SCAN_DIRS = ("docs", "skills")` 逐字相符（覆蓋面觀察見次要建議 5）。AC10 授權「先判斷值不值得做」，Developer 行使該判斷並依 AC 要求把理由落在兩處，未越權。`org.yml` 的 `permissions[]` 用 Foundry 級名稱、不寫任何平台欄位名，與 `known-drift` 記載的「寫 `permissions.*`／稽核讀 `access.*`」反差正面對上。
- **安全性**：無發現。新程式只讀本 repo 內的檔案，無網路、無 `subprocess` 新增面、無使用者輸入路徑；`parse_org` 不 `eval`。授權面上有一項**正向**設計：AC6 把「agent 不得自行改」延伸到 `org.yml`，堵住「agent 改自己的編制與權限」這個自我授權破口——這是本單最實質的安全貢獻，措辭夠明確。
- **可維護性**：整體與 repo 慣例一致（常數集中在檔頭、每個判定分支各配訊息、docstring 寫「為什麼」而非「做什麼」）。三處會實際造成負擔的不一致列在次要建議 2／3／6。`ORG_TIER_ALIASES` 這則別名放寬有節制（一則、附「要加第二則之前先想清楚」的警語），且 Developer 不逕自改 protocol 的判斷是對的——第 8 節正名屬 §9 矩陣的「規範修訂」列（CEO 提案＋使用者核可），且會連帶手冊 07 章與四章戳記與一輪發佈四步，不在本單授權內。

## 3. 重大瑕疵清單

無。

## 4. 次要建議

不擋結案，Developer／合併者自行決定；1 建議由合併者順手處理，2／3 建議搭下一張單的便車。

1. **分支名缺 `<類型>/` 前綴。** `MYL-76-org-yml` 不符 protocol §7「`<類型>/<工單編號>-<簡述>`」，同鏈的 MYL-73／74 都是 `feat/MYL-7x-…`。**不退件的理由**：現在改名要刪一條**未合併**的遠端分支＝`P3` 使用者專屬，為了命名燒一張卡不划算；而合併後刪除已合併分支是 `P1`，這條偏差會隨收尾自然消失。請 MYL-77～80 沿用 `feat/` 前綴。
2. **`skills/foundry-platform/SKILL.md:153` 的檔案索引過期了**——仍寫「`config-schema.md`｜`.foundry/config.yml` 欄位說明」，但本次已把該檔正名為「`.foundry/` 設定檔 schema」並擴為涵蓋兩份檔案。這是本次改動**新造出來**的落差，一行可修。
3. **`Makefile:14` 漏了「版本號形狀」。** 這是 MYL-71 留下的既有缺漏（不是本次造成），但本次正好改到同一行卻沒順手補齊，於是四處清單有一處仍然短一項。依 MYL-74 的「零成本搭便車的純事實訂正要搭」，這格值得補。
4. **缺 `title` 時會多噴一句誤導訊息。** `foundry_lint.py:1170` 用 `len(titles) != len(by_id)` 判重複，但缺 `title` 的角色也會讓 `titles` 變短，於是實測輸出同時有「`developer` 缺必填欄位 `title`」與「有重複的 `title`」——後者是假的。改成只在真有重複鍵時報即可。
5. **`ai_platform` 在 org.yml 側沒有機械把關。** 實測 `ai_platform: banana` ＋ `config.yml` 沒有該欄 → `org-sync` 通過。docstring 說枚舉合法性歸 config-schema，但同一段程式碼裡 `ORG_MODEL_TIERS`／`ORG_PERMISSIONS` 兩個枚舉又確實寫在 Python 裡，理由對這一項不完全成立。本 repo 的 `config.yml` 有該欄所以現在擋得住，缺口只在導入的新專案（該欄選填）。自然歸屬是 MYL-85（欄位名／schema 版本自檢）。
6. **「寫入者：`foundry-init`（導入新專案時產生）」目前沒有對應的實作步驟。**（`config-schema.md:247`）`foundry-init/SKILL.md` §2 只產 `config.yml`、§2.5 只複製入口檔與閘門，全文沒有產生 `org.yml` 的一步；而 T5／MYL-77 的範圍是 `provision_team`（把宣告**套到平台**），不含「產生這個檔案」。**這一格現在沒有任何一張單承接**，請 CEO／Scrum Master 判斷是併進 MYL-77 還是另開。附帶事實：模擬一次 `foundry-init` 導入後跑 `--selfcheck`，`org-sync` 會因缺檔報紅——但**同一個模擬在 main 上也已經有 4 項紅**（`nav-sync`／`anchors`／`big-files`／`handbook-stamp`），所以這不是本次新造成的破口，是既有的「`--selfcheck` 對新專案不可攜」問題多了一項。
7. **`table-shape` 掃不到的兩類表格**（皆符合 AC9 字面，僅記錄）：根目錄的 `CLAUDE.md`／`AGENTS.md`（表格最密的兩份檔案不在 `docs/`／`skills/` 下），以及引用區塊內的表格（`> | … |` 不以 `|` 開頭，例：`docs/features/git-flow/proposal.md:142`）。要不要擴掃屬編輯判斷。
8. **`permissions[]` 的來源沒寫在檔內。** CEO 那兩格逐條註明了理由，其餘 8 名一律 `create_skills` 卻沒說依據。我已用平台 API 核對過那正是現況（8 名全 `canCreateSkills: true`），但下一個讀者看不到這件事。補一行「其餘角色為登記現況（2026-09-06 核對）」即可，體例上與 §8 對 Frontend Verifier 的「登記現況」寫法一致。

## 5. 分支收尾檢查

- 分支狀態：**待合併**。分支上只有本單一顆 commit、已推 origin、內容與 main 無衝突。
- 合併者的接續義務（照 Developer 交付回報，我逐項核過屬實）：
  1. 合併回 main 後刪除 `MYL-76-org-yml`（`P1`）。
  2. **不觸發手冊發佈四步**——本單未動 `docs/handbook/`，protocol 亦一字未改（`git diff --name-only main...HEAD` 已證）。
  3. 同步鏡像 `github#13`（現為 `OPEN`）走時機 3 結案。
  4. 鏈上下一張（T5／MYL-77）自動轉 `in_progress` 後，順手把它的鏡像 Status 改成 In Progress——前三張單（MYL-73／74／75）都踩過「鏈頭結案→下一張自動 `in_progress` 但鏡像不跟→`mirror-recon` 立刻紅擋住全 workspace」。
- 附記：工作區有兩項與本單無關的未追蹤檔（`.codex/`、`myl69-repo-viewport.png`），屬 MYL-61 的遺留待處置，未混入本 commit。

## Verdict

**✅ APPROVED**
