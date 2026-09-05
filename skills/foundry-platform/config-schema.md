# `.foundry/config.yml` schema

依 MYL-9 HLD §2.3 定案（repo 歸檔本：`docs/features/cross-platform/HLD.md`，下文所有「HLD §x」均指該檔）。本檔是專案層 Foundry 設定的唯一 schema 權威；範例見 `config.example.yml`。檔案位置固定：專案根目錄 `.foundry/config.yml`，進版控。

寫入者：`foundry-init`（S4）首次產生；`foundry-gates`（S3）經使用者確認後改 `gates` 段。**agent 不得未經對應 workflow 或使用者指示直接改本檔**——gates 與 push 的值都是使用者裁定的授權邊界。

## 頂層結構

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `foundry` | 整數 | ✅ | schema 版本，目前固定 `1`。讀取者遇到不認得的版本應停下報錯，不得猜著解析。 |
| `platform` | 枚舉 | ✅ | `github`｜`gitlab`｜`local-md`｜`paperclip`。決定載入哪份 adapter 對照文檔（`adapters/<值>.md`）。再新增平台時在此補枚舉值。⚠️ `gitlab` 的 adapter 已全覆蓋八個執行層動詞，但**尚未在真的 GitLab 專案上實跑過**（見 `adapters/gitlab.md` 附錄 B），且 `foundry-init`／`foundry-adopt` 的平台問卡還沒納入它——現在填這個值等於自己走一次首跑驗證。 |
| `mirror_platform` | 枚舉 | ─ | 對外可見面的鏡像平台，值域同 `platform`（MYL-39）。語意：**執行與喚醒仍在 `platform`，工單另單向鏡像到此平台供外部閱讀**。**整段缺席＝不鏡像**，同 `model_routing` 的「缺席＝未啟用」——是預設狀態，不是設定缺漏。 |
| `platform_options` | 物件 | ─ | adapter 專屬選項，鍵為平台名。省略時各 adapter 用下述預設值。 |
| `gates` | 物件 | ✅ | 三個抽象關卡的核可設定（HLD §4）。 |
| `push` | 物件 | ✅ | push 權限設定（HLD §5）。 |
| `model_routing` | 物件 | ─ | 模型供應商路由（MYL-36）。**整段缺席＝路由未啟用**，全隊都用執行環境的預設供應商——這是預設狀態，不是設定缺漏。 |
| `docs` | 物件 | ─ | 文檔投影（MYL-39）：來源目錄、主閱讀面、精裝站。**整段缺席＝不投影**——手冊仍在版控內，只是沒有任何機械產生的閱讀面。 |

## `platform_options`

（HLD §2.3 未列本段；為 adapter 實作所需的補全，選填、有預設，屬設計缺漏補寫而非變更。）

| 欄位 | 型別 | 預設 | 說明 |
| --- | --- | --- | --- |
| `platform_options.github.project_title` | 字串 | `Foundry` | GitHub ProjectV2 的標題，adapter 據此查 project 編號。 |
| `platform_options.github.project_owner` | 字串 | `@me` | project 擁有者（org 專案填 org 名）。 |
| `platform_options.github.mirror_since` | 字串 | ─ | **只在鏡像模式下有意義**（MYL-54）：鏡像從這個 `issue_ref` 起算（含本身），之前的單不對帳。缺席＝全部納入。存在的理由是啟用鏡像時舊單通常沒有回填，而回填是批次對外動作、要另外核可；沒有這條界線，對帳一啟用就把所有舊單報成漏建，於是整項檢查在第一天就被當成雜訊。**調低它等於宣告那些舊單已回填**——回填做完才改，不是想少看幾條紅燈就改。 |
| `platform_options.gitlab.url` | 字串 | `https://gitlab.com` | GitLab 實例位址。**自架實例必填**——GitLab 不像 GitHub 只有一個站，adapter 的每一條指令都要顯式帶位址，不能靠 CLI 猜。 |
| `platform_options.gitlab.project_path` | 字串 | ─ | 完整命名空間路徑（`group/subgroup/project`）。省略時 adapter 無從組出 API base（路徑要整段 URL-encode），`gitlab` 模式下視為缺必填。 |
| `platform_options.gitlab.tier` | 枚舉 | `free` | `free`｜`premium`。決定四個動詞走哪條路徑（scoped label 互斥、`blocks` 關聯、epic／Roadmap 的可用性）。**填的是探測結果，不是期望值**——探測方式見 `adapters/gitlab.md`「版本分岔」。填錯不會報錯，只會讓 `update_status` 靜靜留下兩個 `status::` label。 |
| `platform_options.local-md.id_prefix` | 字串 | `FND` | 工單編號前綴（`<前綴>-<序號>`）。設定後不得變更——已發出的 issue_ref 會失效。 |
| `platform_options.paperclip.company_id` | 字串 | `${PAPERCLIP_COMPANY_ID}` | 公司 UUID。省略時取執行環境的同名環境變數；label 是公司層資源，adapter 據此查建。 |
| `platform_options.paperclip.project_id` | 字串 | ─ | 專案 UUID。省略時 `create_issue` 需由呼叫端指定，`list_issues` 不做專案過濾。 |

