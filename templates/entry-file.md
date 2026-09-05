# 接手入口檔模板（`CLAUDE.md` ／ `AGENTS.md`）

> **這份模板產出兩個檔案**，放在導入專案的 repo 根：
> `CLAUDE.md`（Claude Code 讀）與 `AGENTS.md`（Codex 及其他 harness 讀）。
> **§0 共用正文逐字相同，只有 §8 工具名對應不同**——這樣換 runtime 不必重寫一份規範。
>
> 由 `foundry-init`（新專案）或 `foundry-adopt`（既有專案）產生。
> 產生後由執行者填入 `{}` 佔位符，並刪除本說明區塊與各段的引導文字。
>
> **為什麼需要這個檔**：沒有入口檔，每個新 session 都得從 `git ls-files` 自己摸索
> 專案結構、規範位置、已知陷阱——同一份摸索成本每次重付。

---

## 0. 產生方式

1. 把下方「共用正文」原樣寫入 `CLAUDE.md` 與 `AGENTS.md`，**含 `FOUNDRY:SHARED-BODY` 標記註解**
   （標記是給 `foundry-lint --selfcheck` 比對用的，不可刪）。
2. 各自接上對應的「工具名對應」段（§8-A 給 `CLAUDE.md`、§8-B 給 `AGENTS.md`）。
3. 各自的一級標題不同，寫在標記**之前**：
   - `CLAUDE.md` → `# {專案名} — 接手入口（Claude Code）`
   - `AGENTS.md` → `# {專案名} — 接手入口（Codex／其他 harness）`
4. 跑 `python3 tools/foundry-lint/foundry_lint.py --selfcheck` 確認兩份正文一致，
   且 §4 的大檔清單沒有漏列（`big-files` 這一項）。

> **維護規則的權威在 `skills/foundry-ai-platform/SKILL.md` §5**：哪一段共用、哪一段允許各 harness 分岔
> （判準：只換說法、不換規則）、以及**新增第三個 harness 要動哪些檔**都寫在那裡。
> 本模板只負責產檔，不重複那份規則。
>
> ⚠️ 要新增第三個入口檔之前先讀該節最後一點：`--selfcheck` 的 `entry-sync`
> **寫死只比對 `CLAUDE.md` 與 `AGENTS.md`**，不一併改它的話，第三份的共用正文漂了不會有任何地方報錯。

---

## 共用正文（兩檔逐字相同）

