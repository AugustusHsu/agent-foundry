# 8. 怎麼把這套流程帶到其他專案？

> 本章來自 MYL-9「跨平台開發流程」的設計與實作（S1–S5，2026-09）。Foundry 的規則與 workflow 全部是純 .md 文檔——不綁 Paperclip、不綁 Claude Code，任何 agent runtime（Claude Code、Codex 等）甚至人類，照文檔逐步執行就能跑。本章回答四件事：文檔怎麼分層、平台差異怎麼吸收、新／舊專案各怎麼導入、導入後怎麼調整被問的頻率。

## 文檔分三層：規則、執行、說明

Foundry 把「文檔」拆成三層，各有各的載體與真實來源（SSOT）；分層的目的是讓「規則」「進度」「說明」永遠只有一份真相：

| 層 | 載體 | 給誰看 | 放什麼 | 真實來源 |
| --- | --- | --- | --- | --- |
| ① 規則層 | repo 內 .md（`skills/`、`docs/`、`templates/`、`.foundry/`） | agent（人可讀） | 流程規範、角色定義、模板、專案設定 | **是**——規則與流程以此為準 |
| ② 執行層 | git 平台（GitHub Issues／Projects／Milestones／Labels）或 `.foundry/board/` | 人機共用 | 工單、進度、里程碑、看板 | **是**——執行狀態以此為準 |
| ③ 說明層 | 文檔網站（你現在讀的這本手冊） | 人類 | 使用說明、導入教學、troubleshooting | 無——永遠是 ① 的投影 |

同步只有固定方向，不能反著來：

- 規則只在 ① 編輯；③ 由發佈腳本從 ① 同步、② 的 labels／模板骨架由導入 workflow 從 ① 產生。**直接改 ③、或在 ② 上另寫規則，都會製造第二份真相**，一律禁止。
- 執行狀態只在 ② 更新；① 不保存工單進度副本。
- 跨層衝突的裁決規則寫在 `foundry-protocol` 第 6 節：規則類以 ① 為準、狀態類以 ② 為準。

## 平台差異怎麼吸收：adapter 對照表

每個人用的 git 平台不一樣，甚至可能沒有 git server。Foundry 的解法是把執行層的所有操作收斂成 **8 個抽象動詞**（開單、改狀態、留言、掛 label、設里程碑、查工單、建關聯、初始化骨架），流程規範只引用動詞、不綁平台；每個支援的平台有一份「動詞 → 具體指令」的對照文檔：

- `github` → GitHub Issues／Projects（agent 用 `gh` CLI 寫入、人類用網頁看板檢視）。
- `local-md` → `.foundry/board/` 目錄裡的 .md 檔——**沒有 git server 也能跑完整流程**，日後要上 GitHub 再走遷移（見下方 adopt）。
- `paperclip` → Paperclip 的工單與看板（agent 走 REST API）。**這就是你現在這支團隊跑的平台**——它不是「另一套流程」，而是同一套流程的其中一個 adapter。
- 之後要支援 GitLab 或其他平台，只需新增一份對照文檔，介面與流程都不動。

換平台時該動哪裡，只有三個地方，其餘一律不動（MYL-35）：**通用規則**在 `foundry-protocol`（不動）、**平台專屬的欄位與限制**在該平台的 adapter（換一份）、**專案專屬的授權邊界**在 `.foundry/config.yml`（換一份）。判準很簡單：一句規則如果換個平台就字面不成立，它就不該寫在規範裡。

專案用哪個平台，記在專案根目錄的 `.foundry/config.yml`（`devtools_platform` 欄位）；這份設定檔同時記著關卡設定（`gates` 段）與 push 權限（`push` 段），是每個專案自己的授權邊界，**agent 不得未經對應 workflow 或使用者指示直接改它**。agent-foundry 自己也有一份（`devtools_platform: paperclip`），你在 MYL-28 選定的關卡方案就記在裡面——**規範怎麼要求別的專案，這個 repo 自己就怎麼做**。

### 「平台」其實是兩個問題（MYL-82）

這個欄位原本就叫 `platform`，而「平台」這個詞在這裡一直同時指兩件事：

