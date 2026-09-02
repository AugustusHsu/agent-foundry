# Foundry

> 這個專案不是在做某一個產品,它在鑄造「做產品的那支團隊」——一套跑在 [Paperclip](https://paperclip.ing) 上、有角色分工、有交接規範、有品質閘門的 AI 開發流程。

Foundry 把「一個人帶著一堆 AI 亂做」變成「一支有編制的團隊照規矩做」。它定義了誰負責拆單、誰做設計、誰寫程式、誰審查、誰測試,定義了工單怎麼流轉、什麼時候必須停下來問人、程式碼在什麼條件下才能 commit。

這個 repo 是整套規範的**單一真相來源(single source of truth)**:團隊規範、角色 skill、文件模板都版控在這裡。改 repo 就等於改團隊。

## Repo 結構

```
agent-foundry/
├─ README.md                     # 本文件
├─ skills/                       # Agent skill 原始檔
│  ├─ foundry-protocol/          # 核心規範(每個 agent 必掛):工單骨架、
│  │                             #   狀態機、交接格式、HITL 閘門、commit 規則
│  └─ roles/<角色>/              # 角色薄 skill:只寫該角色獨有的判準與產出格式,
│                                #   共通規則一律引用 foundry-protocol
├─ templates/                    # 共用文件模板:BRD / PRD / HLD / LLD /
│                                #   test-plan / review-report
├─ docs/
│  ├─ handbook/                  # 使用手冊:要做一個新功能時,該下什麼指令、
│  │                             #   流程會怎麼跑、要在哪幾個點做決定
│  └─ features/<模組>/           # 各功能模組的需求與設計文件
└─ mkdocs.yml                    # MkDocs Material 設定(本機預覽用,尚未發佈)
```

## 三層 skill 結構

1. **`skills/foundry-protocol/`** — 核心規範,每個 agent 必掛。工單骨架(Inputs/Outputs/驗收標準/未決事項)、狀態機與流轉條件、交接格式、HITL 閘門觸發條件、缺陷收容判準、文檔權威階序、commit/分支規則。
2. **`skills/roles/<角色>/`** — 角色薄 skill(約 60–120 行)。只寫該角色獨有的內容,共通規則引用第 1 層,不重抄。
3. **`templates/`** — 共用文件骨架。模板只有一份,改了全隊同步。

## Skill 怎麼匯入 Paperclip

Skill 原始檔放在這個 repo,Paperclip 的 company skill library 從**本機 clone 路徑**匯入:

1. 修改(或新增)`skills/` 底下的 SKILL.md。
2. Commit 進 repo(依規範:訊息草案先過目、同意才 commit)。
3. 透過 Paperclip 的 company skills API 從本機路徑重新匯入,再把 skill 指派給對應 agent。

如此不會出現「Paperclip 上一份、repo 上一份」的雙份真相——repo 永遠是權威版本。

## 文件與發佈

- 手冊與設計文件先以 Markdown 形式放在 `docs/`,GitHub 會直接渲染,可線上閱讀。
- 想看網站版:本機執行 `pip install mkdocs-material && mkdocs serve`。
- 是否發佈成網站(GitHub Pages 等)待手冊定稿後再決定;private repo 開 Pages 有方案與公開性限制,屆時另行評估。

## 文檔權威階序

**設計文件 > 工單驗收標準 > 對話。** 三者衝突時停下來問人,不自行裁定。
