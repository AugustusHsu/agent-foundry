# agent-foundry — 接手入口（Codex／其他 harness）

<!-- FOUNDRY:SHARED-BODY:BEGIN -->
> **本檔的角色**：讓一個沒有前文的 session 在 60 秒內知道「這是什麼、規則在哪、先讀什麼、哪裡有坑」。
>
> **本檔的自我約束（重要）**：
> 只放三種東西——**摘要**、**正版文件的指向**、**文件裡查不到的實況**。
> 詳細規範一律以指向的文件為準。**不要把規範內容抄進本檔**——抄過來的那份會過期，
> 於是 repo 裡就有了兩份互相矛盾的規則，而讀到本檔的人不會知道自己讀的是舊的。
> 本檔要是變成第三份規範拷貝，它就從資產變成負債。

## 1. 這個 repo 是什麼

不是在做某個產品，而是在鑄造「做產品的那支團隊」：一套有角色分工、有交接規範、有品質閘門的 AI 開發流程。
**規則層 .md 就是產品本身**——改 repo 等於改團隊行為。

執行層（工單／狀態／看板）跑在 Paperclip 上；規則層（skills／docs／templates／tools）在本 repo。
兩者分工見 protocol「平台中立原則」與第 6 節三層文檔體系。

## 2. 開場必讀順序

1. **`skills/foundry-protocol/SKILL.md`** — 全隊硬規則，每個 agent 必掛。
   ⚠️ 41KB，**不要整份讀**（見 §4）。先 `grep -n '^#\{1,3\} '` 取標題地圖，再讀需要的節。
2. **`docs/standards/known-drift.md`** — 已知漂移與反悔錄。**動手前讀這份**：
   哪些 API 會 403、哪些提案已經被否決過、哪些缺口是使用者知情下保留的。
   不讀這份，很容易花一整輪去重踩一個已經有結論的坑。
3. **自己的角色 skill**（`skills/roles/<角色>/SKILL.md`，約 60–120 行）——只寫該角色獨有的判準。
4. `.foundry/config.yml` — 本專案的關卡與 push 授權設定（**agent 不得自行改動**）。

## 3. 地圖

```
agent-foundry/
├─ CLAUDE.md / AGENTS.md    # 本檔（雙入口，正文相同、只差工具名對應段）
├─ .foundry/config.yml      # 本專案的平台、關卡、push 授權設定
├─ skills/
│  ├─ foundry-protocol/     # 第 1 層：全隊硬規則（必掛）
│  ├─ foundry-platform/     # 平台抽象層：8 個抽象動詞＋各平台 adapter
│  ├─ foundry-init/         # workflow：新專案首次導入
│  ├─ foundry-adopt/        # workflow：既有專案漸進導入
│  ├─ foundry-gates/        # workflow：調整關卡粒度
│  └─ roles/<角色>/         # 第 2 層：角色薄 skill（6 個角色）
├─ templates/               # BRD / PRD / HLD / LLD / test-plan /
│                           #   review-report / publish-review
├─ docs/
│  ├─ handbook/             # 使用手冊（8 章）＝說明層，會發佈到公開站
│  ├─ standards/            # 契約與已知漂移（不發佈）
│  ├─ features/<模組>/      # 各模組的 BRD/PRD/HLD/LLD 與審查報告
│  └─ publish-reviews/      # 手冊發佈審查記錄（閘門證據，綁 commit sha）
├─ tools/foundry-lint/      # 文件檢查器＋自檢
└─ scripts/publish-handbook.sh  # 手冊 → 公開鏡像（P2 常設授權）
```

## 4. Context 預算（protocol 第 10 節 `C1`～`C5`）

**超過 20KB 的檔案禁止整份載入**，先 `grep -n` 定位再局部讀。本 repo 目前的大檔：

| 檔案 | 大小 | 備註 |
| --- | --- | --- |
| `skills/foundry-protocol/SKILL.md` | ~41KB | 整份讀約 1.2 萬 tokens。多數工單只需要其中一到兩節 |
| `skills/foundry-adopt/SKILL.md` | ~15KB | |
| `docs/pilot/pilot-log.md` | ~13KB | 歷史紀錄，除非要查典故否則不必讀 |
| `skills/foundry-platform/adapters/paperclip.md` | ~12KB | 只讀當前平台那一份，不要三份都載 |

