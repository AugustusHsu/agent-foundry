---
name: foundry-adopt
description: 既有開發中專案漸進導入 Foundry 的 workflow（MYL-9 HLD §6.2）。凡是要對已有開發活動的專案（有既存工單、分支慣例、CI，或已部分導入 Foundry）盤點現況、勾選啟用模組（Issues → ＋Projects views → ＋關卡制 → ＋角色分工）、把既有工單納入 Foundry 管理、或把 local-md 專案遷移到 github——照本文執行。可重複執行以增開模組。乾淨的新專案（無任何既有開發活動）不走本文，走 foundry-init（§6.1）。
---

# foundry-adopt：既有專案漸進導入

依已核可的 MYL-9 HLD §6.2 制定（repo 歸檔本：`docs/features/cross-platform/HLD.md`）。與 `foundry-init` 是兩件套：init 一次建全套、adopt 分模組漸進。兩者共用 `foundry-platform`（adapter 介面與對照文檔）與 `foundry-gates`（關卡設定 workflow），本文不重複定義那兩份文檔已有的內容。本文是跨平台純 .md workflow：任何 agent runtime 或人類照本文逐步執行即可；Claude Code 可安裝為 slash command（`/foundry-adopt`）作可選增強。

## 0. 邊界與詞彙

- **適用對象**：已有開發活動的專案——有既存工單／分支歷史／CI，或已部分導入 Foundry（例如只啟用了 Issues 模組）。與 foundry-init 的分流以 init §0 的判準為準：init 發現既有活動改走本文；本文發現目標是全新空專案時，建議直接走 init（一次建全套較省），但照本文逐模組跑也合法。
- **`<SRC>`**／**`<TARGET>`**：同 init §0——`<SRC>` 是本 skill 所在的 agent-foundry checkout 根目錄，所有複製來源；`<TARGET>` 是要導入的專案根目錄。動工前記下 `<SRC>` 的 commit sha 供報告引用。
- **互動方式**：平台有互動卡機制（如 Paperclip）→ 發卡；無 → 輸出 .md 報告請使用者批示。等到明確回覆為止，不得代答。
- **四個模組**（漸進階梯，依賴單向）：

  | 模組 | 內容 | 依賴 |
  | --- | --- | --- |
  | M1 Issues | `.foundry/config.yml`＋流程檔複製＋工單基礎（labels／milestones 或 board 目錄）＋既有工單選擇性納管 | — |
  | M2 Projects views | 看板：project＋board／table／roadmap 三 view | M1 |
  | M3 關卡制 | `gates` 段由使用者經 foundry-gates 選定生效 | M1 |
  | M4 角色分工 | `role:*` label 慣例＋「角色 ↔ 執行者」對照表，落檔為 `.foundry/org.yml` | M1 |

- **漸進原則**：每個模組獨立啟用、獨立回退、獨立 commit；使用者可一次只勾一個模組、之後任何時候再跑本文增開（§5）。啟用步驟全部冪等——已啟用的模組重跑不報錯、不覆蓋既有資料。
- 本 workflow 產生的檔案一律進 `<TARGET>` 版控；push 依該專案現行授權規則，本 workflow 不放寬。**絕不覆蓋 `<TARGET>` 既有檔案、絕不改寫既有工單的內文與歷史**——這是 adopt 與 init 最大的差異，下文每個會碰到既有資料的步驟都各自重申。

## 1. 步驟 1：盤點（必跑、唯讀）

每次執行本文都從盤點開始，產出**現況報告**。本步不寫入任何平台側資源、不改任何 `<TARGET>` 檔案。

1. **Foundry 現況**：`.foundry/config.yml` 存在嗎？存在則依 `config-schema.md` 驗證（非法即停止並回報，同 gates §1）。逐模組判定已啟用與否：
   - M1：config 合法，且平台側工單基礎存在（github＝標準 label 集查得到；local-md＝`.foundry/board/issues/` 存在）。
   - M2：github＝ProjectV2 與三 view 查得到；local-md＝`views/` 三檔存在。
   - M3：`gates` 段有使用者選定紀錄（確認卡識別碼或批示位置，通常在工單留言）；只有 schema 預設佔位、查無選定紀錄 → 視為未啟用。
   - M4：`.foundry/org.yml` 存在（**舊版寫的是 `.foundry/roles.md`**——MYL-76 起組織宣告改用
     schema 化的 `org.yml`。盤到只有 `roles.md` 的專案＝**舊格式，視為 M4 已啟用但需遷移**，
     在報告列為待辦，不要當成未啟用而重跑一次 M4）。
