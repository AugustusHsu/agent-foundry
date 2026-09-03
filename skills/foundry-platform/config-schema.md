# `.foundry/config.yml` schema

依 MYL-9 HLD §2.3 定案（repo 歸檔本：`docs/features/cross-platform/HLD.md`，下文所有「HLD §x」均指該檔）。本檔是專案層 Foundry 設定的唯一 schema 權威；範例見 `config.example.yml`。檔案位置固定：專案根目錄 `.foundry/config.yml`，進版控。

寫入者：`foundry-init`（S4）首次產生；`foundry-gates`（S3）經使用者確認後改 `gates` 段。**agent 不得未經對應 workflow 或使用者指示直接改本檔**——gates 與 push 的值都是使用者裁定的授權邊界。

## 頂層結構

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `foundry` | 整數 | ✅ | schema 版本，目前固定 `1`。讀取者遇到不認得的版本應停下報錯，不得猜著解析。 |
| `platform` | 枚舉 | ✅ | `github`｜`local-md`｜`paperclip`。決定載入哪份 adapter 對照文檔（`adapters/<值>.md`）。未來新增平台（如 `gitlab`）時在此補枚舉值。 |
| `platform_options` | 物件 | ─ | adapter 專屬選項，鍵為平台名。省略時各 adapter 用下述預設值。 |
| `gates` | 物件 | ✅ | 三個抽象關卡的核可設定（HLD §4）。 |
| `push` | 物件 | ✅ | push 權限設定（HLD §5）。 |
| `model_routing` | 物件 | ─ | 模型供應商路由（MYL-36）。**整段缺席＝路由未啟用**，全隊都用執行環境的預設供應商——這是預設狀態，不是設定缺漏。 |

## `platform_options`

（HLD §2.3 未列本段；為 adapter 實作所需的補全，選填、有預設，屬設計缺漏補寫而非變更。）

| 欄位 | 型別 | 預設 | 說明 |
| --- | --- | --- | --- |
| `platform_options.github.project_title` | 字串 | `Foundry` | GitHub ProjectV2 的標題，adapter 據此查 project 編號。 |
| `platform_options.github.project_owner` | 字串 | `@me` | project 擁有者（org 專案填 org 名）。 |
| `platform_options.local-md.id_prefix` | 字串 | `FND` | 工單編號前綴（`<前綴>-<序號>`）。設定後不得變更——已發出的 issue_ref 會失效。 |
| `platform_options.paperclip.company_id` | 字串 | `${PAPERCLIP_COMPANY_ID}` | 公司 UUID。省略時取執行環境的同名環境變數；label 是公司層資源，adapter 據此查建。 |
| `platform_options.paperclip.project_id` | 字串 | ─ | 專案 UUID。省略時 `create_issue` 需由呼叫端指定，`list_issues` 不做專案過濾。 |

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

## 合法性總則

- 未知欄位：忽略並警告（向前相容），但不得依未知欄位改變行為。
- 缺必填欄位、枚舉值非法、或違反上述「只允許 `user`」約束：整檔視為非法，停止依賴本檔的操作並回報，不得帶預設值硬跑。
- 本 schema 變更（加欄位、加枚舉值）走 CEO 提案＋使用者核可（protocol 第 9 節規範修訂流程），並遞增 `foundry` 版本號於不相容變更時。
