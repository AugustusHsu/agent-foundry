<!-- 本檔為 MYL-9 設計文件的 repo 歸檔本，原文照錄，不重寫（MYL-71 移除自有版本欄位除外，見下方歸檔說明）。 -->

> **歸檔說明（MYL-35，2026-09-03）**
>
> - **來源**：Paperclip 工單 MYL-9 的 `plan` 文檔（revision 2），2026-09-03 經確認卡 `a25f56cd` 核可定案。
> - **歸檔原因**：`skills/foundry-protocol`、`skills/foundry-platform`、`foundry-init`／`foundry-adopt`／`foundry-gates`
>   共十餘處引用「MYL-9 HLD §x」，但本文原先只存在於執行層（工單系統），不在規則層 repo——
>   違反 foundry-protocol 第 3 節「HLD／LLD 存於 `docs/features/<模組>/`」，且轉移平台後所有引用會斷。
> - **本檔與原文的關係**：MYL-35 歸檔時**逐字照錄**；此後唯一的改動是 MYL-71 依使用者裁定
>   移除下方標題列的自有版本欄位（protocol `V5`：repo 內的永久文件不設自有版本欄位，
>   文件的版本就是 git sha），**內容其餘部分未動**。已核可的設計文件不因歸檔而重寫；
>   後續變更依 foundry-protocol 第 6 節由 Tech Lead 改本檔（自此本檔為該設計的唯一權威）。
> - 本文早於 `templates/hld.md` 的章節骨架，章節標題與該模板不同，不納入 `foundry-lint --type hld` 檢查。

---

# MYL-9 跨平台開發流程設計（HLD）

> 作者：CEO｜狀態：**已核可**（2026-09-03 確認卡 `a25f56cd` accepted）
> 依據：2026-09-03 問卷卡（interaction `cee612c5`）6 項定案結論；foundry-protocol（skills/foundry-protocol/SKILL.md）；handbook 第 4 章決策點；MYL-14 決策權矩陣。

## 0. 已定案結論（本設計的前提，不再重議）

| # | 議題 | 定案 |
|---|------|------|
| 1 | 文檔分層 | 三分法＋repo .md 為 SSOT，其餘為投影 |
| 2 | GitHub 受眾 | 人機共用：agent 用 CLI 寫入、人類用網頁 view 檢視 |
| 3 | 平台抽象 | adapter 介面；本期實作 `github` 與 `local-md` 兩個；GitLab 後續照介面補 |
| 4 | 審查粒度 | 收斂成 3 個抽象關卡；**另設計 `foundry-gates` workflow**：盤點現況粒度＋建議設置，交使用者確認後才生效 |
| 5 | push 權限 | 下放 Tech Lead：分支 push＋開 PR 自動；push main 與對外發佈仍需使用者當下同意 |
| 6 | 導入方式 | `foundry-init`＋`foundry-adopt` 兩件套，以跨平台 .md skill 格式實作 |

---

## 1. 文檔體系：三層架構

### 1.1 分層定義

| 層 | 載體 | 受眾 | 內容 | 真實來源歸屬 |
|----|------|------|------|--------------|
| ① 規則層 | repo 內 .md（`skills/`、`docs/`、`templates/`、`.foundry/`） | agent（人可讀） | 流程規範、角色定義、模板、專案設定 | **SSOT：規則與流程以此為準** |
| ② 執行層 | git 平台（GitHub Issues／Projects／Milestones／Labels／Views） | 人機共用 | 工單、進度、里程碑、看板 | **SSOT：執行狀態以此為準** |
| ③ 說明層 | 文檔網站（現有 foundry-handbook Pages） | 人類 | 使用說明、初始化教學、troubleshooting | 無——永遠是 ① 的投影 |

### 1.2 同步方向規則

- **規則文檔**只在 ① 編輯；③ 由 `scripts/publish-handbook.sh` 同步，② 的 issue templates／labels 定義由 init workflow 從 ① 產生。禁止直接改 ③ 或在 ② 上另寫規則。
- **執行狀態**只在 ② 更新（agent 走 CLI、人走網頁）；① 不保存工單進度副本。`local-md` 模式下 ② 的載體改為 `.foundry/board/`（見 §2.3），規則不變。
- 衝突裁決：規則類以 ① 為準、狀態類以 ② 為準——與 protocol 第 6 節「文檔權威階序」銜接，實作時在該節補上這兩條。