- **工具面**——工單、狀態、看板放在哪個服務上（`github`／`gitlab`／`local-md`／`paperclip`）。
- **AI 平台面**——agent 本身在哪裡執行、被誰喚醒（`paperclip`／`claude-code`／`codex`）。

在 agent-foundry 這個 repo 上兩者剛好都是 Paperclip，所以混用一直沒出過事；但它們是兩條互相獨立的軸——
工單可以在 GitHub、agent 卻跑在 Codex 上。一個欄位承載兩條軸，讀的人各自解讀成自己需要的那一個，
遲早會在文件裡對不上。因此欄位正名為 **`devtools_platform`**（工具面），另加選填的 **`ai_platform`**（AI 平台面），
設定檔的 schema 版本同時從 `foundry: 1` 升到 `2`。

⚠️ 這是**不相容變更**：舊設定檔裡的 `platform` 會被新的讀取者當成未知欄位丟掉，而必填的 `devtools_platform`
不存在，整份設定就此非法。要升級只需改欄位名——但要改，不會自動相容。

⚠️ `ai_platform` 這一欄**本身仍然只是宣告**：沒有任何動詞依它分派。但能力對照表已經有了（見下一節）。

規則本體：`skills/foundry-platform/`（介面 SKILL.md＋`adapters/github.md`＋`adapters/local-md.md`＋`config-schema.md`）。

### 換到 Claude Code 或 Codex，會掉哪些能力？（MYL-78）

上一節把軸分開了，但沒有回答真正要緊的那題：**換過去之後，這套流程還跑得動嗎？**

答案是「跑得動，但有代價，而且代價是可以事先查的」。`skills/foundry-ai-platform/` 把軸 A 的
**九項能力 × 四個平台**列成一張表，每格填「原生支援／降級／做不到／未驗證」，並替每個落差配一條
可驗收的降級規則——不只寫「不支援」，還寫**降級成什麼、誰負責、證據長什麼樣**。

三件事值得先知道：

- **Paperclip 的工具能力是借來的。** 它自己不提供工具，而是生一個 adapter（本 repo 是 Claude Code）去跑。
  所以「Paperclip 樣樣都行」是誤讀——它真正獨有的是**編排面**：派工、喚醒、互動卡。
- **Claude Code 在這條軸上是轉發層。** 它不持有工單、不持有喚醒機制，靠底下的工具平台或真人推動，
  與 Paperclip 不對等。
- **落差最大的兩項都在編排面。** 一是**互動卡**：在 Paperclip 上它會讓工作停下來等人回答，
  換到別的平台就只剩留言——留言不會擋住任何人，HITL 閘門於是從「擋得住」變成「靠自覺」。
  二是**指派＝喚醒**：GitHub 的 issue 指派不會叫醒任何 agent，整套「交接鏈自動往下跑」建立在這一條上，
  這是目前最不可攜的一件事。

還有一條誠實話：**「把團隊帶過去」目前任何平台都做不到。** `.foundry/org.yml` 是一份組織**宣告**，
沒有動詞會依它到平台上把 agent 建出來——可攜的是那份宣告，不是那支團隊。

導入時不必自己查這張表：`foundry-init` 的初始化問答會問「agent 要跑在哪」，
`foundry-adopt` 會盤點現況並問要不要對齊，兩者都會把落差與降級方式寫進報告。

## 新專案：跑 foundry-init（五步，一次建全套）

適用對象：還沒導入過 Foundry 的乾淨專案（沒有 `.foundry/config.yml`）。workflow 本體在 `skills/foundry-init/SKILL.md`，五步固定：

1. **問你三件事**（一張卡問齊）：用哪個平台（`github`／`local-md`）；branch push 權限給誰（`user`＝每次問你，`tech-lead`＝分支 push＋開 PR 自動——這是常設授權的給予，只有你能拍板）；同意建立哪些平台側資源（labels、milestone、看板）。
2. **產生 `.foundry/config.yml`**，並把 protocol／templates 複製進專案。
3. **建平台側骨架**：標準 label 集、milestone 容器、專案看板＋三個 view（board 狀態看板／table 全欄位／roadmap 時間軸）。github 模式用 GitHub Projects 原生功能，不自行開發外掛。
4. **設定關卡**：呼叫 foundry-gates（見下）讓你選定 A／B 關卡的粒度。
5. **產出初始化報告**：建了什麼、哪些要你手動補（平台 API 做不到的部分）、下一步指引。

