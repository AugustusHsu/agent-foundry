---
issue: MYL-79
verdict: APPROVED
handbook_commit: 6d6bb3282a98748bc262c7b080c0f9e186ab731e
reviewer: CEO
reviewed_at: 2026-09-06
---

# 發佈審查記錄：MYL-79 T7 平台側套用（PM 落地、`O4` 暫代條款、`org.yml` 權限來源註記）

母單 MYL-61 組織重新規劃的第七棒（T7）。規則層回填由 CEO 執行，Code Reviewer 走**兩輪**審查：
第 1 輪 ❌ CHANGES REQUESTED（七項事實與機械覆蓋，報告見 MYL-95 留言 `957e5546`），
修正後第 2 輪 ✅ APPROVED（報告定稿存 `docs/features/org/review-report-MYL-79.md`，commit `d72c104`）。
使用者核可包在本單的裁定卡 `0bd69c99`（`answered`），其中 Q1 ＝ PM 模型層選「中」、
Q3／Q4 ＝ 核可 `O4` 條文與 `org.yml` 註記。本記錄由執行合併與發佈的 CEO 撰寫。

## 1. 變更範圍

本單主體是平台側 API 操作（建 PM agent、收放權限、掛 skill、對帳）與規則層回填，
手冊側是連帶同步，兩個檔案：

| 檔案 | 改了什麼 | 性質 |
| --- | --- | --- |
| `06-org-structure.md` | ① 既有段落 1 行改寫：「PM 目前只存在於規範裡，平台上的 agent 還沒建」→「2026-09-06 已在平台上建置完成」，並改述九個角色的對帳結果為「除下述一處刻意保留的例外外，其餘逐格一致」；② 新增一段說明那處例外（Frontend Verifier 的「可否指派工單」旗標在平台上解出來是開的，關掉它的 API 是單向門，能清乾淨的設定點只有使用者動得了，實際影響為零）；③ 新增 `###` 節「角色還沒建出來的那段期間，誰拍板」，用非技術語言講 `O4` 暫代通則（拍板者未建置時由匯報對象暫代、註明暫代者與終止條件、暫代不擴權），並說明為何寫成通則而非 PM 個案 | **內容變更**（非戳記-only）|
| `07-workflows.md` | 模型分層表「中」列的適用對象 1 行改寫：補上 Frontend Verifier 的前端驗證、以及 PM 的狀態彙整／異常判讀／派工。這是 protocol §8 分層表定案值（PM ＝「中」）的轉寫 | **內容變更**（非戳記-only）|

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `6d6bb3282a98748bc262c7b080c0f9e186ab731e` |
| 變更檔案 | `docs/handbook/06-org-structure.md`、`docs/handbook/07-workflows.md` |
| 來源工單 | MYL-79（母單 MYL-61、審查單 MYL-95）|
| 合併 commit | `68a0789`（`--no-ff`）|
| 手冊差異量 | 06 章 +11／−1 行、07 章 +1／−1 行 |

**本次不走戳記旁路**：`publish-gate.sh` 的 (b) 分支只在手冊 diff 每一行都是戳記時放行，
而本次 14 行差異**沒有任何一行是戳記**（四章戳記本次全部未動，見下），因此必須有這份
精確匹配 `handbook_commit` 的 APPROVED 記錄。

**`handbook_commit` 指向 `6d6bb32` 而非合併 commit `68a0789`，這是正確的**：
`git log -1 --format=%H -- docs/handbook` 在路徑過濾下套用 history simplification，
`--no-ff` 合併的結果與分支側 TREESAME，因此合併 commit 本身不列入，輸出的是實際動到手冊的那一顆。
與 MYL-73／MYL-74／MYL-75／MYL-82／MYL-78／MYL-77 六次的行為一致。

⚠️ **本單動手冊的是兩顆 commit**（`866537c` 建立內容、`6d6bb32` 依第 1 輪退件修正 `06:69`／`:71`
的過度宣稱），`handbook_commit` 取**較晚的那顆** `6d6bb32`——這正是模板所說「手冊在審查後又改了，
就要重新自檢並更新這一欄」的情形，本記錄填的是修正後的值。

