---
issue: MYL-73
verdict: APPROVED
handbook_commit: 0a0b4612c6c590a656df26e12f151c46d599232c
reviewer: CEO
reviewed_at: 2026-09-06
---

# 發佈審查記錄：MYL-73 組織章改寫（補登記 Frontend Verifier 與彙整型 PM）

母單 MYL-61 組織重新規劃的鏈頭（T1）。條文由 Tech Lead 起草、Code Reviewer 出
`APPROVED`（留言 `0e169797`），使用者核可包在母單 `plan` v5 §8 第 2 項（卡
`8a9fac61` ＝ `accepted`，標的 sha `0a0b461`）。本記錄由執行合併與發佈的 CEO 撰寫。

## 1. 變更範圍

手冊側只動 `06-org-structure.md` 一章，三處：

| 段落 | 改了什麼 | 對應 protocol |
| --- | --- | --- |
| 組織圖 | 補 PM 與 Frontend Verifier；「直轄三個」→「直轄五個」；新增一則說明 FV 為何不在開發三角內 | §9 現行結構 |
| 「現在為什麼不加 PM？」→「PM 是做什麼的？跟以前說的『不加 PM』是不是矛盾？」 | 整節改寫成 stream owner vs 彙整型的對照表，明寫 stream owner 觸發條件未變、兩項現在都不成立 | §9 兩種 PM 型態（`O2`）|
| 新增「規範落後現況時怎麼辦」 | 用 Frontend Verifier 當實例說明兩個不一致方向的處置 | §9 權威來源（`O1`）|

另有一處既有段落補字：拍板者清單補「AC 修改與依賴鏈歸 Scrum Master、派工歸 PM」。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `0a0b4612c6c590a656df26e12f151c46d599232c` |
| 變更檔案 | `docs/handbook/06-org-structure.md` |
| 來源工單 | MYL-73（母單 MYL-61）|
| 合併 commit | `871f3a3`（`--no-ff`）|

戳記：`06` 章由 `e62e42c` 推進到 `0e94307`。protocol 與手冊在**同一顆** commit
（`0a0b461`），依 `unsynced_protocol_commits()` 的判準即為已同步；戳記指不到自己那顆，
所以填的是前一顆動過 protocol 的 commit。`03`／`04`／`07` 三章本次不動——
§3 新增的兩棒（Frontend Verifier、PM → CEO）protocol 自己就標明「不在主線」，
而 `03` 章寫的是六段主線流程，未因此變成不實敘述。**這一點已知有機械缺口**：
`handbook-stamp` 驗的是「同一顆 commit 有動到 `docs/handbook/` 底下**任一**檔」，
不是「動到**對應章**」（`foundry_lint.py:819`），本次四章全綠並不代表章別對得上。
缺口由 Code Reviewer 於本單發現（F3），已轉 MYL-76（T4）。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | `git merge --no-ff feat/MYL-73-org-chapter` → `871f3a3`；`git push origin main` 後本地 main 與 `origin/main` 一致（見下方發佈紀錄）|
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --name-only 185dc19..HEAD` 三個檔案：`docs/handbook/06-org-structure.md`、`docs/standards/known-drift.md`、`skills/foundry-protocol/SKILL.md`。後兩者不在投影範圍，腳本只讀 `docs/handbook/` |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | `git diff 185dc19..HEAD -- docs/handbook/06-org-structure.md \| grep '^+' \| grep -o '\[[^]]*\]([^)]*)'` **無輸出**——本次新增內容一條連結都沒加，過濾面不變。`internal-links` 自檢 70 條全綠 |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容是組織編制與分工語意（角色名、匯報線、兩種 PM 的差別），
  以及三個工單編號（MYL-37／MYL-61／MYL-73）。這些工單的鏡像本來就在公開 repo 的
  issue 上。無憑證、無內部網址、無個資。
- **內部路徑與代號**：新增段提到 `reportsTo`（Paperclip 欄位名）與
  `skills/foundry-protocol/SKILL.md` 第 9 節。兩者在本章既有段落都已出現過，
  且新增段自己交代了 `reportsTo` 是什麼（「匯報對象」）。「規範落後現況時怎麼辦」
  整節對外部讀者是自足的——它講的是一個通用的治理問題（成文規範與實際系統不一致時
  該往哪邊修），不需要讀者能打開 `skills/`。
- **連結可達性**：本次未新增任何連結；既有連結未動。`anchors` 與 `internal-links`
  自檢通過。⚠️ 章內新增了兩個標題（「PM 是做什麼的？…」取代「現在為什麼不加 PM？」、
  新增「規範落後現況時怎麼辦」），**舊標題的錨點 `#現在為什麼不加-pm` 會失效**——
  已查全 repo 無任何檔案連到該錨點（`grep -rn '現在為什麼不加' --include='*.md'`
  只命中本次改動自身），外部若有人書籤到它則無從得知，屬可接受的章節改寫代價。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
