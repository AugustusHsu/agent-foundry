---
issue: MYL-36
verdict: APPROVED
handbook_commit: 31f80ff897949c5cb18506f85179b5b5736d7ef9
reviewer: CEO
reviewed_at: 2026-09-03
---

# 發佈審查記錄：MYL-36 參考外部專案/文章改善專案（P10 模型供應商路由）

本工單的第二份發佈記錄。第一份（`MYL-36.md`，`handbook_commit c1d020b`）涵蓋 P1～P9；
本份涵蓋使用者裁定後才實作的 P10。

## 1. 變更範圍

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `31f80ff897949c5cb18506f85179b5b5736d7ef9` |
| 變更檔案 | `docs/handbook/07-workflows.md`、`docs/handbook/index.md` |
| 來源工單 | MYL-36 |

具體變更三項：

1. **新增第 8 條 workflow「模型供應商路由」**：目的（觀點互補）、三條規則（`M4`／`M5`／`M6`）、
   盤點指令，以及「目前是能力就位、開關沒開」的現況說明。
2. **第 4 條加一句軸線區分**：模型分層管「用多強的模型」，第 8 條管「用哪一家的模型」。
3. **順帶修正兩處既有錯誤**（發現於本輪，非本次新增內容造成）：
   - 第 5 條「規範修訂」仍寫「改文件 → 重新匯入 skill」與「agent 會發卡請你做最後的重新匯入」。
     反悔錄 `R3` 已證明這是誤診（參照式安裝、commit 即生效）。前一輪修了手冊第 2、5 章，
     **漏了第 7 章這兩處**——而這條錯誤在公開站上會讓使用者收到不必要的卡片並白做一次操作。
   - `index.md` 寫「六條固定跑法總覽」，但第 7 章當時已有七條。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進私有 main | ✅ | `31f80ff` 由 merge commit `941f1d8` 併入 `main`；本記錄 commit 後一併推送 origin，腳本的 `merge-base --is-ancestor` 對 `main` 與 `origin/main` 兩者都會再驗一次 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --stat 99f989b..HEAD -- docs/handbook/` 僅列 `07-workflows.md`、`index.md` 兩檔。同批 commit 另動 protocol／skills／tools，但那些**不在同步範圍內**，腳本只複製 `docs/handbook/` |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | 新增內容含 3 個連結：`05-troubleshooting.md`、`07-workflows.md`（皆手冊內部，公開站可達）、`../../skills/foundry-protocol/SKILL.md`（私有路徑，過濾規則會拆為純文字——與本章既有的同型連結一致）。發佈後核對 `filtered:` 行 |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容不含憑證、內部網址、個資。提到的兩個 CLI（`claude`／`codex`）
  是公開產品名；**未寫入任何帳號、訂閱層級或額度數字**。
- **內部路徑與代號**：新增內容提到 `tools/model-routing/probe_providers.py` 與
  `skills/foundry-model-routing/SKILL.md`。這兩處是**指令與檔案位置**，與本章既有的
  `tools/foundry-lint/`、`foundry-protocol` 寫法一致；對外部讀者的意義是「這套流程長這樣、
  工具叫這個名字」，讀得通。`M4`／`M5`／`M6` 為規則 ID，同章已有 `H1`～`H6` 等先例。
- **連結可達性**：`#8` 錨點由 `foundry-lint --selfcheck` 的 `anchors` 檢查驗過
  （中文標題的 slug 是 mkdocs 產生的 `8`，不是中文字面——`X3` 踩過的坑）。
  `nav-sync` 確認章節數與兩份 nav 一致（8 篇，本次未新增章節、nav 不變）。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