## 2. 平台 adapter 抽象層

### 2.1 介面（抽象動詞集）

adapter 介面 = 本期兩個 adapter 的共同操作，刻意最小化：

```
init_structure    建立平台側骨架（labels、milestones、project、views）
create_issue      開單（含 type label、milestone、assignee）
update_status     更新工單狀態（todo/in_progress/in_review/blocked/done/cancelled）
comment           在工單留言（交接、審查結論）
set_labels / set_milestone
list_issues       依狀態／label／milestone 查詢
link_issues       建立 blocker／parent 關聯
```

### 2.2 實作形式

每個 adapter 是一份 .md 對照文檔（`skills/foundry-platform/adapters/<name>.md`）：抽象動詞 → 具體指令。例如 `github.md` 把 `create_issue` 對到 `gh issue create --label … --milestone …`；`local-md.md` 對到「在 `.foundry/board/issues/` 新增一個帶 frontmatter 的 .md 檔」。agent 執行時讀專案設定檔決定用哪份對照表。GitLab 之後新增 `gitlab.md` 即可，介面不動。

### 2.3 專案設定檔 `.foundry/config.yml`

```yaml
foundry: 1
platform: github        # github | local-md（未來 gitlab）
gates:                  # 見 §4，由 foundry-init/foundry-gates 寫入
  spec_approval: user
  design_approval: user   # 小型工單可設 skip_below: small
  external_actions: user  # 不可調降
push:
  branch_push: tech-lead  # 見 §6
  main_push: user
```

### 2.4 local-md fallback

`.foundry/board/` 目錄模擬執行層：`issues/*.md`（frontmatter 存 status/labels/milestone）、`milestones.md`、`views/*.md`（預存的查詢定義，agent 產生的狀態快照）。無 git server 也可用；日後遷移到 GitHub 時由 `foundry-adopt` 轉換。

## 3. GitHub 結構映射

| Foundry 概念 | GitHub 元素 | 說明 |
|--------------|------------|------|
| 工單（BRD/PRD/HLD/實作/測試單） | Issue ＋ type label（`type:brd`、`type:impl`…） | 文檔本體仍在 repo ①，issue 放連結＋狀態 |
| 版本／階段目標 | Milestone | |
| 狀態機六態 | Project 的 Status 欄位 | 與 protocol 第 2 節一一對應 |
| 角色分工 | Assignee ＋ `role:*` label | |
| 「View 外掛」構想 | **GitHub Projects 原生 views** | board（狀態看板）、table（全欄位）、roadmap（milestone 時間軸）；init 時自動建立，不自行開發外掛 |

## 4. 審查粒度：3 個抽象關卡

### 4.1 關卡定義

| 關卡 | 問題 | 對應現行決策點 | 預設 |
|------|------|----------------|------|
| A 規格核可 | 做什麼？ | 現行 1（選題）＋2（取捨）＋3（需求定稿） | 使用者 |
| B 方案核可 | 怎麼做？ | 現行 4（階段交接）之 HLD 部分 | 使用者；小型工單可設定跳過 |
| C 對外／不可逆核可 | 要不要出去？ | 現行 5（實作交付）之 push／發佈部分＋7（平台動作） | 使用者，**不可調降** |

- 中段執行決策（排程、實作、code review、測試、本地 commit、文檔同步、關卡間交接）依 MYL-14 決策權矩陣下放 Tech Lead 自動跑，人只收各階段摘要留言。
- 現行決策點 6（觸發式 HITL 閘門，protocol 第 4 節）**原樣保留**：它是例外通道（花錢、對外、破壞性、規格矛盾…），不屬於常規關卡，不受粒度設定影響。
- 現行決策點 5 中「驗收實作結果」併入關卡 C 前的摘要報告：使用者在核可對外動作時一併驗收，不再單獨發卡。

### 4.2 foundry-gates workflow（問卷第 4 題加碼要求）

一份獨立的 .md skill（`skills/foundry-gates/`），任何時點可跑，流程固定四步：

