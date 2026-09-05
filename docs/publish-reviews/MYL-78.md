---
issue: MYL-78
verdict: APPROVED
handbook_commit: ab9aa6290badb990bc7320e4d07d543931affa64
reviewer: CEO
reviewed_at: 2026-09-06
---

# 發佈審查記錄：MYL-78 T6 軸 A 可攜層（Claude Code／Codex）＋ 初始化問答

母單 MYL-61 組織重新規劃的第五棒（T6）。本體由 Developer 執行、Code Reviewer **兩輪**審查
（第一輪 `CHANGES_REQUESTED`／R1 R2 必改，第二輪 R1～R7 全收後判 ✅ APPROVED；
報告定稿存 `docs/features/cross-platform/review-report-MYL-78.md`，commit `64af7b1`）。
本記錄由執行合併與發佈的 CEO 撰寫。

## 1. 變更範圍

本單主體是 `skills/foundry-ai-platform/` 這份新 skill（261 行）加上 `foundry-init`／`foundry-adopt`／
`foundry-model-routing` 的連帶修改，手冊側是**面向讀者的說明**，只有一個檔案：

| 檔案 | 改了什麼 | 性質 |
| --- | --- | --- |
| `08-cross-platform.md` | ① 既有的 2 行 ⚠️ 改寫：上一棒（MYL-82）寫的「`ai_platform` 目前**只是宣告**……也還沒有三家平台的能力對照表」，其中「還沒有對照表」這半句在本單之後**不再成立**，改為「欄位本身仍然只是宣告，但能力對照表已經有了」；② 新增 `###` 節「換到 Claude Code 或 Codex，會掉哪些能力？（MYL-78）」，24 行。內容是三件要先知道的事（Paperclip 的工具能力是**借來的**、Claude Code 是**轉發層**、落差最大的兩項都在**編排面**）＋一條誠實話（「把團隊帶過去」任何平台都做不到）＋導入時由 `foundry-init`／`foundry-adopt` 代查的出口 | **內容變更**（非戳記-only）|

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `ab9aa6290badb990bc7320e4d07d543931affa64` |
| 變更檔案 | `docs/handbook/08-cross-platform.md`（+26／-2）|
| 來源工單 | MYL-78（母單 MYL-61）|
| 合併 commit | `a383a9a`（`--no-ff`）|

**本次不走戳記旁路**：`publish-gate.sh` 的 (b) 分支只在手冊 diff 每一行都是戳記時放行，
而本次是 28 行實質內容（2 行改寫＋26 行新增），因此必須有這份精確匹配 `handbook_commit`
的 APPROVED 記錄。

**`handbook_commit` 指向 `ab9aa62` 而非合併 commit `a383a9a`，這是正確的**：
`git log -1 --format=%H -- docs/handbook` 在路徑過濾下套用 history simplification，
`--no-ff` 合併的結果與分支側 TREESAME，因此合併 commit 本身不列入，輸出的是實際動到手冊的那一顆。
分支四顆 commit 中**只有 `ab9aa62` 動到手冊**（`git log --oneline main..分支 -- docs/handbook/` 單筆），
後三顆（`bd6c402`／`4f68eb7`／`64af7b1`）都沒碰 `docs/handbook/`，所以不必擔心「審查後手冊又改了」
導致 sha 過期的情形。與 MYL-73／MYL-74／MYL-75／MYL-82 四次的行為一致。

