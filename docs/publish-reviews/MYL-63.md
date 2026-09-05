---
issue: MYL-63
verdict: APPROVED
handbook_commit: 477350b3cd920557fa73982f2b94931de87f09d3
reviewer: Tech Lead
reviewed_at: 2026-09-05
---

# 發佈審查記錄：MYL-63 已發佈的手冊版本不重打（protocol `V3`）

## 1. 變更範圍

protocol 第 7 節新增 `V3`「已發佈的版本不重打」，手冊隨之補上**寫給打 tag 的人**的那一句：
發出去的版本號不重發，要修就發下一版；要重建同一版走 `workflow_dispatch`。
兩章各加一段，其餘六章未動（含戳記——四章戳記與本次 protocol 改動在同一顆 commit，
`handbook-stamp` 的判準是「戳記之後的每一顆 protocol 改動都要有手冊變更同行」，已成立）。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `477350b3cd920557fa73982f2b94931de87f09d3` |
| 變更檔案 | `docs/handbook/04-decision-points.md`、`docs/handbook/07-workflows.md` |
| 來源工單 | MYL-63（父單 MYL-39，對應 SuperOD `T5`） |

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進私有 main | ✅ | `477350b` 經 `cb6f670`（`--no-ff` 合併）進 main，並已 `git push origin main`（`f531850..cb6f670`）。`git log -1 --format=%H -- docs/handbook` 回 `477350b3…`，與本欄 `handbook_commit` 一致 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | 本單同一顆 commit 另動了 protocol、`site_docs.py`、其測試與 CI workflow，但**投影範圍**只有 `docs/handbook/`：`project_docs.project()` 的來源目錄只有一個，閘門比對的也是 `git log -1 -- docs/handbook` |
| 3 | 私有連結改寫輸出檢查無異常 | ✅ | `project_docs.py` 投影 11 頁通過，摘要 `9707329ae54e`。本次新增文字**沒有任何指向 repo 內部的相對連結**，唯一新增的連結是章間的 `[第 7 章](07-workflows.md)`，投影後正確去掉 `.md` 成 `[第 7 章](07-workflows)`（wiki 頁名形式）。`--selfcheck` 的 `internal-links`（65 條）與 `anchors`（9 條）全綠 |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容只講「已發佈的版本號不重發、要重建走手動觸發」，
  沒有憑證、內部網址或個資。
- **內部路徑與代號**：新增段落提到 `handbook-v1`／`handbook-v2` 與 `workflow_dispatch`，
  都是公開站與公開 repo 上本來就看得到的東西。未提及任何私有路徑。
- **連結可達性**：新增章間連結一條（`04` → `07`），目標章節既有。
  ⚠️ 一項**本機驗不了**的殘留同 MYL-55：站台實際渲染出來的錨點字串（`X4`：本機沒有
  markdown／mkdocs）。本次新增的是章層級連結、不帶錨點，所以這一項的風險比 MYL-55 當時低。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
