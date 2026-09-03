# 現行流程 vs 跨平台流程：差異盤點與處置（MYL-35）

> 2026-09-03｜CEO｜對象：agent-foundry 自身的開發流程（跑在 Paperclip 上）與
> `foundry-init`／`foundry-adopt` 導入其他平台的流程之間的落差。
> 上游設計：[`HLD.md`](HLD.md)（MYL-9，已核可）。

## 0. 一句話結論

MYL-9 建好了跨平台的抽象層，**但本 repo 自己沒有站進去**：Paperclip 不在 adapter 枚舉裡，
於是規則層只好直接寫 Paperclip 的欄位名，本 repo 的關卡選定與設計文件也留在工單系統裡沒回到 repo。
本次補上 **Paperclip adapter ＋ 本 repo 的 `.foundry/config.yml` ＋ 規則層去平台耦合**，
讓「現行流程」變成「跨平台流程的一個實例」，而不是另一套。

## 1. 判準：什麼算「差異」

一條規則若**換到其他平台後字面上不成立**，就是差異。三類內容各有歸屬，錯位就是缺口：

| 內容 | 該放哪 | 換平台時 |
| --- | --- | --- |
| 全平台通用的流程規則 | `skills/foundry-protocol/SKILL.md` | 不動 |
| 平台專屬的欄位、限制、API 怪癖 | `skills/foundry-platform/adapters/<平台>.md` | 換一份 |
| 專案專屬的授權邊界（關卡、push） | 該專案 `.foundry/config.yml` | 換一份 |

這也就是使用者要的「保留彈性」的落點：**彈性放在 adapter 與 config，規則本身不留活口**。

## 2. 已經一致的部分（不動）

- 8 個抽象動詞介面、六態狀態機、標準 label 集（`foundry-platform` §2、§3）。
- 三層文檔體系與同步方向（protocol 第 6 節、手冊第 8 章）。
- 三個抽象關卡＋觸發式 HITL 閘門（protocol 第 4 節）。
- `foundry-init`／`foundry-adopt`／`foundry-gates` 三個純 .md workflow，不依賴特定 runtime。
- 六個角色 skill 的職責與交接格式——全部只引用 protocol，無平台耦合。

## 3. 缺口逐項

| # | 缺口 | 證據 | 影響 | 本次處置 |
| --- | --- | --- | --- | --- |
| **G1** | **Paperclip 不在 platform 枚舉**（根因） | `config-schema.md` 枚舉原為 `github｜local-md`；MYL-9 結案留言 AC3／AC5 明載「本 repo 平台為 Paperclip、不在 adapter 枚舉」而繞道 | 本 repo 無法用自己的抽象層管理自己；`foundry-adopt` §1.5 對本 repo 直接不可用（只能盤點、不能啟用模組） | 新增 `adapters/paperclip.md`（8 動詞全覆蓋＋平台限制表＋指令查證狀態），枚舉補 `paperclip` |
| **G2** | **規則層綁死 Paperclip 詞彙** | protocol 第 1 節「每張 **Paperclip issue** 的 description」；第 2 節「直接使用 **Paperclip** 的六個狀態」「硬依賴一律用 `blockedByIssueIds` 欄位表達」；`blocked` 的 `unblockDescriptor` 平台限制段 | 換平台後這幾條字面不成立——GitHub／local-md 都沒有 `blockedByIssueIds` | 改為抽象動詞與六態（`link_issues`／`blocked_by`／`update_status`）；Paperclip 專屬限制下沉到 adapter 的「平台限制」節；新增「平台中立原則」小節寫死三類內容的歸屬 |
| **G3** | 角色 skill 同樣綁死欄位名 | `roles/scrum-master/SKILL.md` 兩處 `blockedByIssueIds` | 同 G2 | 改為 `blocked_by` 關聯＋指向 adapter |
| **G4** | **本 repo 沒有 `.foundry/config.yml`** | repo 根目錄無 `.foundry/`；MYL-28 使用者選定的關卡方案（b-skip-small）只存在工單留言 `d8d356f1` | 專案的授權邊界只存在於執行層，違反 protocol 第 6 節「規則只在 ① 編輯」；轉平台即遺失；`foundry-gates` 在本 repo 讀不到設定 | 建立 `.foundry/config.yml`：`platform: paperclip`、`gates` 帶入 MYL-28 選定、`push` 依 MYL-27／MYL-23 |
| **G5** | **MYL-9 設計文件不在 repo** | `skills/` 五個檔共十餘處引用「MYL-9 HLD §x」；`docs/features/` 原無 cross-platform 目錄 | 違反 protocol 第 3 節「HLD／LLD 存於 `docs/features/<模組>/`」；離開 Paperclip 後所有引用斷鏈 | 逐字歸檔為 [`HLD.md`](HLD.md)（不重寫已核可文件），並在五處引用補上 repo 路徑 |
| **G6** | 等卡期間的狀態語意不明 | protocol 第 2 節只寫「HITL 閘門等回覆 → `blocked`」；`foundry-gates` §3.4、`foundry-adopt` §2.4 寫「等待期間轉 `in_review`」 | 同一情境兩種寫法，跨平台照做的人會不一致 | protocol 第 2 節 `in_review` 補分界判準：**有沒有東西要人驗收**——關卡核可卡 → `in_review`；觸發式閘門 → `blocked` |
| **G7** | **本 repo 的 main push 授權無法用 config 表達**（⚠️ 待裁定） | MYL-23 P1 常設授權含「合併回 main 後 push origin，執行者自行」；但 `config-schema.md` 硬約束 `push.main_push` **只允許 `user`**，否則整檔拒用 | 本 repo 的真實授權寫不進可攜格式，只能靠 protocol 第 7 節的散文例外句 | **本次不自行決定**（屬關卡 C：常設授權的表達與擴大是使用者專屬）。config 先寫 `main_push: user` 並註明本欄目前只表達 P3 類動作，本 repo push 仍以分級表為準；選項見 §5 |

