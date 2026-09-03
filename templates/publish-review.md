---
issue: MYL-xx
verdict: APPROVED
handbook_commit: {完整 40 碼 sha}
reviewer: {agent 角色名}
reviewed_at: {YYYY-MM-DD}
---

# 發佈審查記錄：{工單編號} {工單標題}

> 由手冊變更工單的執行者自己撰寫（MYL-23 分級表 P2：拍板者＝執行者本人，
> 審查內容＝逐項自檢前提，Scrum Master 巡檢兜底）。存檔於
> `docs/publish-reviews/<工單編號>.md`，commit 後 `scripts/publish-handbook.sh`
> 才會放行。每個欄位下的引導文字填寫時整段刪除。
>
> **frontmatter 是給腳本讀的，格式不可改**：
> - `verdict` 必須是 `APPROVED` 才放行（未通過就填 `CHANGES REQUESTED`，或先不要建這個檔）。
> - `handbook_commit` 必須等於 `git log -1 --format=%H -- docs/handbook` 的輸出。
>   手冊在審查後又改了，就要重新自檢並更新這一欄——舊 sha 不會放行。

## 1. 變更範圍

（這次要同步到公開站的手冊變更：哪幾章、改了什麼。給 commit 區間或檔案清單。）

| 項目 | 值 |
| --- | --- |
| 手冊 commit | {sha} |
| 變更檔案 | {docs/handbook/xx.md, …} |
| 來源工單 | {MYL-xx} |

## 2. P2 前提逐項自檢

（三項全成立才可填 `APPROVED`。每項都要寫「怎麼驗的」，不是打勾了事。）

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進私有 main | ✅ / ❌ | {`git merge-base --is-ancestor` 或 `git log main` 輸出} |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ / ❌ | {變更檔案清單，確認沒有其他目錄混入} |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ / ❌ | {腳本 `filtered:` 行；或逐項確認新增內容沒有指向 skills/、templates/、docs/pilot/ 的連結} |

## 3. 公開適切性檢查

（過濾規則只擋連結，擋不住內文。逐項確認新增內容沒有不該公開的東西；沒有就寫「無」。）

- **機敏資訊**：（憑證、內部網址、個資、未公開的商業資訊）
- **內部路徑與代號**：（提到 `skills/`、`docs/pilot/` 等私有路徑時，前後文對外部讀者是否仍讀得通）
- **連結可達性**：（章節間的相對連結、錨點在公開站上是否有效）

## 4. 未通過項目

（Verdict 為 ❌ 時必填，具體到「改哪個檔案的哪一段才算過」。沒有就寫「無」。）

## Verdict

**✅ APPROVED** 或 **❌ CHANGES REQUESTED**（二選一；與 frontmatter 的 `verdict` 必須一致）