2. **軸 A 現況與現有分工（MYL-78 增訂，唯讀）**：
   - **`ai_platform` 宣告了嗎**：`.foundry/config.yml` 有沒有這一欄、值是什麼。**沒有就記「未宣告」**，
     不要用「現在是誰在跑」去回填——agent 觀察到的是自己這一輪的殼，不一定是該專案長期要用的殼。
   - **實際在哪個殼裡跑**：repo 根有 `CLAUDE.md`？`AGENTS.md`？兩者都有還是只有一個？
     有沒有其他 harness 的設定檔（如 `.codex/`）？**這是觀測值，與上一項的宣告值分開記**，
     兩者不一致本身就是要報告的發現。
   - **現有分工**：目前有哪些人／agent 在這個專案上工作、各自負責什麼。有 `org.yml` 或
     `roles.md` 就照它記；沒有就從近期 commit 作者與工單 assignee 觀察，**記為「觀察值」並註明樣本範圍**。
   - **能力落差**：依上面的觀測，查 `skills/foundry-ai-platform/SKILL.md` §3 對照表，
     逐項列出 ⚠️／❌ 的能力與對應降級規則（`AP-1`～`AP-6`）。
3. **既有開發慣例**（各項找不到就記「無」，不猜）：
   - issue tracker：GitHub Issues？`.foundry/board/`？其他系統（Jira、Paperclip 等——記錄名稱與工單量級即可）？既有工單數、有無 label／milestone 慣例。
   - 分支慣例：近期分支命名模式、合併方式（merge／rebase／squash）、commit 訊息風格。
   - CI：`.github/workflows/` 或其他 CI 設定檔清單。
   - 檔案衝突預查：`<TARGET>` 是否已有 `skills/foundry-*`、`templates/`、`.foundry/` 且內容與 `<SRC>` 不同——有就逐檔列出，這些檔在 M1 一律不覆蓋（§3.1）。
4. **模組建議**：對照上述現況，逐模組寫「已啟用／可啟用／暫不建議＋理由」。平台側慣例與 Foundry 標準衝突時（例如既有 label 命名撞名）列為風險，附處理選項。
5. **報告去向**：有工單系統 → 貼對應工單留言；無 → 存 `<TARGET>/.foundry/adopt-report-<YYYY-MM-DD>.md`（目錄不存在先建，這是本步唯一允許的寫入）。報告開頭記：執行日期、執行者、`<SRC>` commit sha、`<TARGET>` 路徑與 HEAD sha。
6. **平台不在 adapter 枚舉時**（現行為 `github`｜`gitlab`｜`local-md`｜`paperclip`；如 Jira、Linear）：盤點照跑、報告照出，但模組啟用不可用——報告註明「需先依 foundry-platform §5 新增該平台 adapter（protocol 第 9 節規範修訂流程）」，本次到此為止，不發模組選擇卡。

## 2. 步驟 2：模組選擇（發卡）

1. 發卡給使用者，卡上只列**未啟用**的模組（已啟用的在卡文註明現況即可），逐模組可勾選、允許全不勾（只留盤點報告，本次結束）。依賴自動連帶：勾了 M2／M3／M4 而 M1 未啟用，卡上明列「將一併啟用 M1」。
2. M1 未啟用時，同卡問齊 init 步驟 1 的三件授權（同樣依 protocol 第 4 節不得代選）：
   - **平台**：`github`｜`local-md`｜`paperclip`（盤點若已見 `.foundry/board/`、明確的 GitHub 使用慣例、或專案已跑在 Paperclip 上，可預填建議值，仍由使用者拍板）。
   - **branch push 權限**（`push.branch_push`）：`user` 或 `tech-lead`；未選視同 `user`。
   - **平台側資源建立同意**（github 模式）：明列將建立的資源——標準 label 集、納管標記 label `foundry:managed`、milestone 容器；勾了 M2 再加 ProjectV2＋三 view。此同意即 protocol 決策點 7 的授權證據，未同意不得動平台側。