1. **盤點**：讀 `.foundry/config.yml`（無則視為未設定）＋近期工單紀錄，整理「目前每個關卡誰核可、實際發卡頻率、平均等待」。
2. **建議**：對照專案規模與歷史，產出建議設置（例如「B 關卡近 10 單全數照建議通過 → 建議小型工單跳過」）。
3. **確認**：把「現況 vs 建議」差異表發成互動卡（或無平台時輸出 .md 報告）給使用者選定。
4. **寫入**：把選定結果寫回 `.foundry/config.yml` 並留紀錄。絕不跳過第 3 步自行調整——與 protocol 第 4 節鐵律一致。

`foundry-init` 首次設定關卡時即呼叫此 workflow 的 2–4 步。

## 5. push 權限下放（已獲問卷同意，實作時生效）

| 動作 | 權限 | 說明 |
|------|------|------|
| feature／docs 分支 push、開 PR | **Tech Lead 自動** | 含 CI 觸發 |
| push main、force-push、tag 發佈 | 使用者當下同意 | 維持現行 protocol 第 7 節鐵律 |
| 對外發佈（publish-handbook、public repo） | 使用者當下同意 | 關卡 C，不可調降 |

實作範圍：修訂 protocol 第 7 節 push 規則與第 9 節決策權矩陣、tech-lead role skill、handbook 第 4／6 章；修訂後需重新匯入受影響 skill（使用者操作）。**現有 main 領先 origin 27 commit 的補推不在本單自動化範圍**，仍需使用者屆時明確說 push。

## 6. 導入流程兩件套

### 6.1 foundry-init（新專案／首次導入）

.md skill，跨平台可讀（Claude Code 作為 slash command、Codex 等直接讀文檔照做）。步驟：

1. 詢問平台（github / local-md）→ 檢查前置（gh auth、repo 存在）
2. 產生 `.foundry/config.yml` ＋ 複製 protocol／templates 到位
3. 呼叫 adapter `init_structure`：建 labels、milestones、project＋三個 views
4. 呼叫 foundry-gates（§4.2 步驟 2–4）設定關卡
5. 產出初始化報告＋下一步指引（連到說明層網站）

### 6.2 foundry-adopt（既有開發中專案漸進導入）

1. **盤點**：掃描現有 repo（已有的 issue tracker、分支慣例、CI）產出現況報告
2. **模組選擇**：發卡讓使用者勾選啟用模組（僅 Issues → ＋Projects views → ＋關卡制 → ＋角色分工），可分多次
3. **逐模組啟用**：每個模組有獨立的啟用步驟與回退說明；既有工單可選擇性遷移（掛 label 標記，不強制改寫歷史）
4. 任何時候可再跑 adopt 增開模組

### 6.3 跨平台相容原則

所有 workflow／skill 一律純 .md＋frontmatter，指令用抽象動詞＋adapter 對照表，不依賴特定 runtime 特性；Claude Code 專屬功能（如 hooks）只能作為可選增強，缺了照樣能人工照文檔跑。

## 7. 實作拆單（已核可，子單已建立並指派 Tech Lead）

| 子單 | 內容 | 依賴 |
|------|------|------|
| S1 | adapter 介面定義＋github／local-md 對照文檔＋`.foundry/config.yml` schema | — |
| S2 | 3 關卡制修訂：protocol 第 4/6/7/9 節、handbook 第 4 章＋push 權限下放修訂（tech-lead skill） | S1（config schema） |
| S3 | foundry-gates skill | S2 |
| S4 | foundry-init skill | S1、S3 |
| S5 | foundry-adopt skill | S4 |
| S6 | handbook 增補「跨平台導入」章＋網站同步；受影響 skill 重匯入（使用者） | S2–S5 |

## 8. 驗收標準（提議）

1. `.foundry/config.yml` schema 定案且有 github、local-md 兩份 adapter 對照文檔。
2. protocol／handbook 修訂後，3 關卡＋觸發式閘門的對照表可在 handbook 第 4 章查到。
3. foundry-gates 在本 repo 實跑一次：產出現況 vs 建議差異表並經使用者確認寫入。
4. foundry-init 在一個乾淨測試 repo 實跑通過（github 模式），local-md 模式在無 remote 目錄實跑通過。
5. foundry-adopt 對 agent-foundry 本身跑一次盤點（不強制啟用全部模組）。
6. Tech Lead push 權限修訂經使用者確認後生效，並在一次真實分支 push＋PR 中驗證。
