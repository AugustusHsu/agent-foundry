# MYL-6 Pilot 試跑記錄

本文件是 Pilot 試跑（MYL-6）的兩份即時追蹤清單，由 Scrum Master 全程維護：

1. **使用者決策點記錄**——使用者在流程中被問到的每個決策點（使用手冊「你要在哪幾個點做決定」一節的原料，對應驗收標準 5）。
2. **卡住的地方清單**——流程卡點：卡在哪、為什麼卡、規範怎麼改（對應驗收標準 3、4）。

記錄規則：事件發生當下就記，不事後補寫；每筆附上對應工單或互動卡，讓證據可追溯。

---

## 一、使用者決策點記錄

### 決策點 #1：Pilot 試跑題目的選定

- **時機**：流程起點，任何階段開跑之前。
- **形式**：互動卡（ask_user_questions，human_only）單選＋自由輸入。選項含使用者自帶題目（最優先）與 CEO 三提案：A. 看板日報小工具、B. foundry-lint 文件檢查器、C. Foundry 文件站。
- **為何需要使用者**：試跑產出應是使用者真的想要的東西；MYL-6 明文禁止 agent 自行挑題開跑。
- **證據**：MYL-6 互動卡 `ask:MYL-6:pilot-topic:v1`（2026-09-02 由 CEO 發出）。
- **結果**：使用者於 2026-09-02 選定 **CEO 提案 B：foundry-lint 文件檢查器**——一個檢查 BRD／PRD／HLD 等文件是否符合 foundry-protocol 模板必備章節的小 CLI。互動卡 `ask:MYL-6:pilot-topic:v1` 已 answered。

### 決策點 #2：foundry-lint 需求層四項取捨（檢查範圍／嚴格度／類型指定／輸出格式）

- **時機**：需求階段（MYL-16），BRD／PRD 起草後、定稿前。
- **形式**：互動卡（ask_user_questions）四題，由 Product Analyst 發出。
- **為何需要使用者**：這四題決定工具的行為邊界，是產品取捨而非技術實作細節，protocol 規定需求層決策點須經使用者確認。
- **證據**：MYL-16 互動卡 `ask:MYL-16:lint-requirements:v1`（2026-09-03 answered）。
- **結果**：(1) 檢查範圍＝六份模板全上；(2) 嚴格度＝單級，缺必備章節即不通過；(3) 文件類型由 `--type` 明確指定，不做自動推斷；(4) 輸出＝人讀文字＋exit code，另提供 `--format json`。BRD／PRD 依此定稿（commit `ac0c180`）。

### 決策點 #3：BRD／PRD 定稿核可

- **時機**：需求階段收尾，交接設計之前。
- **形式**：確認卡（request_confirmation），由 Product Analyst 發出。
- **為何需要使用者**：需求文件是後續所有階段的依據，protocol 要求定稿須經使用者核可才能往下交接。
- **證據**：MYL-16 確認卡 `confirmation:MYL-16:prd-final:ac0c180`。
- **結果**：使用者於 2026-09-03 **核可**，BRD／PRD 以 commit `ac0c180` 為定稿版本。

### 決策點 #4：需求 → 設計交接的承接確認

- **時機**：MYL-16 結單前，Product Analyst 向 Tech Lead 交接時。
- **形式**：確認卡（request_confirmation）。
- **為何需要使用者**：Pilot 期間每段交接都經使用者過目，確認交接內容完整（BRD／PRD 路徑與四項已確認決策）再放行。
- **證據**：MYL-16 確認卡 `confirmation:MYL-16:handoff-techlead:ac0c180`（2026-09-03T01:05 核可）。
- **結果**：核可，Tech Lead 承接開工 MYL-17，MYL-16 結單 `done`。

### 決策點 #5：HLD／LLD 定稿與設計 → 拆單交接核可

- **時機**：設計階段（MYL-17）收尾，Scrum Master 拆實作鏈之前。
- **形式**：確認卡（request_confirmation），由 Tech Lead 發出。
- **為何需要使用者**：設計文件（含 ADR-1～3 技術選型）決定實作方向，核可後 Scrum Master 才能據以拆單。
- **證據**：MYL-17 確認卡 `confirmation:MYL-17:handoff-sm:76f3089`（2026-09-03T01:16 核可）。
- **結果**：核可，HLD／LLD 以 commit `76f3089` 為定稿版本；MYL-18 拆單解除阻塞，拆出 MYL-19（實作）→ MYL-20（審查）→ MYL-21（測試）工單鏈。

### 決策點 #6：實作交付核可與收尾授權

- **時機**：實作階段（MYL-19）收尾，交付進入審查之前。
- **形式**：確認卡（request_confirmation），由 Developer 發出。
- **為何需要使用者**：Pilot 期間交付收尾經使用者過目；卡上並附分支收尾方式供核可。
- **證據**：MYL-19 確認卡 `confirmation:MYL-19:delivery:1451c4f`（2026-09-03T01:30 核可）。
- **結果**：核可。Developer 據此把 `feat/MYL-19-foundry-lint` 合入本地 main 並刪除分支——此舉發生在 MYL-20 正式審查之前，觸發卡點 #3（見下）。其後的審查（MYL-20）與測試（MYL-21）均為 agent 對 agent 交接，無新增使用者決策點。

