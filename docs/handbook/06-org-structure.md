# 6. 團隊是怎麼編制的？

> 本章記錄 MYL-12 討論、MYL-14 落地的組織結構決議。規則本體在 [`skills/foundry-protocol/SKILL.md`](../../skills/foundry-protocol/SKILL.md) 第 9 節；本章解釋它對你（使用者）的意義。

## 組織圖

```
你（使用者）
└── CEO ─────────── 你唯一的對口
    ├── Product Analyst（需求）
    ├── Scrum Master（流程）
    └── Tech Lead（技術）
        ├── Developer
        ├── Code Reviewer
        └── QA Engineer
```

- **CEO 直轄三個職能負責人**：Product Analyst 管需求、Scrum Master 管流程、Tech Lead 管技術。
- **開發三角（Developer、Code Reviewer、QA Engineer）掛在 Tech Lead 下**。

## 這對你有什麼影響

1. **你的對口不變**：一律對 CEO 說話（見[第 2 章](02-commands.md)），不需要理解內部匯報線。
2. **技術爭議不會吵到你面前**：Developer 與 Code Reviewer 對瑕疵判定有異議、實作發現設計缺漏，這類技術面爭議由 Tech Lead 裁定收斂；只有涉及需求取捨、優先序、花錢、對外的問題才會以互動卡的形式升到你這裡（清單見[第 4 章](04-decision-points.md)）。
3. **匯報線 ≠ 流程鏈**：[第 3 章](03-workflow.md)的交接順序（需求→設計→工單→實作→審查→測試）照舊，不因組織結構改變。

## 哪些決定會回到你手上

長期只有三類（MYL-12 你的裁定）：

1. **錢與權限**——任何會產生費用或變更權限的動作。
2. **對外動作**——push、發布、公開任何東西。
3. **產品方向**——需求內容、範圍取捨、優先序。

其餘決定都有明文的拍板者：技術選型歸 Tech Lead、AC 修改歸 Scrum Master、審查結論歸 Code Reviewer、技術爭議歸 Tech Lead 裁定。完整的「誰拍板、裁不了怎麼升級」矩陣在 [`foundry-protocol` 第 9 節](../../skills/foundry-protocol/SKILL.md)。如果你被問到矩陣內已授權的決定，可以直接回「這由 {角色} 依規範決定」，把決定推回去。

## 現在為什麼不加 PM？

現階段只有一條 feature 流，CEO 直接協調就夠；多一層 PM 只會多一站轉手。

**加 PM（stream owner）的觸發條件**（兩項同時成立才啟動）：

1. 同時有 ≥2 條獨立 feature 流在進行。
2. CEO 的時間主要花在跨流協調，而非單流內的裁決。

觸發時 CEO 會開單提案、發卡請你裁定，不會自行改組織。

## 結構與平台設定的對應

Paperclip 上各 agent 的 `reportsTo`（匯報對象）設定是上面組織圖的映射，MYL-14 已同步完成。兩者若再出現不一致，以 foundry-protocol 第 9 節為準發起同步。
