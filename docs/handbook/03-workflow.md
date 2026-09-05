# 3. 流程會怎麼跑？

> 最後對照 protocol `e62e42c`（2026-09-05）

標準流程鏈（foundry-protocol 第 3 節）：

```
需求 ──▶ 設計 ──▶ 拆單 ──▶ 實作 ──▶ 審查 ──▶ 測試 ──▶ 結案
 PA       TL       SM       Dev      CR       QA
```

每一棒要交出規定的交接物，**交接物不齊，下一棒有權直接退回、不開工**。交接一律發生在工單留言或工單文件上，不依賴私下對話。

下面用 Pilot 的真實案例（foundry-lint，MYL-16 → MYL-21）把每一段走一遍。每段格式固定：誰接手、產出什麼、什麼條件才往下走、Pilot 實際發生的事。

## 第 0 段：選題／提需求

- **誰**：你（使用者）＋ CEO。
- **產出**：一個確定要做的題目。
- **往下走的條件**：題目由你明確選定或提出——agent 不得自行挑題開跑。
- **Pilot 實際**：CEO 發選題卡（`ask:MYL-6:pilot-topic:v1`），使用者 2026-09-02 選定「foundry-lint 文件檢查器」。

## 第 1 段：需求（Product Analyst）

- **誰**：Product Analyst 接手，開需求單。
- **產出**：BRD（為什麼做、成功長怎樣）＋ PRD（具體要有什麼行為），用 `templates/` 骨架，存 `docs/features/<模組>/`。
- **往下走的條件**：
  1. 需求取捨經你確認（互動卡）——文件正文只放你明確確認過的需求；
  2. 未決事項清空；
  3. BRD／PRD 定稿經你核可（確認卡）；
  4. 交接 Tech Lead 前，交接物齊：BRD／PRD 路徑＋已確認的決策清單。
- **Pilot 實際**：MYL-16。起草（commit `07b8865`）→ 四項取捨經 `ask:MYL-16:lint-requirements:v1` 確認 → 定稿（`ac0c180`）→ 定稿核可卡 `confirmation:MYL-16:prd-final:ac0c180` → 交接核可卡 `confirmation:MYL-16:handoff-techlead:ac0c180`（2026-09-03 核可）→ MYL-16 結單，Tech Lead 開工。

## 第 2 段：設計（Tech Lead）

- **誰**：Tech Lead。
- **產出**：HLD（系統長什麼樣、為什麼這樣選，含 ADR）＋ LLD（Developer 照著寫就行），存 `docs/features/<模組>/`。
- **往下走的條件**：
  1. LLD 完成度達標——Developer 讀完不需再做任何設計決策；
  2. 重大選型有 ADR（選項＋取捨＋結論三段齊）；
  3. 設計定稿經你核可，Scrum Master 才能據以拆單。
- **Pilot 實際**：MYL-17。HLD／LLD 含 ADR-1～3 技術選型（commit `76f3089`）→ 核可卡 `confirmation:MYL-17:handoff-sm:76f3089`（2026-09-03 核可）→ MYL-18 拆單解除阻塞。

## 第 3 段：拆單（Scrum Master）

- **誰**：Scrum Master。
- **產出**：合格工單鏈——每張單過四段骨架判準、單一交付物、可獨立驗收、附設計文件路徑；硬依賴用 `blockedByIssueIds` 掛好。
- **往下走的條件**：工單四段齊全、Inputs 逐項可存取、依賴鏈沒有環也沒有隱藏前置；Tech Lead 核對拆單能對應回設計文件章節。
- **Pilot 實際**：MYL-18 拆出 **MYL-19（實作）→ MYL-20（審查）→ MYL-21（測試）** 三張一鏈。

## 第 4 段：實作（Developer）

- **誰**：Developer 領單。
- **產出**：一單一分支上的程式碼＋測試，加**三段式交付回報**：(1) 執行項目追蹤（AC 逐條對應做了什麼、在哪個檔案）；(2) 矛盾與風險警告；(3) 驗證與測試建議。外加分支名與 commit 訊息草案。
- **往下走的條件**：每條 AC 自驗有證據、測試全綠、分支上只有本單變更、三段式回報齊。**AC 逐條對應，不多做也不少做**——順手改善記進風險警告，不動手。
- **Pilot 實際**：MYL-19。分支 `feat/MYL-19-foundry-lint`，實作 CLI＋測試（commit `7bf8c6e`、`1451c4f`）→ 交付確認卡 `confirmation:MYL-19:delivery:1451c4f`（2026-09-03 核可）→ 交棒審查。
  - ⚠️ 此處踩過卡點 #3：確認卡核可後 Developer 先把分支合入 main 才進審查，順序倒置。現行規範已補「合併時點」條款：**掛有審查單的分支，一律審查 APPROVED 之後才合併**；你的核可＝同意交付進入審查，不等於合併授權。