> 實作→審查→測試段（MYL-19～21）共新增 1 個使用者決策點。整段 Pilot 的使用者決策點合計 6 個：選題 1、需求 3（含四項取捨合併為一卡）、設計 1、實作 1。

---

## 二、卡住的地方清單

### 卡點 #1：foundry-protocol 的 commit 同意規則與 MYL-10 暫行放寬未同步

- **卡在哪**：`skills/foundry-protocol/SKILL.md` 第 7 節規定「commit 需當次同意：每次 commit 前把訊息草案給使用者過目」；但使用者全域 CLAUDE.md 已依 MYL-10（2026-09-03 起）暫時放寬為「允許自動 commit，不必先徵求同意」。兩份規範對同一行為給出相反指示。
- **為什麼卡**：foundry-protocol 寫定後，MYL-10 的暫行放寬只更新了全域 CLAUDE.md，沒有回寫到 protocol。任何 agent 掛著 protocol 工作時都會遇到「照哪份做」的矛盾；本次依文檔權威階序由使用者即時指示（CLAUDE.md 放寬條款）優先，先行自動 commit。
- **規範怎麼改（提案，尚未執行）**：在 foundry-protocol 第 7 節 commit 規則加註 MYL-10 暫行放寬條款（含恢復條件），與全域 CLAUDE.md 的寫法對齊；恢復嚴格模式時兩處一起改回。修改權歸 protocol 維護者（CEO／使用者核可後執行）。
- **狀態**：已記錄，待納入規範修正批次（驗收標準 4）。

### 卡點 #2：MYL-4 結案時分支未合併，下游工單 Inputs 在 main 上打不開

- **卡在哪**：六份角色 skill 與六份文件模板只存在於分支 `docs/MYL-4-role-skills-templates`，MYL-4 已結案但分支從未合入 main。Scrum Master 開 Pilot 需求單時，Inputs 要引用 `templates/brd.md` 等路徑，逐項確認可存取時發現 main 上不存在。
- **為什麼卡**：foundry-protocol 第 7 節規定「工單結案前分支要收尾乾淨：該合的合」，並指定由 Code Reviewer 在 APPROVED 時檢查；但純文件工單沒有走 Code Reviewer 審查，這條檢查就沒人執行，規則出現無人負責的縫隙。
- **當下處置**：Scrum Master 於 2026-09-02 將 `docs/MYL-4-role-skills-templates` fast-forward 合入 main（552bb40→cff7dc8，非破壞性、未 push），解除 Inputs 阻塞。
- **規範怎麼改（提案，尚未執行）**：protocol 第 7 節補一條——不經 Code Reviewer 的工單（如純文件單），分支收尾由「結案前的最後執行者」自查、Scrum Master 巡檢兜底；結案檢查清單加入「分支已合併或已註明保留原因」。
- **狀態**：已記錄，待納入規範修正批次（驗收標準 4）。

### 卡點 #3：使用者確認卡核可導致「先合併、後正式審查」順序倒置

- **卡在哪**：MYL-19 的交付確認卡（決策點 #6）核可後，Developer 隨即把 `feat/MYL-19-foundry-lint` 合入本地 main、刪分支、結單；排在其後的 MYL-20 正式審查變成對「已合入 main 的 commit」做核驗，與工單原設計「審查通過後才合併」順序倒置。Code Reviewer 只能在審查報告開頭加流程備註說明。
- **為什麼卡**：protocol 第 7 節只規定「結案前分支收尾乾淨」，沒有規定**合併時點**與審查單的先後關係；使用者確認卡的「核可」語意涵蓋了收尾動作，讓 Developer 有依據先合。兩種授權（使用者核可交付 vs 審查者核可品質）在規範裡沒有被區分開。
- **規範怎麼改（提案，尚未執行）**：第 7 節「分支」補「合併時點」條款——掛有審查單的實作分支，合併回 main 一律在審查單 APPROVED 之後；使用者確認卡的核可＝同意交付進入審查，不等於合併授權。若使用者明確指示先合併，審查單改為對已合入 commit 的核驗，並在審查報告開頭註明（本次 MYL-20 的實際做法，就地追認為例外程序）。
- **狀態**：已記錄，待納入規範修正批次（驗收標準 4）。

### 卡點 #4：`unblockDescriptor.owner` 只能填自己，照規範直覺填「解除者」會整筆 PATCH 失敗

- **卡在哪**：Scrum Master 把 MYL-6 重新掛回 `blocked` 時，依 protocol 第 2 節「留言註明解除者是誰」的精神把 owner 填成 QA agent，API 回「Agents may only name themselves as an unblock owner」，且**整個 PATCH 不生效**——status 與 `blockedByIssueIds` 也一併沒寫入，需重送。
- **為什麼卡**：protocol 要求寫明「解除者」，但 Paperclip 平台限制 `unblockDescriptor.owner` 只能是 agent 自己；規範沒有提示這條平台限制與正確做法，直覺填法必踩。
- **規範怎麼改（提案，尚未執行）**：第 2 節 `blocked` 補平台限制註記——指望其他 agent 解鎖時，把對方的工單掛進 `blockedByIssueIds` 作一級 blocker，owner 欄位一律填自己，收尾動作寫在 `action`；「解除者是誰」寫在留言即可。
- **狀態**：已記錄，待納入規範修正批次（驗收標準 4）。