戳記說明：**四章戳記（`03`／`04`／`06`／`07`）本次全部不動，這是正確的。**
現況是 `03`／`04`／`07` ＝ `e62e42c`（2026-09-05）、`06` ＝ `0a0b461`（2026-09-06）。
本單確實動了 `skills/foundry-protocol/SKILL.md`（§8 分層表回填 PM ＝「中」、§9 新增 `O4`），
pre-commit 的手冊同步觸發器因此被觸發，而本單同時動了手冊兩章 ⇒ 觸發器 Passed；
`handbook-stamp` 自檢亦綠（其判準不是「戳記等於最新 sha」，見 MYL-44 的裁定）。
合併後在 main 上覆驗，兩者維持綠。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進私有 main | ✅ | `git merge --no-ff myl-79-t7-platform-apply` → `68a0789`；`git merge-base --is-ancestor 6d6bb3282a98748bc262c7b080c0f9e186ab731e main` 回 0。已 `git push origin main`（`b61e533..68a0789`）。`git log -1 --format=%H -- docs/handbook` 回 `6d6bb328…`，與本欄 `handbook_commit` 逐字一致 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --name-only d2400c6..68a0789`（`d2400c6` ＝ 上一份已核可記錄 MYL-77 的 `handbook_commit`，`68a0789` ＝ 本次合併 commit，即本記錄自身 commit 之前的 main）共 **29 檔，其中僅 2 檔**在 `docs/handbook/` 底下（`06-org-structure.md`、`07-workflows.md`）。其餘 27 檔分佈於 `docs/features/`（9）、`tools/`（6）、`skills/`（5）、repo 根目錄雙入口與建置檔（4，含 `Makefile`／`.pre-commit-config.yaml`）、`docs/publish-reviews/`（1）、`docs/standards/`（1）、`.foundry/`（1），皆不在投影範圍——腳本只讀 `docs/handbook/`。這 29 檔橫跨 MYL-86／MYL-91／MYL-92 與本單四次合併，其中**只有本單動了手冊**，故基準仍是 `d2400c6` |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | `git diff b61e533..HEAD -- docs/handbook/ \| grep '^+' \| grep -E 'skills/\|templates/\|docs/pilot\|docs/standards\|\.foundry\|\]\('` **無輸出**——本次新增與改動的 14 行**一條 markdown 連結都沒有**，也未出現任何私有目錄路徑，過濾面完全不變。`internal-links` 自檢 70 條全綠、`anchors` 9 條全綠 |

補充：合併前在分支上跑 `make check` **exit 0**——`--selfcheck` **14 項全綠**
（`entry-sync`／`nav-sync`／`anchors`／`rule-ids`／`rule-marks`／`big-files`／`internal-links`／
`version-shape`／`table-shape`／`org-sync`／`handbook-stamp`／`init-copy-list`／`selfcheck-names`／
`mirror-recon`，其中 `mirror-recon` 來源端 39 張／鏡像端 27 張）、356 項單元測試全過
（200＋15＋34＋107）。`rule-marks` 覆蓋 **27 行違反段**（＝ main 的 26 ＋ `O4` 新增的一段），
第 1 輪那個「檢查照樣綠、覆蓋卻悄悄少兩段」的失效已修復並經 Code Reviewer 六發突變獨立覆驗。

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容是對讀者解釋「組織規範與平台實況的一處已知落差」與「拍板者尚未建置時怎麼辦」，
  外加一則對自身限制的誠實揭露（那個旗標關不乾淨、只有使用者動得了）。
  無憑證、無內部網址、無個資。**特別確認未出現 agent id、grant id 或 `company_id` 等私有識別碼**——
  以 `[0-9a-f]{8}-[0-9a-f]{4}` 與 `[0-9a-f]{8}\b` 兩式掃過本次新增行，**零命中**
  （沿用 `MYL-35.md`:31 的同一條判準）。本單在 `.foundry/org.yml` 與 `docs/standards/known-drift.md`
  裡確實記了 grant id 與 granter，但那兩個檔案**不在投影範圍**，未外流到手冊。
- **內部路徑與代號**：新增段落提到工單編號 `MYL-79`、`MYL-73`，以及角色名
  （Frontend Verifier／PM／CEO）與平台名 Paperclip。全部對外部讀者讀得通：
  - 工單編號的寫法與本章既有敘述一致——同章第 66 行本來就有「你在 MYL-37 裁定建的」，
    不是本次才引入的體例。
  - 角色名與平台名都是這份公開手冊本來就在講的對象（06 章整章即組織結構、07 章即八條 workflow）。
  - **未提及任何 `skills/`、`templates/`、`docs/pilot/`、`.foundry/` 路徑**（上表前提 3 的 grep 已機械確認）。
    新增段落刻意用「可否指派工單」「那個旗標」這類非技術語彙描述 `tasks:assign`／`canAssignTasks`，
    讀者不需要拿到私有檔案就看得懂。
- **連結可達性**：本次未新增任何連結，既有連結未動，故無死連結風險。新增了一個 `###` 標題
  「角色還沒建出來的那段期間，誰拍板」，但**沒有任何連結指向它**——`anchors` 自檢全綠，
  `L16`（wiki 與精裝站兩套 slug 演算法對中文標題結果不同）的風險面本次未被觸及。
  章節數不變，`nav-sync` 綠，不需要動 `mkdocs.yml`。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