3. 勾了 M1 且既有工單系統與選定平台相同（例如既有 GitHub Issues），同卡問**既有工單納管範圍**：全部／依 milestone 或 label 圈選／逐單清單／暫不納管（見 §3.1 第 4 點）。
4. **軸 A 與分工的對齊（MYL-78 增訂）**——把 §1 第 2 點盤到的現況攤在卡上，問使用者要不要對齊。
   **三題各自獨立可選，允許全不選**（既有專案本來就在跑，不對齊也不會壞）：
   - **要不要補宣告 `ai_platform`**：卡上寫出盤到的觀測值（`CLAUDE.md`／`AGENTS.md`／`.codex/` 各有沒有）
     當參考，**由使用者拍板寫哪個值**，agent 不得代填。選「暫不宣告」是合法答案。
   - **宣告值與觀測值不一致時要往哪邊修**：改設定遷就現況，還是改現況遷就設定。**這題不給預設**——
     兩個方向的後果不同（前者是承認現況、後者是要求搬遷），只有使用者知道哪個是本意。
   - **要不要把現有分工寫成 `.foundry/org.yml`**（即勾 M4）：卡上附 §1 第 2 點盤到的分工觀察值，
     **但要標明它是「現況」不是「將寫入的內容」**——寫入的角色集合由 protocol 第 9 節決定（M4 第 3 點），
     卡上把兩者的落差列出來，那才是使用者在這一題實際要決定的事。
     ⚠️ 同時要寫明：**這份檔是宣告，不會把 agent 建出來**（`foundry-ai-platform` §6）。
   - 卡上一併附 §1 第 2 點的**能力落差清單**（⚠️／❌ 的能力與 `AP-n` 降級規則）。
     這不是問題、是知情資訊——讓使用者在決定要不要對齊時看得到代價。
5. 鐵律（與 gates §3 同條）：**卡未回覆前不得啟用任何模組**。等待期間對應工單轉 `in_review`（或無平台時明確標記等待中）。

## 3. 步驟 3：逐模組啟用

只啟用使用者勾選的模組，依 M1→M4 順序。每個模組：執行 → 查證 → 獨立 commit（gitmoji 風格、繁中標題，訊息註明模組名）→ 報告記一筆。任一模組查證不過：該模組依回退說明還原，已完成的前序模組**保留**，報告記明失敗原因。

### 3.1 M1 Issues

1. **config**：`.foundry/config.yml` 不存在 → 依 init §2 第 2 點產生（example 為底、schema 為準；`gates` 寫 schema 預設或帶既有已記錄選定；`push.branch_push` 依卡上選定、`main_push: user` 寫死；檔首註解記 `# generated by foundry-adopt from <SRC repo> @ <commit sha> on <YYYY-MM-DD>`）。已存在 → 逐字保留，只在缺必填欄位時停止並回報（非法檔不硬跑，同 §1）。
2. **複製流程檔**：清單與相對路徑規則**以 init §2 第 3 點為準**（該處逐項列出要複製與不複製的路徑）。此處不重列清單——重列的那份會漏掉往後新增的項目，而讀到本文的人不會知道自己看的是舊的。逐檔規則改為漸進版：不存在 → 複製；相同 → 跳過；**不同 → 不覆蓋**，列入報告的衝突清單請使用者裁定（保留己方／改用 Foundry 版／人工合併），裁定前該檔維持原樣、不阻塞其他檔與其他模組。
3. **平台側工單基礎**：照 adapter `init_structure` 執行 label／milestone 相關步驟（github 另建納管標記 label `foundry:managed`，adopt 專用、不屬標準集；local-md＝建 `board/issues/`＋`milestones.md`），project＋view 步驟留給 M2——adapter 步驟冪等，M2 重跑整個 `init_structure` 補齊即可。**不刪、不改任何既有 label／milestone**；撞名（既有同名 label 用途不同）列入衝突清單，不強改。
4. **既有工單選擇性納管**（僅使用者在卡上圈了範圍才做）：對圈選的每張既有工單**只掛 label**——`foundry:managed`＋依標題內容歸類的 `type:*`（歸類對照表列入報告，使用者可事後改掛）。**不改寫 body、不補四段骨架、不動留言與歷史**；未圈選的工單完全不碰。納管後的新工單一律走 protocol 第 1 節骨架。
- **查證**：config 依 schema 驗證合法；複製清單逐檔存在（衝突檔除外，報告有記）；github＝`type:*` label 計 8＋`foundry:managed` 存在、圈選工單逐單掛上標記；local-md＝`board/issues/` 與 `milestones.md` 存在。
- **回退**：git revert M1 的 commit（config＋複製檔＋board 目錄隨之還原）；github 側刪除本次新建的 label（`gh label delete`——會同時從工單上移除該 label，但不動工單本身；僅刪本次新建的，撞名保留的既有 label 不碰）。

### 3.2 M2 Projects views

