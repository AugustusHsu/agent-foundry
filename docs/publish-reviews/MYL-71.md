---
issue: MYL-71
verdict: APPROVED
handbook_commit: 0e94307908974d592e8b22e773f0d22da3e4dcc2
reviewer: Tech Lead
reviewed_at: 2026-09-05
---

# 發佈審查記錄：MYL-71 版本號命名空間 `V5` ＋ `version-shape` 自檢（併 MYL-70）

實作單為 MYL-72；MYL-70（`V1` 措辭缺口）同分支併入、由本單交付物銷案。

## 1. 變更範圍

protocol 第 7 節新增 `V5`「版本號命名空間」小節、`V1` 補「使用者當次明確指示」例外、
第 11 節登記 `V5`；`foundry-lint` 新增 `version-shape` 自檢；repo 內八處舊形狀版本號收斂。
手冊側三章跟著動——**兩章是規則新增的說明、一章是舊形狀收斂**：

| 章 | 改了什麼 | 對應規則 |
| --- | --- | --- |
| `03-workflow.md` | 第五步的 tag 佔位符由舊形狀改為四碼，並補指第 7 章第 6 節的進位規則 | `V4`／`V5` |
| `04-decision-points.md` | 新增一則：使用者當次明確說「打／刪這個 tag」即關卡 C 核可，agent 不再發卡；附三項義務（只算那一次／留痕／提醒切回 ruleset） | `V1` 增補 |
| `07-workflows.md` | 第 6 節新增一則：四碼只管手冊，另一個受管號碼是 `foundry` 單一整數，其餘 `v` 開頭號碼是外來的、不得為求統一去改 | `V5` |

`06-org-structure.md` 本次不動：`V5`／`V1` 增補都不涉及角色編制或分工。
四章戳記維持 `e62e42c`——本次 protocol 與手冊在**同一顆 commit**（`0e94307`），
依 `unsynced_protocol_commits()` 的判準即為已同步，無戳記可推（戳記指不到自己那顆）。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `0e94307908974d592e8b22e773f0d22da3e4dcc2` |
| 變更檔案 | `docs/handbook/03-workflow.md`、`04-decision-points.md`、`07-workflows.md` |
| 來源工單 | MYL-71（實作 MYL-72，併 MYL-70） |
| 合併 commit | `fdf2c8b`（`--no-ff`，已 push `origin/main`） |

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進 main | ✅ | `git merge --no-ff docs/MYL-71-version-namespace` → `fdf2c8b`；`git push origin main` 回 `0487a3c..fdf2c8b`，本地 main 與 `origin/main` 一致 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff --name-only 0487a3c..HEAD -- docs/handbook` 只列出上表三章；同一顆 commit 的其他檔案（protocol、lint、README、HLD、腳本）不在投影範圍內，腳本只讀 `docs/handbook/` |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | 新增內容的連結全部指向手冊內部（`04-decision-points.md`、`07-workflows.md`），無指向 `skills/`／`templates/`／`docs/pilot/` 的相對連結；`internal-links` 自檢 70 條全綠 |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容只有版本號的分類語意、`handbook-version-tags` 這條 ruleset 的名稱與
  Settings → Rules → Rulesets 路徑（本 repo 為 public，任何人打開 Rules 頁面就看得到），
  以及 `version-shape` 這個 lint 檢查名。無憑證、無內部網址、無個資。
- **內部路徑與代號**：`07-workflows.md` 新增段提到 `.foundry/config.yml` 與 protocol `V5`——
  兩者在既有章節都已出現過，前後文對外部讀者讀得通（該段自己說明了 `foundry` 這一欄答的是什麼問題）。
  `version-shape` 以「agent 這邊有一道 lint」的措辭出現，不要求讀者知道實作在哪。
- **連結可達性**：新增的兩條相對連結 `07-workflows.md`／`04-decision-points.md` 為章節間互指，
  `internal-links` 與 `anchors` 自檢均通過；無新增錨點連結。

## 4. 未通過項目

無。

## 5. 破例記錄（使用者定調「這次算破例的一次」）

三點皆有使用者裁定為依據，逐點記明違反的是什麼、憑什麼做：

| # | 破例內容 | 違反 | 依據與實際處置 |
| --- | --- | --- | --- |
| ① | 刪除已發佈的 tag `handbook-v1`（本地 ＋ `origin`） | `V3` **字面** | 裁定卡 `c349dc36` Q1（2026-09-05 10:46）＝使用者當次明確指示＝關卡 `G-C` 核可。實質理由：站上的 `v1` 已於 MYL-68 由使用者刪除，`versions.json` 現只有 `v0.0.0.1`，此 tag 已是指向不存在版本的**懸空指標**——`V3` 保護的對象（站上那一版）不在了。依 `V1` 新增例外的三項義務執行：刪除前把 ruleset 實測值（`enforcement: active`、`rules: ['creation']`、`bypass_actors: []`）記入 MYL-72 留言留痕；本次**不需切 Disabled**（規則只放 `creation`，刪除不在規則內）；破例明文即本列。⚠️ 副作用：這個 tag 名**再也建不回來**，除非使用者先把 ruleset 切 Disabled。 |
| ② | 動到明文「逐字歸檔，未作任何內容修改」的歸檔本 `docs/features/cross-platform/HLD.md` | 該檔自身的歸檔約定 | 裁定卡 `c349dc36` Q2 選「刪除版本欄位」。移除標題列的 `> 版本：v1.1（2026-09-03）` 後，「未作任何內容修改」即成不實敘述，故**同一次**改寫歸檔說明與檔首註解為據實敘述（MYL-35 逐字照錄；MYL-71 依裁定移除版本欄位，其餘未動）。`gap-analysis.md` 的「逐字歸檔」**未動**——那是 MYL-35 當時的行動紀錄，執行後仍為真。 |
| ③ | 改寫 protocol 規則本體的既有措辭（`V3` 內文、`V4` 違反段的反例） | 無明文禁止，屬慎重事項 | 只改**舊形狀示例**，判準一字未動。`V4` 違反段那一處是新發現的（計畫的 D 清單漏列，由 `version-shape` 跑出來）：原文拿舊形狀 tag 名當「位數不足會被擋」的反例，改寫為「版本號只有一到三位，如 `v1`／`v1.1`／`v1.1.1`」——語意不變，且完整的反例字串仍保留在 `.foundry/config.yml` 的註解裡（該檔在豁免清單內）。 |

## Verdict

**✅ APPROVED**
