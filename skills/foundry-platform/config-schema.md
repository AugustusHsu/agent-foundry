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

## 合法性總則

- 未知欄位：忽略並警告（向前相容），但不得依未知欄位改變行為。
- 缺必填欄位、枚舉值非法、或違反上述「只允許 `user`」約束：整檔視為非法，停止依賴本檔的操作並回報，不得帶預設值硬跑。
- 本 schema 變更（加欄位、加枚舉值）走 CEO 提案＋使用者核可（protocol 第 9 節規範修訂流程），並遞增 `foundry` 版本號於不相容變更時。
