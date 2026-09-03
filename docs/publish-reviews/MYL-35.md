---
issue: MYL-35
verdict: APPROVED
handbook_commit: 0f7245feb8e27892e10744d8189e30b0ce6ec0db
reviewer: CEO
reviewed_at: 2026-09-03
---

# 發佈審查記錄：MYL-35 分析目前開發流程跟套用到其他開發流程的差異

## 1. 變更範圍

第 8 章「跨平台」三處增修，皆為 MYL-35 規範修訂的說明層同步：① 平台清單補 `paperclip` 一項並點明「本團隊跑的就是這個 adapter，不是另一套流程」；② 新增「換平台時該動哪三個地方」的段落（通用規則／adapter／設定檔）；③ push 權限段補一條子項，說明 agent-foundry 自身的 P1 例外為何無法寫進 `.foundry/config.yml`（G7 裁定選項 A）。未新增章節、未動 nav。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | 0f7245feb8e27892e10744d8189e30b0ce6ec0db（合併 commit a474c4a） |
| 變更檔案 | docs/handbook/08-cross-platform.md（同區間另含 `skills/`、`.foundry/`、`docs/features/` 之變更，不在同步範圍內） |
| 來源工單 | MYL-35 |

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進私有 main | ✅ | `docs/MYL-35-platform-consistency` 已 `--no-ff` 合併為 `a474c4a` 並 push origin/main（`9d47b72..a474c4a`）；`main` 與 `origin/main` 同為 `a474c4a`，工單分支本地與遠端皆已刪除 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | `git diff 9d47b72..a474c4a --stat -- docs/handbook/` ＝ `docs/handbook/08-cross-platform.md` 單檔（+5 −1）。同區間的 `skills/`、`.foundry/config.yml`、`docs/features/cross-platform/` 屬規則層與設計文件，腳本只讀 `docs/handbook/`，公開站僅收到該章異動 |
| 3 | 私有連結過濾輸出檢查無異常 | ✅ | 本次新增內容只有一條連結 `[第 6 章](06-org-structure.md)`——章內相對連結，公開站各章平移後仍可解析，與既有章節（如第 4 章連結）寫法一致。未新增任何指向 `skills/`、`templates/`、`docs/pilot/` 或私有 repo 的超連結，過濾器不應對本次內容作動；腳本 `filtered:` 輸出見工單結案留言 |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增文字為流程層說明（platform 枚舉、三層歸屬、push 授權的可攜性限制），不含憑證、內部網址、個資或商業資訊。特別確認：`.foundry/config.yml` 內的 `project_id`／`company_id` 屬私有設定檔，**未**出現在手冊任何一行。
- **內部路徑與代號**：新增文字提到 `foundry-protocol`、`.foundry/config.yml`、`adapters/`，皆為 inline code 而非超連結，且該章原本就以同樣方式描述這些路徑，外部讀者讀得通（前後文有解釋各自是什麼）。工單代號 MYL-28／MYL-35 沿用手冊既有慣例（第 2、6、7 章同樣引用 MYL-xx）。
- **連結可達性**：新增的 `06-org-structure.md` 相對連結，目標章節已存在於公開站；未修改既有連結或錨點，未動 nav 條目。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