## 4. 本次變更清單

| 檔案 | 變更 |
| --- | --- |
| `skills/foundry-platform/adapters/paperclip.md` | 新增。8 動詞 → Paperclip REST API；七態 vs 六態映射；`labelIds`／`blockedByIssueIds` 全量替換的 read-modify-write 規則；平台限制表；指令查證狀態表 |
| `skills/foundry-platform/SKILL.md` | §1 載入規則、§2 `issue_ref`／`status`／新增「依賴」詞條、§5 新增「平台專屬限制寫在 adapter」原則、§6 檔案地圖 |
| `skills/foundry-platform/config-schema.md` | `platform` 枚舉補 `paperclip`；新增 `platform_options.paperclip.*` |
| `skills/foundry-platform/config.example.yml` | 同步枚舉與範例註解 |
| `skills/foundry-protocol/SKILL.md` | 新增「平台中立原則」；第 1、2、4、8、9 節與附錄自檢去平台耦合；第 2 節補 `in_review`／`blocked` 分界 |
| `skills/roles/scrum-master/SKILL.md` | 依賴表達改抽象動詞 |
| `skills/foundry-init/SKILL.md` | 平台選項補 `paperclip`＋該模式的前置檢查 |
| `skills/foundry-adopt/SKILL.md` | 枚舉更新（Paperclip 自此可啟用模組）、平台預填建議 |
| `.foundry/config.yml` | 新增。本 repo 自身的 Foundry 設定 |
| `docs/features/cross-platform/HLD.md` | 新增。MYL-9 設計文件 repo 歸檔本（原文照錄） |
| `docs/features/cross-platform/gap-analysis.md` | 本檔 |
| `docs/handbook/08-cross-platform.md` | 說明層同步 |

## 5. 待使用者裁定：G7 的兩個選項

| 選項 | 做法 | 代價 |
| --- | --- | --- |
| **A 維持現狀（本分支預設）** | `push.main_push` 維持「只允許 `user`」的硬約束；本 repo 的 P1 例行 main 同步繼續以 protocol 第 7、9 節分級表為授權依據，config 的該欄只表達 P3 類動作 | 本 repo 仍有一條「散文例外」，跨平台一致性差最後一哩；但**零風險**——沒有任何平台的設定檔能自動放行 main push |
| **B 擴充 schema** | `push.main_push` 加枚舉值（如 `executor`）表示「私有 repo 的例行 main 同步可由執行者自行」，force-push／tag／改遠端歷史仍寫死 `user`；本 repo 填該值 | 授權表達完全可攜、差異歸零；但**放寬了一條原本寫死的不變條款**——之後任何專案都可能被設成自動 push main，護欄改由「私有 repo」這個前提承擔 |

依 protocol 第 4 節，常設授權的給予與擴大是**使用者專屬**，agent 不得自行採用建議值——故本次到此為止，等裁定。

## 6. 驗證

- `.foundry/config.yml` 依 `config-schema.md` 逐欄檢查：必填齊、枚舉合法、`gates.external_actions` 與 `push.main_push` 皆 `user`。
- 全 repo 掃描：`skills/` 底下除 `adapters/paperclip.md` 外，不再出現 `blockedByIssueIds`、`unblockDescriptor`、`adapterConfig`、`reportsTo` 等平台專屬欄位名作為**規則語句**（僅作為 adapter 對照或括號舉例）。
- `adapters/paperclip.md` 的 GET 類指令已於 2026-09-03 對本公司實機執行驗證；寫入類指令的 body schema 取自平台 `openapi.json`，並在該檔附錄 B 標明查證狀態與首次使用前的試跑要求。
