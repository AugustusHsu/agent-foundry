---
issue: MYL-68
verdict: APPROVED
handbook_commit: 2699572b2641cfa1b2f466841838d01675a2a794
reviewer: Tech Lead
reviewed_at: 2026-09-05
---

# 發佈審查記錄：MYL-68 手冊版本號規範改四碼 `handbook-v<a>.<b>.<c>.<d>`

## 1. 變更範圍

手冊版本號從單軸 `handbook-v<N>` 改為四碼 `handbook-v<a>.<b>.<c>.<d>`（protocol 新增
`V4`），三章跟著改敘述、四章推同步戳記。**實質內容變更集中在 07 章第 6 節**，新增一
張逐位判準表；02／04 兩章是把「發一版」的說法對齊新形狀。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `2699572b2641cfa1b2f466841838d01675a2a794` |
| 變更檔案 | `02-commands.md`、`04-decision-points.md`、`07-workflows.md`（實質）；`03-workflow.md`、`06-org-structure.md`（僅戳記） |
| 來源工單 | MYL-68（MYL-62 裁定卡 `adffcbd8` 的附帶要求） |

逐章比對：

| 章 | 改了什麼 |
| --- | --- |
| `02-commands.md` | 「手冊定版」列：觸發語從「手冊發 v2」改為「手冊定一版」（舊寫法在四碼下不成立），tag 形狀改四碼，並說明 agent 會先算出該動哪一位 |
| `04-decision-points.md` | 關卡 C 的「手冊發一版」段：tag 形狀改四碼＋指向 07 章的進位規則；「站上同時留住 `v1`、`v2`…」改為不綁死版號的說法 |
| `07-workflows.md` | 第 6 節：表格 tag 形狀改四碼；新增「版本號是四碼」整段＋逐位判準表（`a` 違規／`b` 純新增／`c` 敘述／`d` 建置）；「發出去的版本不重打」由「發 `handbook-v2`」改為「遞增一位」 |
| `03`／`06` | 只有第 3 行的 protocol 對照戳記推到 `e62e42c`，內文一字未動 |

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | `git merge-base --is-ancestor 2699572 main` 回 0；`main` 現為 `d8273c1`（合併 commit），已 push 到 `origin/main`（`6d4cec3..d8273c1`） |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --stat 6d4cec3..HEAD -- docs/handbook/` 列出 5 檔，全在該目錄內。本工單同時動了 protocol、`.foundry/config.yml`、`tools/`、`scripts/`、README 與雙入口檔，**那些都不在同步範圍**，投影腳本只讀 `docs/handbook/` |
| 3 | 私有連結改寫輸出無異常 | ✅ | 新增行裡的連結只有 `](04-decision-points.md)` 與 `](07-workflows.md)` 兩種，都是手冊章間相對連結，wiki 側是平的頁面結構、腳本原樣保留。**本次沒有新增任何指向 `skills/`、`templates/`、`docs/pilot/` 的連結**，故 `link_policy: absolute` 的改寫路徑這次無新增輸入 |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容只有版本號的四位語意與進位規則。提到的 `handbook-version-tags`
  規則名、Settings → Rules → Rulesets 路徑、`GH013` 錯誤碼都是 MYL-62 已發佈過的內容，
  且是這個 public repo 上任何人打開 Rules 頁面就看得到的公開設定。
- **內部路徑與代號**：07 章新增段落提到 **SuperOD** 這個專案名（「跟你其他專案（SuperOD）
  同一套形狀」）。**判定可公開**：只出現專案代號，不帶路徑、不帶主機名、不帶該專案任何
  內容或設定；對外部讀者讀起來是「這套版本號沿用作者既有慣例」，語意完整。⚠️ 這是本次
  唯一需要判斷的一格——`scripts/tag_release.py`、`docs/development/git_flow.md`、自架
  GitLab 位址、實際版號 `superod-bin_v0.0.5.7` 這些查證細節**刻意只留在工單留言與 protocol
  違反段**（protocol 不發佈），沒有寫進手冊。
- **連結可達性**：新增的兩條章間連結目標章節都存在且已在 nav 內（`--selfcheck` 的
  `internal-links` 與 `nav-sync` 均通過）。新增的是表格與段落，未新增標題，故不影響既有錨點；
  `anchors` 檢查 9 個內部錨點全通過。

## 4. 未通過項目

無。

補一則**不屬未通過、但發佈後仍待完成**的事實，以免讀者誤以為本記錄涵蓋了整件事：本記錄
只涵蓋 `docs/handbook/` 的同步（前四步）。使用者裁定的「已發出的 `v1` 換成 `v0.0.0.1`」
需要**打 tag（`V1`，使用者專屬）＋刪除站上 `v1`（`G-C`）**，那兩步不在 P2 範圍內，也不是
本記錄的證據對象。在那兩步完成前，精裝站上仍是舊形狀的 `v1`，而 `README.md` 已據實註明
「站上現為 `v1`，那是 `V4` 之前的舊形狀」。

## Verdict

**✅ APPROVED**
