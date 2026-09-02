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