**減法原則**：先給最小必要上下文跑一輪，不滿意再補。不要為了「準備完整」而預先載入整個 `docs/`。

## 5. 最常被違反的硬規則（速查，權威在 protocol）

引用規則請用**穩定 ID**（protocol 第 11 節），不要用節號——節號會隨增訂變動。

- `H1`～`H6` **觸發式 HITL 閘門**：未決事項未解／規格矛盾／要花錢／要對外／破壞性操作／平台權限外。
  **口訣：拿不準要不要問的時候，就是要問。**
- **鐵律：絕不自作主張採用建議值。** 文件裡的「建議 X」是待確認選項，不是決定。
- `G-C` **對外／不可逆核可不可調降**——`gates.external_actions` 只允許 `user`。
- `D1`～`D4` **缺陷收容**：能退回原單就不開新單。
- `W1`／`W2` **永久文件 vs 一次性意圖紀錄**：實作計畫、探索筆記寫工單留言，**不進版控**。
- **一單一分支**，分支名帶工單編號；commit 用 gitmoji ＋繁體中文標題。
- **commit 前先驗 `git symbolic-ref --short HEAD`**——本 repo 的 workspace 是共用的，
  併行的 heartbeat run 會互相干擾 checkout（known-drift `X1`，真的發生過）。

## 6. 指令速查

```bash
# 文件是否符合模板必備章節（type: brd|prd|hld|lld|review-report|test-plan）
python3 tools/foundry-lint/foundry_lint.py --type prd docs/features/<模組>/PRD.md

# repo 規範自檢（規則 ID 引用、手冊 nav 一致性、錨點、雙入口同步）
python3 tools/foundry-lint/foundry_lint.py --selfcheck

# 測試
python3 -m unittest discover tools/foundry-lint

# 一次跑完所有閘門（等同 pre-commit 會跑的內容）
make check

# 手冊網站本機預覽
mkdocs serve
```

## 7. 手冊改動的額外義務

動到 `docs/handbook/` 的工單，結案前必須走完 protocol 第 7 節「手冊發佈審查」四步：
**合併進 main → 用 `templates/publish-review.md` 寫審查記錄 → commit（`handbook_commit` 填實際 sha）→ 跑 `scripts/publish-handbook.sh`**。
腳本有證據閘門會核對記錄，繞不過去。這一段**沒有使用者介入點**（P2 常設授權），但漏做就是公開站與 repo 不一致。

⚠️ 新增手冊章節時要改**兩份 nav**：`mkdocs.yml` 與 `scripts/publish-handbook.sh` 內嵌的那份。
只改一份會導致公開站漏章（known-drift 已記錄此結構性漂移，`--selfcheck` 會擋）。
<!-- FOUNDRY:SHARED-BODY:END -->

## 8. 工具名對應（Codex／通用 harness）

本 repo 的 workflow 文件以工具中性的語彙描述動作，在 Codex 或其他 harness 中如此換算：

| 文件裡的說法 | 在 Codex／通用 harness 中 |
| --- | --- |
| 「載入 skill」 | **無自動載入機制**——把 `skills/foundry-protocol/SKILL.md` 與自己的角色 skill 當一般檔案讀進來（守 §4 的 context 預算，別整份載） |
| 「局部讀取檔案」 | `sed -n 'A,Bp' <檔案>`，或 `grep -n` 定位後再讀該區間 |
| 「執行指令」 | 直接在 shell 執行 |
| 「發互動卡」 | 對 Paperclip API `POST /api/issues/{id}/interactions`（形狀見 known-drift `S1`）；平台無互動卡機制時，改為輸出 .md 報告請使用者批示，**等到明確回覆為止，不得代答** |
| 「slash command」 | 無對應，照文檔逐步人工執行即可——本 repo 的 workflow 都是純 .md，不依賴特定 runtime 功能 |

- 本檔為 Codex 及其他 harness 的入口；Claude Code 讀 `CLAUDE.md`（正文相同）。
- **兩檔的共用正文必須逐字相同**（`FOUNDRY:SHARED-BODY` 標記之間），
  由 `foundry-lint --selfcheck` 機械比對；改一份就要改另一份。
