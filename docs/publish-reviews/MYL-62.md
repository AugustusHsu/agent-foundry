---
issue: MYL-62
verdict: APPROVED
handbook_commit: 5a8b62700f8e8589eb3a58938a01b5d79159d429
reviewer: Tech Lead
reviewed_at: 2026-09-05
---

# 發佈審查記錄：MYL-62 `V1` 補機械後盾——`handbook-v*` tag ruleset

## 1. 變更範圍

這次要同步的是「打 tag 前多了一道要自己解開的鎖」。使用者在卡 `adffcbd8` 裁定
選項 A（ruleset 設 `active`、bypass 留空），代價就是**連使用者自己也推不了
`handbook-v*`**——這件事不寫進手冊，下次發版時只會看到一句 `GH013` 而不知道
該去哪裡切開關。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `5a8b62700f8e8589eb3a58938a01b5d79159d429` |
| 變更檔案 | `03-workflow.md`、`04-decision-points.md`、`07-workflows.md`（實質）；`06-org-structure.md`（僅戳記） |
| 來源工單 | MYL-62 |
| 比對基準 | 上一份已核可記錄 MYL-63 的 `477350b`；區間 `477350b..5a8b627 -- docs/handbook/` |

實質新增三處，講的是同一件事、深淺不同：

- `04`（關卡 C）＝**權威版**：規則名、為什麼擋的是所有人、UI 路徑、忘了切會看到什麼錯誤、它買到的是什麼。
- `03`（第五步）＝**一句話＋指回 04**，因為第五步本來就只是索引。
- `07`（精裝站）＝**流程視角**，附帶說明對 `V3` 的副作用（刪掉的 tag 建不回同名）。

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | `feat/MYL-62-tag-ruleset` 經 `2bb0125` 合併，`a1b0cb5..2bb0125 main -> main` 已推上 origin；戳記 commit `5a8b627` 直接落在 main 上。`git log -1 --format=%H -- docs/handbook` ＝ `5a8b627…`，與 frontmatter 一致 |
| 2 | 同步範圍僅限 `docs/handbook/` | ✅ | 本工單另動了 `skills/foundry-protocol/SKILL.md` 與 `docs/standards/known-drift.md`，**兩者都不在發佈範圍內**（前者是規則本體、後者標明不發佈）。`git diff 477350b..5a8b627 --name-only -- docs/handbook/` 只回四章 |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | 新增內容只有兩條相對連結，都是**章對章**（`03`→`04-decision-points.md`、`07`→`04-decision-points.md`），不是指向 `skills/`／`templates/`／`docs/pilot/` 的 repo 內部路徑，過濾規則不會動到它們。`--selfcheck` 的 `internal-links` 67 條、`anchors` 9 條全過 |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容提到的 `handbook-version-tags`、Settings → Rules → Rulesets 路徑、`GH013` 錯誤碼，全是這個 public repo 上任何人打開 Rules 頁面就看得到的公開設定與 GitHub 的標準錯誤碼。ruleset 的數字 id（`22327706`）**刻意只寫在 `known-drift.md`**，那份不發佈。
- **這段等於公告「有一條 guard，而且它關得掉」——是否該公開**：是，而且這正是它被標成 `【自律】` 的理由。關得掉的前提是具備 repo 寫入權，而這個 repo 的寫入權就只有擁有者一人（agent 共用同一個身分，那是 `L22` 的根因本身）。對沒有寫入權的讀者，知道這件事不多出任何可利用的面；對有寫入權的讀者，這是他們發版時必須知道的操作。把它藏起來只會讓手冊少一段、下次發版多一次卡關。
- **內部路徑與代號**：`.foundry/config.yml` 在 `07` 原本就出現過，本次未新增此類引用。`adffcbd8`（卡片 id）、`MYL-62` 只出現在本審查記錄與 protocol，**沒有寫進手冊正文**。
- **連結可達性**：兩條新增連結的目標 `04-decision-points.md` 已在 `mkdocs.yml` nav 內，`nav-sync` 通過；沒有新增錨點連結。

## 4. 未通過項目

無。

一項**刻意不做**、留在這裡備查：`07` 寫了「已發佈的 tag 就算被刪掉也建不回同一個名字」，那是 `creation` 規則的副作用；但這條 ruleset **只放 `creation`**，`push --force` 移動既有 tag 與刪除 tag 都仍然放行。手冊沒有把這個缺口攤開講，因為對讀者而言可操作的結論就是「別動已發佈的 tag」（`V3` 原本就這麼寫）；完整的缺口敘述放在 protocol `V1`／`V3` 違反段與 `known-drift` `L22`。要補滿得加 `update`／`deletion`，那是改既有 ruleset 的範圍，屬 `G-C`，沒有使用者裁定不自行加。

## Verdict

**✅ APPROVED**