## `mirror_platform`

（MYL-39 計畫 v5 §3「T-2 雙軌鏡像」定案。）

**這一段管的是「可見面在哪」，不是「工單在哪」**——後者是 `platform`。設這欄的唯一理由是一個硬約束：
執行層平台的工單頁面不見得對外開放，而對外開放的那個平台**叫不動 agent**（例：GitHub issue 不會喚醒
Paperclip agent）。把喚醒面搬過去，工單就叫不動人；不搬，外面就看不到進度。單向鏡像是這兩者之間唯一不製造第二份真相的解。

| 語意 | 規定 |
| --- | --- |
| 方向 | **單向，`platform` → `mirror_platform`**。鏡像端唯讀：在鏡像端改狀態、留言、指派一律不回寫，且會在下一次同步被覆蓋。 |
| 誰是真相 | 永遠是 `platform`。對帳發現兩邊不一致時修鏡像端，不修來源端。 |
| adapter 選項 | 沿用 `platform_options.<鏡像平台>`，不另開結構。 |
| 怎麼鏡像 | 由 `adapters/<鏡像平台>.md` 的「鏡像模式」一節規定（三個時機、對應標記、對帳欄位）。 |

合法性（違反時同下方總則，整檔拒用）：

- 值不在 `platform` 的枚舉內 → 非法。
- 值等於 `platform` → 非法。鏡像到自己沒有語意，多半是複製貼上錯誤。
- 值指到的 adapter **沒有「鏡像模式」一節** → 非法：讀取者無從得知該怎麼鏡像，**不得自行推導**一套出來。目前只有 `github` 有。

寫入者：使用者，或經使用者核可的計畫（同 `model_routing`）。**且不得早於鏡像實際可用就先寫**——
設定檔宣稱有鏡像、實際沒有，比整段缺席更糟：讀者會以為外面看得到，於是不去同步。

## `gates`

三關卡對應 HLD §4.1：A 規格核可、B 方案核可、C 對外／不可逆核可。每關的值是**核可者**，枚舉：`user`（發互動卡等使用者）｜`ceo`｜`tech-lead`。

| 欄位 | 型別 | 必填 | 約束 |
| --- | --- | --- | --- |
| `gates.spec_approval` | 枚舉 | ✅ | 關卡 A。預設 `user`。 |
| `gates.design_approval` | 枚舉或物件 | ✅ | 關卡 B。預設 `user`。可寫成物件啟用小單跳過（見下）。 |
| `gates.external_actions` | 枚舉 | ✅ | 關卡 C。**只允許 `user`，不可調降**——讀取者遇到其他值視為設定檔非法，整檔拒用並報錯。 |

