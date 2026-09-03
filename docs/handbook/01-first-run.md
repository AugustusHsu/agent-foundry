# 1. 第一次使用走查

照著本節做一遍，你會從零開到第一張合格工單。每一步都對應 Pilot 實際發生過的事件，右側括號附證據。

## 事前檢查（只做一次）

1. **確認 skill 已匯入 Paperclip**：公司 skill library 裡要有 `foundry-protocol` 與六個角色 skill（`role-product-analyst`、`role-tech-lead`、`role-scrum-master`、`role-developer`、`role-code-reviewer`、`role-qa-engineer`），且已指派給對應 agent。
   - 注意：**skill 的匯入／更新只有你（使用者）能做**。Agent 呼叫 skill 寫入 API 一律被平台擋下（403 `skill_actor_restricted`），這不是故障（Pilot 卡點 #5）。
   - Skill 原始檔的權威版本在本 repo `skills/` 底下；匯入流程見 [README「Skill 怎麼匯入 Paperclip」](https://github.com/AugustusHsu/agent-foundry#readme)。
2. **確認素材在 main 上**：agent 開工單時會逐項確認 Inputs 打得開；只存在於未合併分支的檔案，等於不存在（Pilot 卡點 #2 就是模板沒合入 main，開單當場卡住）。

## 開出第一張單的四步

### 第 1 步：對 CEO 說一句話需求

在 Paperclip 上對 CEO agent 說出你想做的東西。不用寫工單格式，一句話加上下文即可。句型與範例見[第 2 章](02-commands.md)，最短可用版：

> 幫我做「〔功能名稱〕」：〔一句話說明它做什麼〕。它解決的問題是〔誰的什麼痛〕，做到〔什麼程度〕算成功。

Pilot 的實際起點略有不同——當時是 CEO 發互動卡列了三個候選題目，使用者選了「B. foundry-lint 文件檢查器」（互動卡 `ask:MYL-6:pilot-topic:v1`，2026-09-02 answered）。日常使用時方向相反：**你主動丟題目，不必等 agent 提案**。

### 第 2 步：回答需求訪談卡

Product Analyst 接手後**不會直接開寫文件**，會先發一張互動卡（ask_user_questions），一次問 3–5 題，問到能回答三件事：解決誰的什麼問題、現在怎麼做痛在哪、做到什麼程度算成功。

Pilot 實例：foundry-lint 的需求卡一次問了四項取捨——檢查範圍、嚴格度、文件類型指定方式、輸出格式（互動卡 `ask:MYL-16:lint-requirements:v1`，2026-09-03 answered）。

**這張卡不回，流程就停在這裡。** 回卡時對具體選項作答；覺得選項都不對，用自由輸入欄寫你要的。

### 第 3 步：核可 BRD／PRD 定稿

Product Analyst 依你的回答定稿 BRD／PRD，發確認卡（request_confirmation）請你核可。核可後文件以當下 commit 為定稿版本，後續所有階段都以它為依據。

Pilot 實例：確認卡 `confirmation:MYL-16:prd-final:ac0c180`，核可後 BRD／PRD 以 commit `ac0c180` 定稿。

### 第 4 步：在看板上看到工單鏈

需求定稿、設計（HLD／LLD）核可之後，Scrum Master 會把設計拆成工單鏈。你會在看板上看到類似 Pilot 的結構：

```
MYL-19 實作 ──blocks──▶ MYL-20 審查 ──blocks──▶ MYL-21 測試
```

每張單的 description 都是固定四段：**Inputs／Outputs／驗收標準／未決事項**。看到這個骨架、依賴用 `blockedByIssueIds` 掛好，就代表第一張合格工單開出來了。

## 開單之後你要做的事

之後的實作、審查、測試都是 agent 對 agent 交接，你只在[第 4 章](04-decision-points.md)列的決策點被問。日常只需要：

- **收件匣有卡就回**——這是流程唯一會停下來等你的地方。
- 想看進度：看工單留言。所有交接回報、審查報告、阻塞原因都在留言裡，不在私下對話。