你在整個過程的必答題就是第 1 步的三件事＋第 4 步的關卡選定；其餘都是照設定自動執行。

## 既有專案：跑 foundry-adopt（四模組，漸進勾選）

適用對象：已經在開發中的專案——有既存工單、分支慣例、CI，不想被一次性改造。workflow 本體在 `skills/foundry-adopt/SKILL.md`，特點是**漸進**：

| 模組 | 啟用後你得到什麼 | 依賴 |
| --- | --- | --- |
| M1 Issues | 設定檔＋流程檔＋工單基礎（labels／milestones），既有工單**選擇性**納管（掛 label 標記，不改寫歷史） | — |
| M2 Projects views | 看板三 view | M1 |
| M3 關卡制 | 三關卡生效（經 foundry-gates 由你選定） | M1 |
| M4 角色分工 | `role:*` label 慣例＋「角色 ↔ 執行者」對照表 | M1 |

流程固定四步：盤點現況（唯讀）→ 發卡讓你勾選要啟用的模組（可一次只勾一個）→ 逐模組啟用（各自獨立回退、獨立 commit）→ 之後任何時候再跑一次增開。鐵律：**絕不覆蓋既有檔案、絕不改寫既有工單的內文與歷史**。

另外 adopt 也負責 `local-md` → `github` 的遷移：board 目錄裡的工單逐張搬上 GitHub Issues，留 `MIGRATED.md` 對照表，可中斷重跑。

## 導入後想調整被問的頻率：foundry-gates

三個抽象關卡（A 規格核可／B 方案核可／C 對外核可）的介紹在[第 4 章](04-decision-points.md)。每個專案的關卡設定存在自己的 `.foundry/config.yml`，調整一律走 `skills/foundry-gates/SKILL.md` 的四步：

1. **盤點**：現在每關誰核可、實際發卡頻率。
2. **建議**：對照專案規模與歷史給建議（例如「B 關近 10 單全數照建議通過 → 建議小型工單跳過」）。
3. **確認**：現況 vs 建議差異表發卡給你選定——**agent 不能自行調整自己被管的粒度**，這步絕不跳過。
4. **寫入**：把你選定的結果寫回設定檔並留紀錄。

不變條款：**關卡 C 不可調降**（`gates.external_actions` 只允許 `user`，設定檔出現其他值會被整檔拒用）；觸發式 HITL 閘門（[第 4 章](04-decision-points.md)）不受任何 gates 設定影響。

## push 權限在其他專案怎麼算？

每個專案的 push 授權互相獨立，記在各自的 `.foundry/config.yml` `push` 段：

- `push.branch_push: tech-lead` → Tech Lead 可自動 push 工單分支＋開 PR（含 CI 觸發）；設 `user` 即收回。
- `push.main_push` 只允許 `user`：push main、force-push、tag 發佈永遠要你當下同意，無例外。
  - 你可能會想：那[第 6 章](06-org-structure.md)不是說我已經核可 P1、agent 可以自己把 main 推上去？是的，但那是你對 **agent-foundry 這個 repo** 的個別裁定，記在 protocol 的分級表裡，**設定檔沒有欄位能表達它**（MYL-35 你選了「維持硬約束不放寬」）。所以其他專案照上面這行字面走——要放寬，得你在該專案另外裁定。
- 對外發佈（網站、public repo、套件）是關卡 C，不可調降。

某個專案給過的常設授權**不會**自動延伸到另一個專案——新專案要放寬，得在該專案走 foundry-gates／關卡 C 由你另行裁定。

## 一句話總結

規則進 repo、狀態進平台、說明進網站；新專案 `foundry-init` 一次建全套，舊專案 `foundry-adopt` 想開幾個模組開幾個模組；被問太多就跑 `foundry-gates` 調粒度——但「要不要出去」（關卡 C）永遠是你的必答題。