`design_approval` 的物件形式：

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `approver` | 枚舉 | ✅ | 同上枚舉。 |
| `skip_below` | 枚舉 | ─ | `small`。工單掛 `size:small` label 時跳過本關；未掛 size label 視為 `medium`、不跳過。目前僅支援 `small`（`medium` 以上跳過等於實質關閉關卡，不開放）。 |

關卡的執行語意（何時發卡、卡在哪個狀態）由 protocol 第 4 節修訂承載（S2 範圍）；本檔只定義欄位。

## `push`

| 欄位 | 型別 | 必填 | 約束 |
| --- | --- | --- | --- |
| `push.branch_push` | 枚舉 | ✅ | `user`｜`tech-lead`。feature／docs 分支 push＋開 PR 的權限。`tech-lead` 表示 Tech Lead 可自動執行（HLD §5，經問卷同意）。 |
| `push.main_push` | 枚舉 | ✅ | **只允許 `user`**——push main、force-push、tag 發佈永遠要使用者當下同意。讀取者遇到其他值同 `gates.external_actions` 處理：整檔拒用。 |

## `model_routing`

規則本體在 foundry-protocol 第 8 節「供應商維度」（`M4`～`M6`）；本段只定義欄位。流程與盤點腳本見 `skills/foundry-model-routing/SKILL.md`。

**這一段管的是「哪一家的模型」，不是「工單放在哪」**——後者是頂層的 `platform`。兩條軸互相獨立，別混。

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `model_routing.default_provider` | 字串 | ✅（有本段時） | 未於 `roles` 指定的角色一律用這家。值為供應商 id，須存在於 `tools/model-routing/probe_providers.py` 的登記表。 |
| `model_routing.roles` | 物件 | ─ | 角色 → 供應商 id 的覆寫。鍵用標準角色名（同 `role:*` label 的後綴，如 `developer`、`code-reviewer`）。 |
| `model_routing.review_provider_distinct` | 布林 | ─（預設 `true`） | 是否強制 `M4`（實作與審查異廠）。設 `false` 等於放棄本段的主要目的，需在對應工單留言記錄理由。 |

寫入者：**使用者，或 `foundry-model-routing` 在使用者核可該次指派之後**（`M6`：供應商切換屬公司層設定變更，agent 不得自行決定）。與本檔其他段落同規則——agent 不得未經核可直接改。

合法性（違反時同下方總則，整檔拒用）：

- `default_provider` 或 `roles` 的值不在供應商登記表 → 非法。**不得**自動 fallback 到別家：靜默換一家跑，產出風格會變而沒有人知道為什麼。
- `review_provider_distinct` 為 `true`（或省略）卻把 `developer` 與 `code-reviewer` 指到同一家 → 非法。這是設定檔自相矛盾，可機械判定，不留給執行期才發現。
- 指定的供應商在本機不可用（盤點腳本回報未安裝／未登入）→ **不是設定檔非法**，是環境問題：停下並依 `M5` 發卡，不要改設定遷就環境。

## `docs`

（MYL-39 計畫 v5 §2「D-3 三層投影」定案。）

三層，**只有第一層可以人手改**：

| 層 | 欄位 | 誰能改 |
| --- | --- | --- |
| 源頭 | `docs.source` | 人／agent，每張工單改的都是這一層 |
| 主閱讀面 | `docs.primary` | **沒有人手改**，機械投影 |
| 精裝面 | `docs.mirror_site` | **沒有人手改**，機械投影，可選 |

