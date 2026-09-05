---
issue: MYL-77
verdict: APPROVED
handbook_commit: d2400c6ecf9488ead684495a8bd144df626a648b
reviewer: CEO
reviewed_at: 2026-09-06
---

# 發佈審查記錄：MYL-77 T5 可攜性級 3：`provision_team`（軸 A 介面）＋ 四份 adapter 增節

母單 MYL-61 組織重新規劃的第六棒（T5）。本體由 Developer 執行、Code Reviewer **三輪**審查
（第一、二輪 `CHANGES_REQUESTED`，第三輪 ✅ APPROVED；報告定稿存
`docs/features/cross-platform/review-report-MYL-77.md`，commit `e1414f8`）。
本記錄由執行合併與發佈的 CEO 撰寫。

## 1. 變更範圍

本單主體是 `skills/foundry-platform/` 的規格增訂（介面 SKILL.md ＋四份 adapter 各增組織層一節），
手冊側是**面向讀者的說明**，只有一個檔案：

| 檔案 | 改了什麼 | 性質 |
| --- | --- | --- |
| `08-cross-platform.md` | 兩處既有敘述改寫，**都是被本單作廢的宣稱**：① 第 49 行原寫「`ai_platform` 這一欄本身仍然只是宣告：**沒有任何動詞依它分派**」——本單增訂 `provision_team` 之後這句話不再成立，改為寫明依 `ai_platform` 分派的動詞**只有一個**、其餘軸 A 差異仍靠能力對照表吸收；② 第 72-73 行的「誠實話」原寫「『把團隊帶過去』**目前任何平台都做不到**……沒有動詞會依它到平台上把 agent 建出來」，改為「**只在 Paperclip 成立**」，並補上換到 `claude-code`／`codex` 時那份宣告仍然合法、檢查照樣綠，但它從那一刻起只約束**人**。結論句「可攜的是那份宣告，不是那支團隊」保留 | **內容變更**（非戳記-only）|

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `d2400c6ecf9488ead684495a8bd144df626a648b` |
| 變更檔案 | `docs/handbook/08-cross-platform.md`（+6／-3）|
| 來源工單 | MYL-77（母單 MYL-61）|
| 合併 commit | `1a551e0`（`--no-ff`）|

**本次不走戳記旁路**：`publish-gate.sh` 的 (b) 分支只在手冊 diff 每一行都是戳記時放行，
而本次 9 行差異全是實質內容，因此必須有這份精確匹配 `handbook_commit` 的 APPROVED 記錄。

**`handbook_commit` 指向 `d2400c6` 而非合併 commit `1a551e0`，這是正確的**：
`git log -1 --format=%H -- docs/handbook` 在路徑過濾下套用 history simplification，
`--no-ff` 合併的結果與分支側 TREESAME，因此合併 commit 本身不列入，輸出的是實際動到手冊的那一顆。
分支四顆 commit 中**只有 `d2400c6` 動到手冊**（`git log --oneline main..分支 -- docs/handbook/` 單筆），
其後的 `e1414f8`（審查報告落檔）沒碰 `docs/handbook/`，所以不必擔心「審查後手冊又改了」導致 sha 過期。
與 MYL-73／MYL-74／MYL-75／MYL-82／MYL-78 五次的行為一致。

