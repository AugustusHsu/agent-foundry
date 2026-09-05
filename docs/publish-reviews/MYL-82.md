---
issue: MYL-82
verdict: APPROVED
handbook_commit: 475d1304ce33f840e5aa60f9ba418e3207eee6f0
reviewer: CEO
reviewed_at: 2026-09-06
---

# 發佈審查記錄：MYL-82 T9 正名遷移（`platform` → `devtools_platform` ＋新增 `ai_platform`）

母單 MYL-61 組織重新規劃的第四棒（T9，A 案插在 T3 與 T4 之間）。機械遷移由 Developer 執行、
Code Reviewer 一輪審查後判 ✅ APPROVED（報告定稿存 `docs/features/cross-platform/review-report-MYL-82.md`，
commit `397f178`），使用者核可包在母單 `plan` v5（卡 `8a9fac61` ＝ `accepted`，其中第 1 項＝A 案、
第 3 項＝授權本單改 `.foundry/config.yml`）。本記錄由執行合併與發佈的 CEO 撰寫。

## 1. 變更範圍

本單主體是 `skills/`＋`tools/`＋`.foundry/config.yml` 的欄位改名（19 檔 65 行），
手冊側是連帶同步，只有一個檔案：

| 檔案 | 改了什麼 | 性質 |
| --- | --- | --- |
| `08-cross-platform.md` | ① 既有段落 1 行改名（`platform` 欄位 → `devtools_platform`，含 `platform: paperclip` → `devtools_platform: paperclip`）；② 新增 `###` 節「「平台」其實是兩個問題（MYL-82）」，18 行。說明「平台」一詞原本同時指**工具面**（工單／狀態／看板在哪個服務）與 **AI 平台面**（agent 在哪執行、被誰喚醒），兩者是正交的軸；並附兩則 ⚠️：這是**不相容變更**（舊設定檔整份非法，要升級只能手改欄位名），以及 `ai_platform` **目前只是宣告**、沒有任何動作依它改變行為 | **內容變更**（非戳記-only）|

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `475d1304ce33f840e5aa60f9ba418e3207eee6f0` |
| 變更檔案 | `docs/handbook/08-cross-platform.md` |
| 來源工單 | MYL-82（母單 MYL-61）|
| 合併 commit | `f848929`（`--no-ff`）|

**本次不走戳記旁路**：`publish-gate.sh` 的 (b) 分支只在手冊 diff 每一行都是戳記時放行，
而本次是 19 行實質內容（1 行改名＋18 行新增節），因此必須有這份精確匹配 `handbook_commit`
的 APPROVED 記錄。

**`handbook_commit` 指向 `475d130` 而非合併 commit `f848929`，這是正確的**：
`git log -1 --format=%H -- docs/handbook` 在路徑過濾下套用 history simplification，
`--no-ff` 合併的結果與分支側 TREESAME，因此合併 commit 本身不列入，輸出的是實際動到手冊的那一顆。
與 MYL-73／MYL-74／MYL-75 三次的行為一致（MYL-75 那次同樣是 `d0464dc` 而非 `346e20e`）。

戳記說明：**四章戳記（`03`／`04`／`06`／`07`）本次全部不動，這是正確的。**
`handbook-stamp` 的觸發條件是「動到 `skills/foundry-protocol/SKILL.md`」，而本單在嚴格判準下
（`platform` 當**設定欄位**用，排除 `mirror_platform`／`platform_options`／`source_platform`／
`cross-platform`）對 protocol **零命中**——這與母單 `plan` v5 §2 連帶事項第 3 點的預測一致，
Code Reviewer 已在報告 §0 覆驗。本單動的 `08` 章沒有戳記行
（`grep -n '最後對照 protocol' docs/handbook/*.md` 只命中 `03`／`04`／`06`／`07` 四章），
閘門本就不該被觸發，`handbook-stamp` 綠是對的、不是漏擋。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | `git merge --no-ff feat/MYL-82-platform-rename` → `f848929`；`git merge-base --is-ancestor feat/MYL-82-platform-rename main` 回 0 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --name-only d0464dc..HEAD`（`d0464dc` ＝ 上一份已核可記錄 MYL-75 的 `handbook_commit`）共 22 檔，其中**僅 1 檔**在 `docs/handbook/` 底下（`08-cross-platform.md`）。其餘 21 檔分佈於 `skills/`（10）、`tools/`（4）、`docs/features/`（2）、`docs/publish-reviews/`（1）、repo 根目錄雙入口（2）、`.foundry/`（1），皆不在投影範圍——腳本只讀 `docs/handbook/` |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | `git diff d0464dc..HEAD -- docs/handbook/ \| grep '^+' \| grep -o '\[[^]]*\]([^)]*)'` **無輸出**——新增與改動的 19 行一條 markdown 連結都沒有，過濾面完全不變。`internal-links` 自檢 70 條全綠 |

補充：合併後在 main 上跑 `make check` **exit 0**——`--selfcheck` 10 項全綠
（含 `mirror-recon`：來源端 27 張／鏡像端 17 張）、288 項單元測試全過（132＋15＋34＋107）。

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容是一段對讀者解釋「為什麼一個欄位要拆成兩個」的設計說明，
  外加兩則對自身限制的誠實揭露（不相容、以及 `ai_platform` 目前只是宣告）。
  無憑證、無內部網址、無個資，未出現 `project_id`／`company_id` 等私有識別碼
  （沿用 `MYL-35.md`:31 的同一條判準）。
  揭露的欄位語意本來就寫在這個 public repo 的 `.foundry/config.yml` 與
  `skills/foundry-platform/config-schema.md` 裡，不構成新的資訊外露。
- **內部路徑與代號**：新增段落提到工單編號 `MYL-82`、設定欄位名
  `devtools_platform`／`ai_platform`／`foundry`、以及四個平台值
  （`github`／`gitlab`／`local-md`／`paperclip`）與三個 AI 平台值
  （`paperclip`／`claude-code`／`codex`）。全部對外部讀者讀得通：
  - 工單編號的寫法與本章既有敘述一致——同章第 29 行本來就有 `（MYL-35）`、
    第 31 行有 `你在 MYL-28 選定的關卡方案`，不是本次才引入的體例。
  - 欄位名與平台值都是這份公開手冊在講的設定檔本身的內容，**新增段落自己把語意講完了**
    （工具面＝「工單、狀態、看板放在哪個服務上」；AI 平台面＝「agent 本身在哪裡執行、被誰喚醒」），
    讀者不需要拿到私有檔案就看得懂。
  - **未提及任何 `skills/`、`templates/`、`docs/pilot/` 路徑**。同段落末尾原有的
    `規則本體：skills/foundry-platform/…` 那一行是本次之前就存在的內容，未被本次改動。
- **連結可達性**：本次未新增任何連結，既有連結未動，故無死連結風險。新增了一個 `###` 標題
  「「平台」其實是兩個問題（MYL-82）」，但**沒有任何連結指向它**——`anchors` 自檢全綠，
  `L16`（wiki 與精裝站兩套 slug 演算法對中文標題結果不同）的風險面本次未被觸及。
  章節數不變（仍 9 篇），`nav-sync` 綠，不需要動 `mkdocs.yml`。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