## 第 5 段：審查（Code Reviewer）

- **誰**：Code Reviewer。
- **產出**：標準審查報告，結尾必有明確 Verdict：`✅ APPROVED` 或 `❌ CHANGES REQUESTED`＋重大瑕疵清單（每項含位置／問題／期望）。報告貼工單留言**並** commit 進 repo（`docs/features/<模組>/review-report.md`，卡點 #6 後的新規）。
- **往下走的條件**：四維審查（AC 證據、設計符合度、安全與資料正確性、可維護性）全過且分支已收尾 → APPROVED；否則退回 Developer，複審只對上一輪清單逐項驗。
- **Pilot 實際**：MYL-20。7 條 AC 實測全過，Verdict `✅ APPROVED`；報告後補轉錄為 `docs/features/foundry-lint/review-report.md`。

## 第 6 段：測試（QA Engineer）

- **誰**：QA Engineer。
- **產出**：測試計畫（`templates/test-plan.md` 骨架，AC 一條不漏、邊界優先）＋執行結果；有缺陷則出三段式缺陷報告（重現步驟／預期／實際）＋成因工單判定建議。
- **往下走的條件**：全數測項綠燈 → 結案；有缺陷 → 依 protocol 第 5 節收容判定表處理（能退回原單就不開新單）。
- **Pilot 實際**：MYL-21。測試計畫 15 測項全過、無缺陷（commit `c26c442`），結單。

## 第 7 段：結案

每張單轉 `done` 的鐵則：**AC 逐條有驗證證據、分支已收尾（合併或註明保留原因）。只有宣稱、沒有證據，不得結案。**

另一項 Definition of Done（MYL-12 決議，MYL-24 改為自動化）：**動到 `docs/handbook/` 的工單，結案前必須同步對外的主閱讀面。**這件事現在由 agent 自己走完，不再逐次問你——你在 push 分級表裡把「既有公開管道的內容同步」列為 P2 常設授權（[第 4 章](04-decision-points.md)），agent 就在授權範圍內代行。四個步驟：

1. 手冊變更合併進 main。
2. 執行 agent 寫**發佈審查記錄**（`docs/publish-reviews/<工單編號>.md`），逐項自檢 P2 三前提——來源已合併、範圍只動 `docs/handbook/`、連結改寫輸出無異常——外加公開適切性檢查（有沒有機敏資訊、內部路徑對外部讀者讀不讀得通、連結會不會斷）。三項全過才給 `APPROVED`。
3. 審查記錄 commit 進 repo。
4. 同步主閱讀面（本專案是 wiki，執行 `scripts/publish-wiki.sh`）。腳本有**證據閘門**：核對不到對應這版手冊的 APPROVED 記錄就拒跑，跳過審查直接發佈是做不到的。閘門綁的是手冊內容的 commit sha，所以「審查通過後又偷改手冊」也會被擋。

自檢有任一前提不成立（例如變更還沒合併進 main），agent 不會硬發，結案留言會註明「主閱讀面未同步」與原因，結案本身不被卡住。

還有**第五步，但它不是結案條件**：版本化的精裝站要不要跟著發一版，由你決定——打 `handbook-v<N>` tag 就會觸發 CI 建站。tag 發佈屬你專屬，agent 不會自己打（[第 4 章](04-decision-points.md)）。推 tag 前要先把 `handbook-version-tags` 這條 repo 規則切成 Disabled、推完切回 Active，原因與路徑見[第 4 章](04-decision-points.md)。

**要你出面的還有一種情況**：發佈範圍或投影規則本身要改（不只是同步內容），那是 P3，會發卡問你。

- **Pilot 實際**：MYL-19～21 依序結案後，Pilot 主單（MYL-6）收尾：六個卡點的規範修正回寫 repo（commit `f5dd989` 等），修正後的 skill 由使用者重新匯入 Paperclip（決策點 #7，agent 無權執行）。

## 狀態機速查

工單只有六個狀態，流轉條件都是可判定的（詳見 protocol 第 2 節）：

```
blocked ──前置done/Inputs可用/卡已回──▶ todo ──領單──▶ in_progress
   ▲                                                      │
   └────遇阻塞或觸發 HITL 閘門────────────────────────────┘
                                                          │交付完成且自檢過AC
cancelled（需求不再成立，留言註明）          in_review ◀──┘
                                              │審查過──▶ done
                                              └退回──▶ in_progress（附具體缺陷清單）
```

看板上一張單長時間不動，先看它的狀態與留言——`blocked` 的單必附阻塞原因與解除路徑，見[第 5 章](05-troubleshooting.md)。