戳記說明：**四章戳記（`03`／`04`／`06`／`07`）本次全部不動，這是正確的。**
`handbook-stamp` 的觸發條件是「動到 `skills/foundry-protocol/SKILL.md`」，而本單
`git diff --name-only b0177e0..HEAD -- skills/foundry-protocol/` **輸出為空**——protocol 一字未改
（本單的規格增訂全部落在 `skills/foundry-platform/`，不是 protocol）。本單動的 `08` 章本身沒有戳記行
（`grep -c '最後對照 protocol' docs/handbook/08-cross-platform.md` ＝ 0），
閘門本就不該被觸發，`handbook-stamp` 綠是對的、不是漏擋。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | `git merge --no-ff origin/feat/MYL-77-provision-team` → `1a551e0`；`git merge-base --is-ancestor feat/MYL-77-provision-team main` 回 exit 0。**推送 origin/main 排在本記錄 commit 之後、發佈之前**——閘門的 P2 前提 1 對 `main` 與 `origin/main` **兩個 ref 都驗**，只合不推會被自己擋下，不必也不能靠這份記錄擔保 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --name-only ab9aa62..HEAD`（`ab9aa62` ＝ 上一份已核可記錄 MYL-78 的 `handbook_commit`）共 21 檔，其中**僅 1 檔**在 `docs/handbook/` 底下（`08-cross-platform.md`）。其餘 20 檔分佈於 `skills/`（8）、`tools/`（2）、`docs/features/`（3）、`docs/publish-reviews/`（1）、repo 根目錄雙入口與建置檔（4，含 `Makefile`／`.pre-commit-config.yaml`）、`skills/foundry-platform/config.example.yml`（1），皆不在投影範圍——腳本只讀 `docs/handbook/`。這 21 檔橫跨 MYL-78、MYL-86 與本單三次合併，其中只有本單動了手冊，故基準仍是 `ab9aa62` |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | `git diff ab9aa62..HEAD -- docs/handbook/ \| grep '^+' \| grep -o '\[[^]]*\]([^)]*)'` **無輸出**——新增與改寫的 6 行一條 markdown 連結都沒有，過濾面完全不變。`internal-links` 自檢全綠（相對連結 70 條） |

補充：合併後在 main 上跑 `make check` **exit 0**——`--selfcheck` **13 項**全綠
（含 `table-shape` 掃 73 份、`org-sync` 9 名、`handbook-stamp` protocol 最新 `d0464dc`、
`init-copy-list` Makefile 引用 4 個／清單列 4 個、`mirror-recon` 來源端 34 張／鏡像端 24 張）、
320 項單元測試全過（164＋15＋34＋107）。

## 3. 公開適切性檢查

- **機敏資訊**：無。改寫的內容是對讀者更正兩則**已經過期的自我限制宣告**——原文說「組織不可攜、沒有動詞依 `ai_platform` 分派」，
  本單讓其中一半不再成立，於是把話收窄到「只在 Paperclip 成立」。無憑證、無內部網址、無個資，
  未出現 `project_id`／`company_id` 等私有識別碼（沿用 `MYL-35.md`:31 的同一條判準）。

- **內部路徑與代號**：改寫段落提到工單編號 `MYL-77`、動詞名 `provision_team`、設定檔 `.foundry/org.yml`
  與欄位 `ai_platform`、平台值 `claude-code`／`codex` 與平台名 Paperclip。逐項確認對外部讀者讀得通：
  - **工單編號**的寫法與本章既有敘述一致——同章本來就有 `（MYL-35）`、`（MYL-82）`、`（MYL-78）`，
    不是本次才引入的體例。
  - **`provision_team`**：這是它**第一次出現在公開手冊裡**。仍判定適切——兩處出現都**當場把它定義完了**
    （「把 `.foundry/org.yml` 宣告的那支團隊在平台上建出來」／「把它變成一支真的存在的團隊要靠……
    而這個動詞只在有 agent 註冊表的平台上跑得動」），讀者不需要拿到私有的 `skills/foundry-platform/`
    就懂它是什麼、為什麼只有一個平台跑得動。
  - **`.foundry/org.yml` 與 `ai_platform`**：兩者都是 MYL-78／MYL-82 已經引入本章的既有詞彙，本次沿用未新增體例。
  - **`skills/foundry-platform/`**：該行（「規則本體：……」）**本次未改動**，是既有內容，公開適切性已於前次審查判定過。
  - **未提及任何 `templates/`、`docs/pilot/`、`docs/standards/` 路徑**。

- **連結可達性**：本次未新增任何 markdown 連結，既有連結未動，故無死連結風險。
  **也未新增任何標題**（`git diff … | grep '^+#'` 無輸出）——`anchors` 自檢全綠（內部錨點 9 個），
  `L16`（wiki 與精裝站兩套 slug 演算法對中文標題結果不同）的風險面本次完全未被觸及。
  章節數不變（`nav-sync` 報 8 篇），`nav-sync` 綠，不需要動 `mkdocs.yml`。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