1. 前置：M1 已啟用；github 模式核對卡上平台側資源同意含 project。
2. 重跑 adapter `init_structure` 全部步驟（冪等：M1 已建的跳過，補建 project＋三 view）。github 模式的人工步驟（Status 三選項、三 view 網頁建立）列入報告待辦，同 init §3 第 4 點，不算失敗但不得靜默略過。
3. 選擇性把已納管（`foundry:managed`）工單加進 project（github：`gh project item-add`，照 adapter 附錄查 project 編號）。
- **查證**：照 adapter `init_structure` 查證條目（github＝project 查得到；local-md＝三 view 檔存在）；重跑一次冪等。
- **回退**：local-md＝git revert；github＝project 移除工單項目可自動做，**刪除 project 本身屬破壞性平台動作，列為使用者操作**（回退說明附 `gh project delete` 指令，由使用者執行或明確同意後代跑）。

### 3.3 M3 關卡制

1. 前置：M1 已啟用（config 存在）。
2. 跑 `foundry-gates` **獨立執行模式，四步全走**——既有專案有工單歷史可盤，與 init 呼叫模式（跳過盤點）不同。建議、確認、寫入全依 gates 文檔，本文不重複其規則；`external_actions` 只允許 `user` 的硬性約束同樣適用。
3. 使用者在 §2 卡上已一併選定 gates 值時，視同 gates §3 的明確選定，寫入時引該卡識別碼，不重複發卡。
- **查證**：gates §4 寫入後驗證＋變更紀錄留言。
- **回退**：再跑一次 foundry-gates 把值改回 schema 預設——回退也是 gates 變更，**同樣走確認步**，不得「回退就免問」。

### 3.4 M4 角色分工

1. 前置：M1 已啟用。
2. 與使用者確認「角色 ↔ 執行者」對照（哪些角色由誰／哪個 agent 擔任、哪些角色暫缺）——可在 §2 卡一併問，或此時補發卡。
3. 寫 `<TARGET>/.foundry/org.yml`：依 `config-schema.md` 的 `.foundry/org.yml` 一節填
   （`foundry_org`／`ai_platform` ＋各角色 `id`／`title`／`reports_to`／`skills[]`／`permissions[]`／`model_tier`），
   對照表的生效日期與出處（卡識別碼）寫在檔首註解。`role:*` label（標準集已含）自此依對照表掛用。
   - ⚠️ **角色集合不是照盤點結果填的**（MYL-78 修正，本行原本要求複製時排除 `skills/roles/`）：
     `org-sync` 把本檔的角色集合與 protocol 第 9 節組織圖做**雙向**相等比對，多一個少一個都報錯。
     §1 盤到的「現有分工」是**實然**，用途是讓使用者知道現況與規範差多少；**本檔填的是應然**，
     照第 9 節那張圖抄。兩者不一致時列進報告當落差，**不是拿盤點值覆蓋規範**（`O1`）。
   - **`skills[]` 逐條驗存在**，所以 M1 複製時要一併帶 `<SRC>/skills/roles/`（init §2 第 3 點
     已改為「勾 M4／答要建團隊時複製」）。**勾了 M4 卻沒帶這個目錄，自檢就是九條「掛的 skill 不存在」**（實測）。
   - 目標專案想要不同編制：先改它自己那份 protocol 第 9 節，再讓本檔跟著填——順序不能反，
     且改規範是使用者裁定的事（第 4 節）。
   - **`ai_platform` 要與 `config.yml` 同值**（`org-sync` 會比對）。`config.yml` 未宣告該欄時，
     先在 §2 卡上把它一起問掉——**不要為了讓檔案長出來而自己填一個值**。
   - ⚠️ **舊格式遷移**：盤點盤到 `.foundry/roles.md`（MYL-76 前的格式）時，本步是「轉寫」不是「新建」——
     照原對照表內容填進 `org.yml`，內容有疑義就回卡問，**不得自行補齊原檔沒有的欄位**；
     轉寫完成後 `roles.md` 的處置（刪除或保留為歷史）交使用者裁定。
   - ⚠️ **這份檔不會把 agent 建出來**：沒有動詞依它去平台上建人（`foundry-ai-platform` §6）。
     還要人工建哪幾個 agent，列進報告待辦。
- **查證**：`org.yml` 存在、對照表與卡上選定一致，且 `--selfcheck` 的 `org-sync` 通過。
- **回退**：git revert（刪 `org.yml`），role label 慣例即停用；已掛在工單上的 `role:*` label 不強制清除，報告註明即可。

