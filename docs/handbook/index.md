# Foundry 使用手冊

這本手冊回答一件事：**你要做一個新功能時，怎麼跟這支 AI 團隊合作。**

全部內容來自 MYL-6 Pilot 試跑（foundry-lint 文件檢查器）的真實流程——每個範例、每個決策點、每個故障案例都有對應的工單、互動卡或 commit 可查，不是設想出來的。原始記錄在 [`docs/pilot/pilot-log.md`](../pilot/pilot-log.md)。

## 手冊結構

| 章節 | 回答的問題 |
| --- | --- |
| [1. 第一次使用走查](01-first-run.md) | 從零開始，照著做就能開出第一張單。 |
| [2. 我該下什麼指令？](02-commands.md) | 第一句話怎麼講、丟給誰、附什麼。含可直接複製的範例。 |
| [3. 流程會怎麼跑？](03-workflow.md) | 從需求到結案每一段誰接手、產出什麼、什麼條件才往下走。用 Pilot 真實案例走一遍。 |
| [4. 我要在哪幾個點做決定？](04-decision-points.md) | 逐一列出 HITL 閘門：什麼時候被問、問題長什麼樣、不同選擇的後果。 |
| [5. 故障排除](05-troubleshooting.md) | 流程卡住時怎麼看、怎麼推。全部案例來自 Pilot 實際踩過的六個卡點。 |
| [6. 團隊是怎麼編制的？](06-org-structure.md) | 誰向誰匯報、爭議怎麼升級、什麼條件下才會加 PM 層。 |
| [7. 團隊有哪些固定 workflow？](07-workflows.md) | 六條固定跑法總覽：每條的觸發條件與權威章節。含模型分層與升級規則。 |

## 30 秒版摘要

1. **你只需要對 CEO 說一句話需求**——不用寫工單、不用指定誰做。範例與要附的三件資訊見[第 2 章](02-commands.md)。
2. **流程自己會跑**：需求（Product Analyst）→ 設計（Tech Lead）→ 拆單（Scrum Master）→ 實作（Developer）→ 審查（Code Reviewer）→ 測試（QA）。每一棒的交接物與放行條件見[第 3 章](03-workflow.md)。
3. **你會在固定幾個點被問**：選題、需求取捨、需求定稿、設計定稿、交付核可、平台專屬動作。問題以 Paperclip 互動卡的形式出現在收件匣；**卡沒回，流程就停在那裡等你**。全清單見[第 4 章](04-decision-points.md)。
4. **卡住了先看工單留言**——所有交接與阻塞原因都寫在留言，不在私下對話裡。推進方式見[第 5 章](05-troubleshooting.md)。

## 規範文件在哪

手冊是「怎麼用」；「規則本體」在 skill 與模板：

- [`skills/foundry-protocol/SKILL.md`](../../skills/foundry-protocol/SKILL.md) — 核心規範：工單骨架、狀態機、交接格式、HITL 閘門、commit／分支規則。
- `skills/roles/<角色>/SKILL.md` — 六個角色各自的判準。
- [`templates/`](../../templates/) — BRD／PRD／HLD／LLD／測試計畫／審查報告的共用骨架。

手冊與規範衝突時，以規範（skill）為準，並回報修正手冊。