**投影不是第二份真相——但這句話要成立，得靠偵測撐著。** 投影前先確認投影面的現況就是上一次投影推上去的
內容，不是就**停下並回報，不得覆蓋**。少了這道偵測，同步會靜靜蓋掉別人在 wiki 上的編輯，而那個人不會
知道發生過什麼；那時「投影面沒有人手改」就只是一句宣稱，不是事實。

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `docs.source` | 字串 | ✅（有本段時） | 來源目錄，相對 repo 根、以 `/` 結尾。這是唯一可寫的真相。 |
| `docs.primary` | 枚舉 | ✅（有本段時） | 主閱讀面：`wiki`（投影到平台 wiki）｜`repo`（不投影，讀者直接讀 repo 內的 `source`）｜`none`（不對外提供閱讀面）。 |
| `docs.link_policy` | 枚舉 | ─（預設 `absolute`，MYL-52 增訂） | 來源裡指向 repo 內部路徑（`skills/`、`templates/` 之類）的相對連結，投影時怎麼處理：`absolute`＝改寫成指回 repo 的絕對 URL；`plain`＝拆為純文字。**投影面的頁面是平的，這些相對路徑在那邊一定失效，所以沒有「原樣保留」這個選項。** |
| `docs.mirror_site` | 物件 | ─ | 精裝站（mkdocs 之類）。**整段缺席＝不建精裝站。** |
| `docs.mirror_site.enabled` | 布林 | ✅（有本段時） | 顯式 `false`＝設定保留、暫時關閉；與整段缺席的差別只在於保不保留下面幾欄。 |
| `docs.mirror_site.trigger` | 枚舉 | ✅（`enabled: true` 時） | 何時重建：`tag`｜`merge`（合併進 main 即發）｜`manual`（人工執行）。 |
| `docs.mirror_site.tag_pattern` | 字串 | ✅（`trigger: tag` 時） | tag 名的 glob，例 `handbook-v*.*.*.*`（配 protocol `V4` 的四碼版本號）。要換版本號形狀的專案改這一欄，`V4` 本身不開旋鈕。其他 trigger 下本欄無意義，讀取者忽略。 |

合法性（違反時同下方總則，整檔拒用）：

- `primary: wiki` 但**投影面的宿主平台沒有 wiki** → 非法。宿主的判定：`mirror_platform` 有值時取它，否則取 `platform`；目前 `github` 與 `gitlab` 有 wiki，`local-md` 與 `paperclip` 皆無。⚠️ 兩個有 wiki 的宿主**載體不同**（頁面層級、首頁與側欄命名、錨點演算法都不一樣），各自的轉換規則寫在自己的 adapter，別互相照抄。
- `source` 指到不存在的目錄 → 非法。這條可機械判定，不要留到發佈當下才炸。
- `enabled: true` 而 `trigger` 缺席，或 `trigger: tag` 而 `tag_pattern` 缺席 → 缺必填，非法。

寫入者：使用者，或經使用者核可的計畫。`foundry-init` **目前不詢問本段**，導入的專案預設整段缺席
（＝只有源頭、沒有投影面）；要投影時再補寫。

**怎麼執行**（MYL-52 增訂）：本段只宣告「投影到哪」，實際動作是抽象動詞 `publish_docs`
（`SKILL.md` §3.9）。載入哪份對照文檔由**宿主平台**決定，判定方式同上面的合法性規則
（`mirror_platform` 有值取它、否則取 `platform`）——例如宿主是 `github` 時，
`primary: wiki` 與 `mirror_site` 兩個面的具體指令都在 `adapters/github.md` 的 `publish_docs` 一節。
上面那句「投影前先確認現況就是上次推上去的內容」在該節有具體的比對依據，不是原則宣示。

⚠️ 本段只宣告**已開通的管道**。開通投影面本身（啟用 wiki、新建公開 repo、開 Pages）
是關卡 C（`gates.external_actions: user`，不可調降），不因為寫進本段而獲得授權。

## 合法性總則

- 未知欄位：忽略並警告（向前相容），但不得依未知欄位改變行為。
- 缺必填欄位、枚舉值非法、或違反上述「只允許 `user`」約束：整檔視為非法，停止依賴本檔的操作並回報，不得帶預設值硬跑。
- 本 schema 變更（加欄位、加枚舉值）走 CEO 提案＋使用者核可（protocol 第 9 節規範修訂流程），並遞增 `foundry` 版本號於不相容變更時。`mirror_platform` 與 `docs` 皆為選填且缺席＝關閉，舊設定檔照舊合法，屬相容變更 → `foundry` 維持 `1`。