```markdown
<!-- FOUNDRY:SHARED-BODY:BEGIN -->
> **本檔的角色**：讓一個沒有前文的 session 在 60 秒內知道
> 「這是什麼、規則在哪、先讀什麼、哪裡有坑」。
>
> **本檔的自我約束（重要）**：
> 只放三種東西——**摘要**、**正版文件的指向**、**文件裡查不到的實況**。
> 詳細規範一律以指向的文件為準。**不要把規範內容抄進本檔**——抄過來的那份會過期，
> 於是 repo 裡就有了兩份互相矛盾的規則，而讀到本檔的人不會知道自己讀的是舊的。

## 1. 這個專案是什麼

{一到三句：這個專案在做什麼、給誰用、目前處於什麼階段}

本專案採用 Foundry 開發流程：規則層在 `skills/`／`docs/`／`templates/`，
執行層（工單／狀態）在 {平台名}，兩者分工見 protocol 第 6 節三層文檔體系。

## 2. 開場必讀順序

1. **`skills/foundry-protocol/SKILL.md`** — 全隊硬規則，每個 agent 必掛。
   ⚠️ 約 40KB，**不要整份讀**（見 §4）。先 `grep -n '^#\{1,3\} '` 取標題地圖，再讀需要的節。
2. **`docs/standards/known-drift.md`** — 已知漂移與反悔錄（若尚未建立，第一次踩坑時建）。
   **動手前讀這份**：哪些操作會失敗、哪些提案已經被否決過、哪些缺口是刻意保留的。
3. **自己的角色 skill**（若專案有配置角色分工）。
4. **`.foundry/config.yml`** — 本專案的關卡與 push 授權設定（**agent 不得自行改動**）。

## 3. 地圖：我想要…→前往

{先給一張「意圖 → 去處」表：列出這個專案最常見的幾種來意（改規則／改文件／
 加檢查／跑測試／發佈…）。每一格只給去處，**不要把該處的規則抄過來**——
 抄過來的那份會過期。想不出五列以上，就表示這個專案還不需要這張表，
 整段刪掉、只留目錄結構。}

| 我想要… | 前往 |
| --- | --- |
| {意圖} | {路徑}｛，外加一句「去了要先注意什麼」｝ |

### 目錄結構

{用樹狀圖列出 repo 主要目錄，每個目錄一行說明它裝什麼。
 只列接手者需要知道的，不必窮舉。}

## 4. Context 預算（protocol 第 10 節 `C1`～`C5`）

**超過 20KB 的檔案禁止整份載入**，先 `grep -n` 定位再局部讀。

<!-- FOUNDRY:BIG-FILES:BEGIN -->
下表**故意不寫每個檔案幾 KB**——寫死在散文裡的數字沒有人會回來改，只會愈漂愈遠；
要現值自己 `ls -l`。清單本身則是機械維護的：`--selfcheck` 的 `big-files` 會掃
`skills/` 與 `docs/`（不含 `docs/features/`，那是各模組自己的交付物），
**每個 12KB 以上的 .md 都必須列在下表**，漏列或路徑失效就擋下。
門檻以下的檔案要不要一併列出，屬編輯判斷。

| 檔案 | 通常只需要哪一部分 |
| --- | --- |
| {路徑} | {為什麼大／通常只需要哪一節} |
<!-- FOUNDRY:BIG-FILES:END -->

**減法原則**：先給最小必要上下文跑一輪，不滿意再補。

## 5. 最常被違反的硬規則（速查，權威在 protocol）

引用規則請用**穩定 ID**（protocol 第 11 節），不要用節號。

- `H1`～`H6` **觸發式 HITL 閘門**：未決事項未解／規格矛盾／要花錢／要對外／
  破壞性操作／平台權限外。**口訣：拿不準要不要問的時候，就是要問。**
- **鐵律：絕不自作主張採用建議值。**
- `G-C` **對外／不可逆核可不可調降**。
- `W1`／`W2` **永久文件 vs 一次性意圖紀錄**：實作計畫、探索筆記寫工單留言，不進版控。
- **一單一分支**，分支名帶工單編號；commit 用 gitmoji ＋繁體中文標題。
- **push 授權以 `.foundry/config.yml` 的 `push` 段為準**；`main_push` 恆為 `user`，無例外。

## 6. 指令速查

{列出這個專案實際會用到的指令：建置、測試、lint、啟動。
 每條附一句「什麼時候用」。沒有的就不要列佔位指令。}

## 7. {專案特有的義務或陷阱}

{例：動到某目錄要連帶更新什麼、發佈前要跑什麼、哪兩份設定必須同步。
 沒有就整節刪掉，不要留空殼。}
<!-- FOUNDRY:SHARED-BODY:END -->
```

---

## 8-A. 工具名對應（寫進 `CLAUDE.md`）

```markdown
## 8. 工具名對應（Claude Code）

| 文件裡的說法 | 在 Claude Code 中 |
| --- | --- |
| 「載入 skill」 | skill 由 runtime 載入後自動進 context；`skills/` 下的 SKILL.md 亦可直接讀取 |
| 「局部讀取檔案」 | `Read` 工具帶 `offset`／`limit`，或 `Grep` 定位後再讀 |
| 「執行指令」 | `Bash` 工具 |
| 「發互動卡」 | {依平台填：Paperclip 為 `POST /api/issues/{id}/interactions`；github 模式為在 issue 留言並掛 `needs-decision` label} |

- 本檔為 Claude Code 的入口；Codex 及其他 harness 讀 `AGENTS.md`（正文相同）。
- **兩檔的共用正文必須逐字相同**（`FOUNDRY:SHARED-BODY` 標記之間），
  由 `foundry-lint --selfcheck` 機械比對；改一份就要改另一份。
```

## 8-B. 工具名對應（寫進 `AGENTS.md`）

```markdown
## 8. 工具名對應（Codex／通用 harness）

| 文件裡的說法 | 在 Codex／通用 harness 中 |
| --- | --- |
| 「載入 skill」 | **無自動載入機制**——把 protocol 與自己的角色 skill 當一般檔案讀進來（守 §4 的 context 預算） |
| 「局部讀取檔案」 | `sed -n 'A,Bp' <檔案>`，或 `grep -n` 定位後再讀該區間 |
| 「執行指令」 | 直接在 shell 執行 |
| 「發互動卡」 | {同 8-A 依平台填}；平台無互動卡機制時，改為輸出 .md 報告請使用者批示，**等到明確回覆為止，不得代答** |

- 本檔為 Codex 及其他 harness 的入口；Claude Code 讀 `CLAUDE.md`（正文相同）。
- **兩檔的共用正文必須逐字相同**（`FOUNDRY:SHARED-BODY` 標記之間），
  由 `foundry-lint --selfcheck` 機械比對；改一份就要改另一份。
```