戳記說明：**四章戳記（`03`／`04`／`06`／`07`）本次全部不動，這是正確的。**
`handbook-stamp` 的觸發條件是「動到 `skills/foundry-protocol/SKILL.md`」，而本單
`git diff --name-only 68ba7d6..HEAD -- skills/foundry-protocol/` **輸出為空**——protocol 一字未改
（這是工單邊界第一條明文守住的：「不改 protocol §9，那是 T1」）。本單動的 `08` 章本身沒有戳記行
（`grep -c '最後對照 protocol' docs/handbook/08-cross-platform.md` ＝ 0），
閘門本就不該被觸發，`handbook-stamp` 綠是對的、不是漏擋。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | `git merge --no-ff feat/MYL-78-ai-platform` → `a383a9a`；`git merge-base --is-ancestor feat/MYL-78-ai-platform main` 回 exit 0 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --name-only 475d130..HEAD`（`475d130` ＝ 上一份已核可記錄 MYL-82 的 `handbook_commit`）共 20 檔，其中**僅 1 檔**在 `docs/handbook/` 底下（`08-cross-platform.md`）。其餘 19 檔分佈於 `skills/`（6）、`tools/`（2）、`docs/features/`（3）、`docs/publish-reviews/`（1）、`docs/standards/`（1）、`templates/`（1）、repo 根目錄雙入口與建置檔（3）、`.foundry/`（1），皆不在投影範圍——腳本只讀 `docs/handbook/` |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | `git diff 475d130..HEAD -- docs/handbook/ \| grep '^+' \| grep -o '\[[^]]*\]([^)]*)'` **無輸出**——新增與改寫的 28 行一條 markdown 連結都沒有，過濾面完全不變。`internal-links` 自檢全綠 |

補充：合併後在 main 上跑 `make check` **exit 0**——`--selfcheck` 12 項全綠
（含 `table-shape` 掃 70 份、`org-sync` 9 名、`handbook-stamp` protocol 最新 `d0464dc`、
`mirror-recon` 來源端 29 張／鏡像端 19 張）、311 項單元測試全過（155＋15＋34＋107）。

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容是一段對讀者解釋「換平台會掉什麼能力」的設計說明，
  外加三則對自身限制的誠實揭露（Paperclip 的工具能力是借來的、Claude Code 是轉發層、
  組織不可攜）。無憑證、無內部網址、無個資，未出現 `project_id`／`company_id`
  等私有識別碼（沿用 `MYL-35.md`:31 的同一條判準）。

- **內部路徑與代號**：新增段落提到工單編號 `MYL-78`、路徑 `skills/foundry-ai-platform/`
  與 `.foundry/org.yml`、workflow 名 `foundry-init`／`foundry-adopt`，
  以及平台名 Paperclip／Claude Code／Codex。逐項確認對外部讀者讀得通：
  - **工單編號**的寫法與本章既有敘述一致——同章本來就有 `（MYL-35）`、`（MYL-82）`、
    `你在 MYL-28 選定的關卡方案`，不是本次才引入的體例。
  - **`skills/foundry-ai-platform/`**：`skills/` 路徑在本手冊是**既有體例**，
    不是本次首開——`index.md`:34 有 `skills/foundry-init/`／`foundry-adopt/`／`foundry-gates/`，
    `04-decision-points.md`:5,94 有 `skills/foundry-protocol/`／`skills/foundry-platform/`，
    `07-workflows.md`:129 有 `skills/foundry-model-routing/`。**這是刻意的取捨而非疏漏**：
    手冊是說明層、規則本體在私有的 `skills/`，指出規則住在哪裡對讀者有意義，
    即使公開讀者點不進去。判準是「前後文對外部讀者是否仍讀得通」——本段自己把該 skill
    的內容講完了（九項能力 × 四個平台、每格填四種狀態、每個落差配一條寫明
    降級成什麼／誰負責／證據長什麼樣的規則），讀者不需要拿到私有檔案就懂它是什麼、有什麼。
  - **`.foundry/org.yml`**：這是它**第一次出現在公開手冊裡**（MYL-76 建了這個檔但未動手冊）。
    仍判定適切——`.foundry/` 目錄在本章是既有體例（同章「還沒導入過 Foundry 的乾淨專案
    （沒有 `.foundry/config.yml`）」），且新增句子**當場把它定義完了**
    （「是一份組織**宣告**」），讀者不需要前情提要。它是使用者自己專案裡會產生的設定檔名，
    不是我方的內部識別碼。
  - **未提及任何 `templates/`、`docs/pilot/`、`docs/standards/` 路徑**。

- **連結可達性**：本次未新增任何 markdown 連結，既有連結未動，故無死連結風險。
  新增了一個 `###` 標題「換到 Claude Code 或 Codex，會掉哪些能力？（MYL-78）」，
  但**沒有任何連結指向它**——`anchors` 自檢全綠，`L16`（wiki 與精裝站兩套 slug 演算法
  對中文標題結果不同）的風險面本次未被觸及。章節數不變（仍 9 篇），`nav-sync` 綠，
  不需要動 `mkdocs.yml`。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
