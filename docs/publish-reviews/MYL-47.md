---
issue: MYL-47
verdict: APPROVED
handbook_commit: 069e2191878c1d745a8881ab9bb3859e18bf2d70
reviewer: Tech Lead
reviewed_at: 2026-09-05
---

# 發佈審查記錄：MYL-47 MYL-39A 後續：protocol 標記法的維護觸發點

## 1. 變更範圍

本單主體在規則層與工具層（protocol 圖例、`rule-marks` 自檢、`C1` 去數字），手冊側只有兩類變更：**07 章機械層閘門表的措辭修正**，以及**四章戳記推到新的 protocol sha**。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `069e2191878c1d745a8881ab9bb3859e18bf2d70` |
| 變更檔案 | `docs/handbook/03-workflow.md`、`04-decision-points.md`、`06-org-structure.md`、`07-workflows.md` |
| 來源工單 | MYL-47 |

實際變更（`git diff 1bd7c6b..069e219 -- docs/handbook/`，7 增 6 刪）：

- **03／04／06**：只有戳記行 `fcbd9c5` → `6d28021`，無內容變更。三章逐段對照過本輪 protocol diff（圖例節、`C1`、§10 違反行），沒有需要跟動的敘述。
- **07-workflows.md §7 機械層閘門**：三處內容修正 ＋ 戳記行。
    1. 「自動擋下**四類**已經踩過的錯誤」→「**一批**」。原文的「四類」在 MYL-41／42／44／54 陸續加入檢查後就失真了（實際已 8 項），本輪再加 `rule-marks` 成 9 項。
    2. 「**擋什麼**」段補一句：下表是**舉例、不是完整清單**，現行清單以 `make check` 輸出為準。**刻意不把 9 項全抄進手冊**——那會變成第五份需要同步的清單（Makefile／pre-commit hook name／雙入口 §6／本表），而這張單的主旨正是消滅這種會過期的拷貝。
    3. 表格新增 `rule-marks` 一列（本單交付物）。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | 工單分支 `MYL-47-rule-marks` 已以 `--no-ff` 併入 main（合併 commit `003fd21`）；`git merge-base --is-ancestor 6d28021 main` 回傳 0。戳記 commit `069e219` 直接落在 main 上。 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --stat 1bd7c6b..069e219 -- docs/handbook/` 只列出上表四章。本輪其餘變更（`skills/foundry-protocol/SKILL.md`、`tools/foundry-lint/*`、`Makefile`、`.pre-commit-config.yaml`、雙入口檔）都在 `docs/handbook/` 之外，投影腳本本來就不會取。 |
| 3 | 私有連結改寫輸出與逐章比對無異常 | ✅ | 本輪手冊新增行以 `grep -oE '\]\([^)]*\)'` 掃過，**一條 markdown 連結都沒有**——新增內容是純文字表格列與行內反引號，沒有任何指向 `skills/`、`templates/`、`docs/pilot/` 的連結，連結改寫規則這輪沒有作用對象。既有連結未被觸碰。 |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容只描述 lint 檢查項擋什麼，不含憑證、內部網址、個資。
- **內部路徑與代號**：新增行提到 `make check` 與 `rule-marks`（工具名與檢查項名），兩者對外部讀者都自足；`make check` 在同段既有文字裡已經出現過，前後文讀得通。新增行未引入任何 `skills/`／`docs/pilot/` 路徑。
- **連結可達性**：本輪未新增、未修改任何連結；`--selfcheck` 的 `anchors`（手冊內部錨點 9 條）與 `internal-links`（相對連結 67 條）全綠。

## 4. 未通過項目

無。

補記一項**已知、且刻意不在本單處理**的缺口（不影響本次 verdict）：07 章那張表現在誠實標示為「舉例」，但仍只列 5 項（9 項中的 5 項）。是否要把 `big-files`／`internal-links`／`handbook-stamp`／`mirror-recon` 四項的「真實缺陷」敘述補進手冊，屬說明層的編輯判斷，成因單（MYL-41／42／44／54）均已結案，依 `D1`～`D4` 不宜掛在本單擴寫；已在工單留言記錄，由 Scrum Master 判斷要不要另立單。

## Verdict

**✅ APPROVED**
