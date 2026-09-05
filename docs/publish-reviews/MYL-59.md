---
issue: MYL-59
verdict: APPROVED
handbook_commit: cf7d5612b15b1d60720cdf383ff4aefe7675e12a
reviewer: Developer
reviewed_at: 2026-09-05
---

# 發佈審查記錄：MYL-59 `P1` 改以「有沒有新增公開面」為判準

## 1. 變更範圍

這次要同步的是**常設授權的判準換了一個座標**。`P1` 原本綁在「repo 是私有的」這個
事實上，而 `AugustusHsu/agent-foundry` 現在是 public——照字面讀，本 repo 的每一次
例行推送都不落在任何一格，再照「拿不準往上取級」就變成推一次發一次卡。手冊這兩處
是使用者看到的那一份說明，不改的話它會繼續告訴使用者「你核可的是私有 repo 的推送」，
而使用者實際上會一直收到不該收的卡。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `cf7d5612b15b1d60720cdf383ff4aefe7675e12a` |
| 變更檔案 | `04-decision-points.md`、`06-org-structure.md`（實質）；`03-workflow.md`、`07-workflows.md`（僅戳記） |
| 來源工單 | MYL-59 |
| 比對基準 | 上一份已核可記錄 MYL-62 的 `5a8b627`；區間 `5a8b627..cf7d561 -- docs/handbook/` |

實質變更兩處，深淺不同：

- `06`（哪些決定回到你手上）＝**權威版**：`P1` 括號裡的「私有 repo」拿掉，並補上判準本身
  ——「這次推送有沒有讓新的東西變成公開」，外加一句把本 repo 現況講明（是 public，但推
  一條工作分支不會多公開任何東西）。
- `04`（關卡 C 常設授權的例子）＝**一句話的舉例**，只把「私有 repo 例行推送」改成「例行
  推送」。這裡是舉例不是定義，展開判準會喧賓奪主，判準留在 `06` 與 protocol。

`04` 同段另有兩處「離開私有環境」的措辭（關卡 C 的觸發描述、`H4` 那一列）**刻意未動**：
它們講的是「東西要不要出去」這件事本身，不是 `P1` 的適用範圍；改動 `H4` 的觸發措辭
會動到 HITL 閘門的判準，超出本單授權（MYL-54 卡 `784fff9e` 只授權補分級表這一格）。
這一項已在工單留言列為建議，由使用者決定要不要另開單。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | `docs/MYL-59-push-tier-public-repo` 經 `0ba2e27`（`--no-ff`）合併，`c75f373..0ba2e27 main -> main` 已推上 origin，分支已 `git branch -d` 刪除。`git log -1 --format=%H -- docs/handbook` ＝ `cf7d561…`，與 frontmatter 一致 |
| 2 | 同步範圍僅限 `docs/handbook/` | ✅ | 本工單另動了 `skills/foundry-protocol/SKILL.md`（規則本體，不在發佈範圍內）。`git diff 5a8b627..cf7d561 --name-only -- docs/handbook/` 只回四章，其中兩章是戳記-only |
| 3 | 私有連結過濾／改寫輸出無異常 | ✅ | 兩處實質變更**都在既有句子裡替換文字，沒有新增任何連結**（`06` 那句原有的 `.foundry/config.yml` 與 protocol 連結原樣保留）。`--selfcheck` 的 `internal-links` 67 條、`anchors` 9 條、`nav-sync` 8 章全過，數量與 MYL-62 那份一致 |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增的文字只講「repo 是 public」與判準本身，這兩件事讀者打開 repo
  就看得到、也正是他要理解授權範圍所需的資訊。
- **這段等於公告「agent 可以自行 push 這個 public repo」——是否該公開**：是。它公告的
  不是權限而是**規則**：能推的前提是具備 repo 寫入權，而這個 repo 的寫入權只有擁有者
  一人（所有 agent 共用同一個 GitHub 身分，即 `known-drift` `L22`／`R5` 的根因）。對沒有
  寫入權的讀者，知道這條規則不多出任何可利用的面；藏起來反而讓手冊少掉使用者判斷
  「這張卡我為什麼收得到／收不到」所需的那一句。
- **內部路徑與代號**：未新增內部路徑。`MYL-59`／`MYL-23` 這類工單編號在手冊既有行文中
  本來就通行（用來指出裁定出處）；互動卡 id `784fff9e` **只寫在 protocol、本記錄與工單
  留言，沒有寫進手冊正文**。
- **連結可達性**：本次未新增或改動任何連結，故無新的可達性風險；既有連結由 `internal-links`
  與 `anchors` 兩項檢查覆蓋，全過。

## 4. 未通過項目

無。

一項**刻意不做**、留在這裡備查：`scripts/lib/publish-gate.sh` 的錯誤訊息與註解仍寫著
「私有 repo agent-foundry」「已合併進私有 main」。那兩句是腳本內部字串、不是規則權威
（權威是 protocol 第 9 節分級表，本次已改），且改動發佈閘門本身的檔案不在本單範圍內
（本單只授權改分級表條文與其引用）。已在工單留言列為建議。

## Verdict

**✅ APPROVED**
