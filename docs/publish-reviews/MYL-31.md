---
issue: MYL-31
verdict: APPROVED
handbook_commit: 4b9c802fd89b5f6987f94589e781d86a20629852
reviewer: Tech Lead
reviewed_at: 2026-09-03
---

# 發佈審查記錄：MYL-31 S6：handbook 跨平台導入章＋受影響 skill 重匯入收尾

## 1. 變更範圍

新增手冊第 8 章「跨平台導入」（三層文檔體系、adapter 概念、init／adopt 教學、gates 調整教學），並修正第 7 章第 6 節「手冊發佈同步」的過時描述（原文仍寫每次發佈需使用者當下同意，與 protocol 第 7 節 MYL-23 P2 常設授權衝突，依「規範為準、修正手冊」處理）。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | 4b9c802fd89b5f6987f94589e781d86a20629852（合併 1a475e4，PR #1） |
| 變更檔案 | docs/handbook/08-cross-platform.md（新增）、docs/handbook/index.md、docs/handbook/07-workflows.md、mkdocs.yml |
| 來源工單 | MYL-31 |

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進私有 main | ✅ | PR #1 已 MERGED（mergedAt 2026-09-03T05:23:37Z），merge commit `1a475e4` 已 push origin/main（`50bed5f..1a475e4`） |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --name-only 50bed5f..1a475e4`＝docs/handbook/ 三檔＋mkdocs.yml（nav 定義，隨手冊結構同步屬既定範圍，與 MYL-25 增章時相同處理） |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | 新章節內私有路徑（skills/foundry-platform 等）均以行內 code 純文字書寫、未加超連結；index.md 新增兩行同為純文字。執行腳本後核對 `filtered:` 輸出無異常（見結案留言） |

## 3. 公開適切性檢查

- **機敏資訊**：無。新內容為流程說明，無憑證、內部網址、個資。
- **內部路徑與代號**：提及 `skills/foundry-*`、`.foundry/config.yml`、工單編號（MYL-9/23/24 等）——前後文均有解釋其角色，對外部讀者可讀；與既有章節慣例一致。
- **連結可達性**：第 8 章對外連結僅指向 04-decision-points.md（同站章節）；index.md 新行連 08-cross-platform.md；mkdocs nav 已含新章，站內錨點均為 mkdocs 自動 slug。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