## 4. local-md → github 遷移（HLD §2.4）

既有 local-md 專案要升級平台時走本節。這不是模組，是平台搬遷——涉及新建平台側資源，整段屬關卡 C 授權範圍。

1. **前置**：`<TARGET>` 已是 local-md 模式（config `devtools_platform: local-md`＋`board/` 有資料）；github 前置檢查同 init §1.2 第 2 點（gh auth、scopes、repo 可解析）。
2. **發卡**：明列——將建立的 github 資源（同 §2 第 2 點清單＋ProjectV2 視 M2 是否已啟用）、搬遷範圍（全部工單／篩選；含幾單幾留言）、搬遷後 board 目錄的處置（預設：保留為唯讀歷史）。未同意不動工。
3. **建骨架**：跑 github adapter `init_structure`（含 M2 已啟用時的 project＋view；人工步驟列待辦）。
4. **逐單搬遷**（順序固定：先建全部單、再補關聯，確保 `link_issues` 的 target 都存在）：
   - `create_issue`：title 原樣；body＝原 body 前加一行 `> migrated from <FND-x> by foundry-adopt on <YYYY-MM-DD>`（這是新平台上的新載體，原 local 檔一字不動）。
   - `set_labels`／`set_milestone`／`update_status`：照原 frontmatter 對應（milestone 先在 `init_structure` 後補建齊）。
   - 留言：逐則以 `comment` 追加，內文保留原日期與作者（如 `（原留言：2026-09-03 tech-lead）`開頭）。
   - 關聯：全部單建完後，依原 frontmatter 的 `parent`／`blocked_by` 逐一 `link_issues`。
5. **對照表與冪等**：`FND-x → #n` 對照表寫入 `<TARGET>/.foundry/board/MIGRATED.md`（含遷移日期）並收進報告。重跑本節時先讀該檔，已搬過的單跳過——搬遷可分批、可中斷續跑。
6. **切換**：config `devtools_platform` 改 `github`＋補 `platform_options.github`；`board/` 依卡上選定處置（預設原樣保留、自此唯讀，MIGRATED.md 即封存標記）。此後所有動詞走 github adapter。
- **查證**：對照表單數＝圈選範圍單數；抽查 3 單（title／labels／milestone／status／留言數）與原檔一致；關聯抽查可查得；重跑一次無新增動作。
- **回退**：config 改回 `local-md` 即恢復原執行層（board 從未被改寫，資料零損失）；已建的 github 資源處置（保留／刪除）屬平台側破壞性動作，交使用者裁定。

## 5. 重複執行

- 任何時候重跑本文：步驟 1 盤點重新判定已啟用模組 → 步驟 2 卡上只列未啟用的 → 步驟 3 只做新勾選的。已啟用模組不重收費、不重發卡、不重寫檔。
- 使用者可用重跑做健檢：全部模組已啟用時，本文退化為「盤點＋報告」，仍有價值（漂移偵測：config 被手改、label 被刪等，列入報告）。

## 6. 驗收自查

結束前逐項核對，缺一項就不算跑完：

- [ ] 盤點報告已產出（工單留言或 `.foundry/adopt-report-*.md`），含逐模組已啟用判定與 `<SRC>` commit sha。
- [ ] 盤點報告含**軸 A 現況與現有分工**（§1 第 2 點）：`ai_platform` 宣告值、實際觀測值、
      兩者是否一致、現有分工、能力落差清單。**「未宣告」「觀察值」都要明寫**，不得因為查不到就整節省略。
- [ ] 對齊三題（§2 第 4 點）已在卡上問過；使用者全不選也算數，但報告要記「已問、使用者選擇不對齊」。
- [ ] 有啟用模組時：模組選擇卡有使用者明確勾選證據；依賴連帶有在卡上寫明。
- [ ] 啟用 M4 時：產出的是 `.foundry/org.yml`（非舊格式 `roles.md`），`org-sync` 通過，
      且報告已列出待人工建立的 agent。盤到舊格式時，轉寫來源與 `roles.md` 的處置裁定已記錄。
- [ ] 每個啟用的模組查證通過、獨立 commit；失敗模組已回退並記錄。
- [ ] 未覆蓋任何 `<TARGET>` 既有檔案；未改寫任何既有工單 body／留言；衝突清單（如有）已列入報告。
- [ ] `gates.external_actions` 與 `push.main_push`（如有寫檔）皆為 `user`。
- [ ] 走了 §4 遷移時：對照表存在、查證通過、原 board 未被改寫。
