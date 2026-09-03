# Foundry

> 這個專案不是在做某一個產品,它在鑄造「做產品的那支團隊」——一套跑在 [Paperclip](https://paperclip.ing) 上、有角色分工、有交接規範、有品質閘門的 AI 開發流程。

Foundry 把「一個人帶著一堆 AI 亂做」變成「一支有編制的團隊照規矩做」。它定義了誰負責拆單、誰做設計、誰寫程式、誰審查、誰測試,定義了工單怎麼流轉、什麼時候必須停下來問人、程式碼在什麼條件下才能 commit。

這個 repo 是整套規範的**單一真相來源(single source of truth)**:團隊規範、角色 skill、文件模板都版控在這裡。改 repo 就等於改團隊。

## Repo 結構

```
agent-foundry/
├─ README.md                     # 本文件
├─ CLAUDE.md / AGENTS.md         # 接手入口(雙入口,正文相同、只差工具名對應段)
├─ .foundry/config.yml           # 本專案的平台、關卡、push 授權設定
├─ skills/                       # Agent skill 原始檔
│  ├─ foundry-protocol/          # 核心規範(每個 agent 必掛):工單骨架、
│  │                             #   狀態機、交接格式、HITL 閘門、commit 規則
│  ├─ foundry-platform/          # 平台抽象層:8 個抽象動詞＋各平台 adapter
│  ├─ foundry-init/ adopt/ gates/ # 三個常設 workflow
│  └─ roles/<角色>/              # 角色薄 skill:只寫該角色獨有的判準與產出格式,
│                                #   共通規則一律引用 foundry-protocol
├─ templates/                    # 共用文件模板:BRD / PRD / HLD / LLD /
│                                #   test-plan / review-report / publish-review /
│                                #   entry-file(雙入口檔)
├─ docs/
│  ├─ handbook/                  # 使用手冊:要做一個新功能時,該下什麼指令、
│  │                             #   流程會怎麼跑、要在哪幾個點做決定
│  ├─ standards/                 # 契約與已知漂移(known-drift.md:反悔錄與已知缺口)
│  ├─ features/<模組>/           # 各功能模組的需求與設計文件
│  └─ publish-reviews/           # 手冊發佈審查記錄(發佈閘門的證據,綁 commit sha)
├─ tools/foundry-lint/           # 文件檢查器＋repo 規範自檢
├─ scripts/publish-handbook.sh   # 手冊 → 公開鏡像
├─ .pre-commit-config.yaml       # 機械層閘門
├─ Makefile                      # 單一指令入口(make help)
└─ mkdocs.yml                    # MkDocs Material 設定
```

## 開始之前

新接手這個 repo 的人或 agent，**先讀 `CLAUDE.md`（或 `AGENTS.md`，正文相同）**——
它會告訴你先讀什麼、大檔怎麼讀、哪裡有坑。不要從這份 README 開始摸索結構。

常用指令：

```bash
make help    # 列出所有指令
make check   # 跑完所有機械層閘門(規範自檢＋單元測試)
make hooks   # 安裝 pre-commit hook,一台機器裝一次
```

## 三層 skill 結構

1. **`skills/foundry-protocol/`** — 核心規範,每個 agent 必掛。工單骨架(Inputs/Outputs/驗收標準/未決事項)、狀態機與流轉條件、交接格式、HITL 閘門觸發條件、缺陷收容判準、文檔權威階序、commit/分支規則。
2. **`skills/roles/<角色>/`** — 角色薄 skill(約 60–120 行)。只寫該角色獨有的內容,共通規則引用第 1 層,不重抄。
3. **`templates/`** — 共用文件骨架。模板只有一份,改了全隊同步。

## Skill 怎麼進到 Paperclip

Skill 以 **`sourceType: local_path` 參照式安裝**:Paperclip 記的是這個 repo 的路徑,
每次喚醒 agent 時直接讀 repo 當下的檔案。所以:

1. 修改(或新增)`skills/` 底下的 SKILL.md。
2. Commit 進 repo。
3. **完成了——不需要重新匯入。**

如此不會出現「Paperclip 上一份、repo 上一份」的雙份真相——repo 永遠是權威版本。

> ⚠️ 要確認 skill 是否真的生效,比對 acp-engine `agents/*/runtime-skills/**/SKILL.md`
> 最新 materialized 副本與 repo 的 md5。**不要看**平台 skill 記錄的 `updatedAt` 或
> versions API——那只反映 Studio 編輯或重匯入,會誤判成「未生效」。
> (踩坑細節見 `docs/standards/known-drift.md` 的 R3。)

## 文件與發佈

- 手冊與設計文件以 Markdown 放在 `docs/`,GitHub 會直接渲染,可線上閱讀。
- 想看網站版:本機執行 `pip install mkdocs-material && make serve`。
- **手冊已發佈為公開站**:<https://augustushsu.github.io/foundry-handbook/>。
  同步流程見 protocol 第 7 節「手冊發佈審查」四步——動到 `docs/handbook/` 的工單,
  結案前必須走完,由 `scripts/publish-handbook.sh` 的證據閘門把關。
  只有 `docs/handbook/` 會上公開站,其餘目錄(含 `docs/standards/`)留在私有 repo。

## 文檔權威階序

**設計文件 > 工單驗收標準 > 對話。** 三者衝突時停下來問人,不自行裁定。
