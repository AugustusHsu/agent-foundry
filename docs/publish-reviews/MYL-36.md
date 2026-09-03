---
issue: MYL-36
verdict: APPROVED
handbook_commit: c1d020b5cc913cb8283ec64e6aa28c538c0731b0
reviewer: CEO
reviewed_at: 2026-09-03
---

# 發佈審查記錄：MYL-36 參考外部專案/文章改善專案

## 1. 變更範圍

本次手冊變更有兩類：① 新增第 7 章第 7 條 workflow（機械層閘門）與第 4 章的規則 ID 說明，
屬新規範的說明層投影；② **更正兩處與現實不符的既有內容**——第 2、5 章原寫「改規範後須由
使用者在 Paperclip 重新匯入 skill」，該結論已於 MYL-23 被推翻（skill 為 `local_path`
參照式安裝，commit 即生效），舊文會讓使用者收到不必要的卡片並白做一次操作。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | c1d020b5cc913cb8283ec64e6aa28c538c0731b0（合併 87e1d07） |
| 變更檔案 | docs/handbook/02-commands.md、04-decision-points.md、05-troubleshooting.md、07-workflows.md |
| 來源工單 | MYL-36 |

各章變更摘要：

- **02-commands.md**：「改團隊規範」列的後果欄改為「commit 即生效、你不必做任何事」，並指向第 5 章案例 5。
- **04-decision-points.md**：觸發式閘門表補上 `H6`（原文只列 5 條，protocol 有 6 條）＋新增 ID 欄與一段「這些編號是什麼」的說明。
- **05-troubleshooting.md**：案例 5 保留原症狀與 403 成因（仍為真），追加「後續更正」區塊說明正解不是重新匯入。
- **07-workflows.md**：總覽表新增第 7 條、新增「## 7. 機械層閘門」一節、文末「這對你有什麼影響」由六條改為七條並補第 7 條說明。

**未動 `mkdocs.yml`**：本次沒有新增章節檔，nav 結構不變。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進私有 main | ✅ | `git merge --no-ff` 產生 `87e1d07`，已 `git push origin main`（`ae33562..87e1d07`）。`git log -1 --format=%H -- docs/handbook` ＝ `c1d020b`，為 `main` 的祖先 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | 本單同時改了 skills／tools／templates／根目錄多檔，但**同步到公開站的只有 `docs/handbook/`**——發佈腳本的來源目錄固定為該目錄，其餘變更留在私有 repo。`git diff --name-only ae33562..HEAD` 中屬 `docs/handbook/` 者為上表四檔 |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | 本次新增內容未加入任何指向私有路徑的超連結：新增的連結只有 `](05-troubleshooting.md)`（章節間）與 `](#7)`（站內錨點）。既有的 `../../skills/…`、`../pilot/…` 連結不受本次變更影響，照既有過濾規則處理。執行腳本後核對 `filtered:` 輸出（見結案留言） |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容為流程說明，無憑證、內部網址、個資。
  ⚠️ 特別確認：本單另建的 `docs/standards/known-drift.md` 含內部 API 路徑與平台細節，
  **刻意不放進 `docs/handbook/`、不發佈**；手冊四章均未連向該檔（已用 grep 核對）。
- **內部路徑與代號**：第 5 章更正段提到「agent runtime 已載入的 SKILL.md 副本與 repo 檔案比對 md5」，
  以概念描述書寫、未寫出 acp-engine 的實際絕對路徑，對外部讀者可讀。
  第 7 章提到 `tools/foundry-lint/`、`make check`，屬公開 repo 既有結構，與既有章節慣例一致。
- **連結可達性**：第 7 章新增的 `](#7)` 錨點由 `foundry-lint --selfcheck` 的 `anchors` 檢查
  以 mkdocs 實際 slug 演算法驗證通過（8 個內部錨點連結全數配對）；
  第 2 章新增的 `](05-troubleshooting.md)` 指向同站既有章節。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
