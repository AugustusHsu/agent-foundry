---
issue: MYL-74
verdict: APPROVED
handbook_commit: 0056dc64993b978cd87fa4d15e8242566204d3f7
reviewer: CEO
reviewed_at: 2026-09-06
---

# 發佈審查記錄：MYL-74 落檔 `role-ceo` 與 `role-pm` 兩份角色 skill

母單 MYL-61 組織重新規劃的第二棒（T2）。skill 本體由 Developer 起草、Code Reviewer 兩輪
審查後判 ✅ APPROVED（工單留言 `988b5614`，報告定稿存
`docs/features/org/review-report-MYL-74.md`），使用者核可包在母單 `plan` v5 §8 第 2 項
（卡 `8a9fac61` ＝ `accepted`）。本記錄由執行合併與發佈的 CEO 撰寫。

## 1. 變更範圍

本單主體是 `skills/`（兩份新角色 skill ＋ protocol `O3`），手冊側是連帶同步，共三個檔案：

| 檔案 | 改了什麼 | 性質 |
| --- | --- | --- |
| `01-first-run.md:7` | 匯入檢查清單原本列舉「`foundry-protocol` 與**六個**角色 skill」並逐一點名，實際已有 9 份。改成不列舉、不寫數量、指向 `skills/roles/` 目錄本身，並補「唯一例外：CEO 不掛 `foundry-protocol`，只掛 `role-ceo`，理由見 protocol `O3`」 | **內容變更**（非戳記-only）|
| `06-org-structure.md:3` | 戳記由 `0e94307` 推進到 `0a0b461` | 戳記 |
| `index.md:32`（合併後追加，`0056dc6`）| 「規範文件在哪」清單寫「六個角色各自的判準」，同樣的數量漂移。改成不寫數量、指向目錄 | **內容變更** |

`index.md` 那一處是 Code Reviewer 在複審的**次要建議 2**，明列給合併者裁定。**CEO 裁定：搭本單一併訂正。**
理由是成本不對稱——本單因 01 章的內容變更本來就要跑一次發佈四步，順手改一行是零成本；
留到日後則要另開一張單、自己的發佈審查記錄、自己的 wiki 同步，而下游 T3～T9（MYL-75～80／82）
**沒有任何一張擁有 `docs/handbook/`**。該行與同一份手冊 06 章自相矛盾（06 章明列 PM 與
Frontend Verifier），屬純事實訂正，不動任何規則語意，因此不影響 Code Reviewer 已出的 APPROVED。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `0056dc64993b978cd87fa4d15e8242566204d3f7` |
| 變更檔案 | `docs/handbook/01-first-run.md`、`docs/handbook/06-org-structure.md`、`docs/handbook/index.md` |
| 來源工單 | MYL-74（母單 MYL-61）|
| 合併 commit | `3e35fb2`（`--no-ff`）|

戳記說明：`06` 章戳記填 `0a0b461`（前一顆動過 protocol 的 commit），而本單動 protocol 的
是 `0446c1e`——**戳記指不到自己那一顆**，與 MYL-73 同一個自我指涉限制。`handbook-stamp`
的判準是「同一顆 commit 有沒有同時動到手冊」而非「戳記等於 protocol 最新 sha」（後者會鎖死），
`0446c1e` 同時動了 protocol 與 `06` 章，故機械層綠。`03`／`04`／`07` 三章本次不動：`O3` 講的是
skill 掛載豁免，這三章沒有敘述因它變成不實。**已知機械缺口**：`handbook-stamp` 驗的是
「動到手冊**任一**檔」不是「動到**對應章**」（`foundry_lint.py:819`），已由 MYL-73 轉 MYL-76（T4）追蹤。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | `git merge --no-ff feat/MYL-74-role-ceo-pm-skills` → `3e35fb2`；`git merge-base --is-ancestor feat/MYL-74-role-ceo-pm-skills main` 回 0 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --name-only 2ebd00d..HEAD` 共 10 檔，其中僅 3 檔在 `docs/handbook/` 底下（見上表）。其餘 7 檔（`AGENTS.md`／`CLAUDE.md`／`README.md`／`docs/features/org/`／`skills/` 三份）不在投影範圍，腳本只讀 `docs/handbook/` |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | `git diff 2ebd00d..HEAD -- docs/handbook/ \| grep '^+' \| grep -o '\[[^]]*\]([^)]*)'` **無輸出**——三處變更一條連結都沒新增，過濾面不變。`internal-links` 自檢 70 條全綠 |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容是「照目錄核對角色 skill」的操作指示與一則規則指標（`O3`），
  以及既有的 403 錯誤碼說明（原文既有，未動）。無憑證、無內部網址、無個資。
- **內部路徑與代號**：01 章與 index 的新增字提到 `skills/roles/`、`foundry-protocol`、`role-ceo`
  與規則 ID `O3`。三者在這兩章的既有段落都已出現過，且 index 那一節的標題就是「規範文件在哪」，
  本來就在向讀者交代 repo 目錄結構——把數量換成「目錄本身就是清單」對外部讀者**更**讀得通，
  因為外部讀者無從得知現在是幾個角色。`O3` 是 protocol 的規則 ID，公開站上讀者打不開 protocol
  原文，但 01 章該句自己已把規則內容講完（「CEO 不掛 `foundry-protocol`，只掛 `role-ceo`」），
  ID 只是給得到原文的人的定位符，不構成斷鏈。
- **連結可達性**：本次未新增任何連結，既有連結未動；未新增或改名任何標題，故無錨點失效。
  `anchors`（9 條）與 `internal-links`（70 條）自檢皆綠。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
