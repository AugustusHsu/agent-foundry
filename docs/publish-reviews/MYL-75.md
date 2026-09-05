---
issue: MYL-75
verdict: APPROVED
handbook_commit: d0464dc4891f5c7a2f0975544fe51d6fcf68e597
reviewer: CEO
reviewed_at: 2026-09-06
---

# 發佈審查記錄：MYL-75 唯讀檢視模式（等級邊界 `F1` ＋ 效力邊界 `F2`）

母單 MYL-61 組織重新規劃的第三棒（T3）。規則本體由 Tech Lead 起草、Code Reviewer 兩輪
審查後判 ✅ APPROVED（報告定稿存 `docs/features/org/review-report-MYL-75.md`，commit
`4e1b476`），使用者核可包在母單 `plan` v5（卡 `8a9fac61` ＝ `accepted`）。本記錄由執行
合併與發佈的 CEO 撰寫。

## 1. 變更範圍

本單主體是 `skills/`（protocol `F1`／`F2` ＋ `foundry-browser` 執行細則 ＋ 三份角色 skill
回填指標），手冊側是連帶同步，只有一個檔案：

| 檔案 | 改了什麼 | 性質 |
| --- | --- | --- |
| `04-decision-points.md:62`（新增節）| 新增「卡片上的截圖，哪一種算證據」一節，11 行。告訴使用者：CEO／PM 自己截的圖只是唯讀檢視（`F1`），**不得推進關卡**（`F2`）；唯一有效力的前端證據是 Frontend Verifier 的對照表；並明說這條沒有工具擋得住，使用者收到截圖時追問「誰截的、有沒有對照表」是實際上唯一的檢查點 | **內容變更**（非戳記-only）|

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `d0464dc4891f5c7a2f0975544fe51d6fcf68e597` |
| 變更檔案 | `docs/handbook/04-decision-points.md` |
| 來源工單 | MYL-75（母單 MYL-61）|
| 合併 commit | `346e20e`（`--no-ff`）|

**本次不走戳記旁路**：`publish-gate.sh` 的 (b) 分支只在手冊 diff 每一行都是戳記時放行，
而本次是 11 行實質內容，因此必須有這份精確匹配 `handbook_commit` 的 APPROVED 記錄
（Code Reviewer 在交接時已點名這一項）。

戳記說明：**04 章戳記維持 `e62e42c`、本次刻意不動，這是正確的。** `handbook-stamp` 的判準
是「戳記之後的每一顆 protocol 改動都要有手冊變更同行」，不是「戳記等於 protocol 最新 sha」
（後者在同一顆 commit 內永遠無法成立——戳記指不到自己那一顆，見 `foundry_lint.py`
`unsynced_protocol_commits` 的 docstring）。本單動 protocol 的兩顆 `e2902aa` 與 `d0464dc`
**都在同一顆 commit 內同時動了 04 章**，因此兩顆都算已同步，機械層綠。`03`／`06`／`07`
三章本次不動：`F1`／`F2` 是第 4 節的決策點規則，那三章沒有敘述因它變成不實。
**已知機械缺口（非本單造成）**：`handbook-stamp` 驗的是「動到手冊**任一**檔」不是「動到
**對應章**」（`foundry_lint.py:819`），已由 MYL-73 轉 MYL-76（T4）追蹤。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | `git merge --no-ff feat/MYL-75-readonly-view-mode` → `346e20e`；`git merge-base --is-ancestor feat/MYL-75-readonly-view-mode main` 回 0；已 push（`e006700..346e20e`），`git rev-parse HEAD origin/main` 兩者同值 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --name-only 0056dc6..HEAD`（`0056dc6` ＝ 上一份已核可記錄 MYL-74 的 `handbook_commit`）共 8 檔，其中僅 1 檔在 `docs/handbook/` 底下。其餘 7 檔（`skills/` 五份、`docs/features/org/`、`docs/publish-reviews/MYL-74.md`）不在投影範圍，腳本只讀 `docs/handbook/` |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | `git diff 0056dc6..HEAD -- docs/handbook/ \| grep '^+' \| grep -o '\[[^]]*\]([^)]*)'` **無輸出**——新增的 11 行一條 markdown 連結都沒有，過濾面完全不變。`internal-links` 自檢 70 條全綠 |

補充：合併後在 main 上跑 `make check` **exit 0**——`--selfcheck` 10 項全綠
（含 `mirror-recon`：來源端 27 張／鏡像端 17 張）、288 項單元測試全過。

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容是一段給使用者的判讀指引（哪種截圖算證據），以及一則
  對自身限制的誠實揭露（瀏覽器工具綁 repo、切不出「只有 Frontend Verifier 有」）。
  無憑證、無內部網址、無個資。那則揭露講的是 `.mcp.json` 的情境級語意，而 `.mcp.json`
  本來就在這個 public repo 裡，不構成新的資訊外露。
- **內部路徑與代號**：新增段落提到規則 ID `F1`／`F2`、角色名 `Frontend Verifier`、
  `protocol`。三者對外部讀者都讀得通：
  - 規則 ID 的寫法與本章既有的 `H1`～`H6` 完全一致，而本章第 86 行本來就有一段
    「**那些 `H1`、`H2` 是什麼？**」在向讀者解釋規則編號這個機制。更重要的是**新增段落
    自己把規則內容講完了**（「只被允許做唯讀檢視——開頁、看渲染、截圖，不點擊、不填表、
    不做故障注入」），ID 只是給拿得到原文的人的定位符，不構成斷鏈。
  - `Frontend Verifier` 在手冊 06 章已出現於五行（組織圖、CEO 直轄五個、為何不在開發三角內、
    「規範落後現況時怎麼辦」的判例、`reportsTo` 映射），不是本次才出現的新代號。
  - 未提及任何 `skills/`、`templates/`、`docs/pilot/` 路徑。
- **連結可達性**：本次未新增任何連結，既有連結未動，故無死連結風險。新增了一個
  `##` 標題「卡片上的截圖，哪一種算證據」，但**沒有任何連結指向它**——`anchors` 自檢
  9 條全綠，`L16`（wiki 與精裝站兩套 slug 演算法）的風險面本次未被觸及。章節數不變
  （仍 8 篇），`nav-sync` 綠，不需要動 `mkdocs.yml`。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
