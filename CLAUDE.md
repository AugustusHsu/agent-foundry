# agent-foundry — 接手入口（Claude Code）

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
   ⚠️ 全 repo 最大的一份，**不要整份讀**（見 §4）。先 `grep -n '^#\{1,3\} '` 取標題地圖，再讀需要的節。
2. **`docs/standards/known-drift.md`** — 已知漂移與反悔錄。**動手前讀這份**：
   哪些 API 會 403、哪些提案已經被否決過、哪些缺口是使用者知情下保留的。
   不讀這份，很容易花一整輪去重踩一個已經有結論的坑。
3. **自己的角色 skill**（`skills/roles/<角色>/SKILL.md`，約 60–120 行）——只寫該角色獨有的判準。
4. `.foundry/config.yml` — 本專案的關卡與 push 授權設定（**agent 不得自行改動**）。

## 3. 地圖：我想要…→前往

先從**意圖**找入口；不確定某樣東西放在哪，再看下面的目錄結構。
每一格只給去處，不給規則——規則以該處的文件為準。

| 我想要… | 前往 |
| --- | --- |
| 改全隊硬規則（改了會改變每個 agent 的行為） | `skills/foundry-protocol/SKILL.md`。新增條款要同步在第 11 節登記規則 ID，否則 `--selfcheck` 擋下；改動同時觸發手冊同步戳記（見 §7） |
| 改某個角色獨有的判準 | `skills/roles/<角色>/SKILL.md`。跨角色共通的規則屬 protocol，別寫進角色 skill |
| 改使用手冊 | `docs/handbook/`，並照 §7 走完發佈四步；新增章節要改**兩份** nav |
| 加一項機械檢查 | `tools/foundry-lint/foundry_lint.py` 的 `SELFCHECKS` ＋同目錄測試（每項檢查都要配一個擋得住的反例），`make check` 驗 |
| 把 Foundry 導入一個專案 | 全新專案走 `skills/foundry-init/`；已有開發活動的走 `skills/foundry-adopt/` |
| 調關卡粒度（哪一關要誰簽） | `skills/foundry-gates/` ＋ `.foundry/config.yml`（agent 不得自行改；`G-C` 不可調降） |
| 查「這個坑是不是已經有結論」 | `docs/standards/known-drift.md`——動手前必讀，別重踩已經有裁定的事 |
| 換某個角色的模型供應商 | `skills/foundry-model-routing/`；先 `make providers` 盤點，別憑印象回答 |
| 讓 agent 看得到畫面／驗前端 | `skills/foundry-browser/`；先 `make browser` 判級，三把鑰匙見 §5 |
| 寫 BRD／PRD／HLD／LLD／測試計畫 | `templates/` 取對應模板，寫完跑 `make lint-doc TYPE=… FILE=…` |
| 知道換到別的平台這步怎麼做 | `skills/foundry-platform/` ＋當前平台的 adapter（只讀一份，見 §4） |

### 目錄結構

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
│  ├─ foundry-model-routing/ # workflow：模型供應商路由（哪個角色用哪一家）
│  ├─ foundry-browser/      # workflow：瀏覽器與視覺能力（L0～L3 探測、補齊、降級）
│  └─ roles/<角色>/         # 第 2 層：角色薄 skill（7 個角色）
├─ templates/               # BRD / PRD / HLD / LLD / test-plan /
│                           #   review-report / publish-review
├─ docs/
│  ├─ handbook/             # 使用手冊（8 章）＝說明層，會發佈到公開站
│  ├─ standards/            # 契約與已知漂移（不發佈）
│  ├─ features/<模組>/      # 各模組的 BRD/PRD/HLD/LLD 與審查報告
│  └─ publish-reviews/      # 手冊發佈審查記錄（閘門證據，綁 commit sha）
├─ tools/foundry-lint/      # 文件檢查器＋自檢
├─ tools/model-routing/     # 供應商盤點腳本（哪幾家 CLI 真的可用）
├─ tools/browser-probe/     # 瀏覽器能力盤點腳本（L0～L3 判級）
├─ .mcp.json ＋ .claude/settings.json  # 瀏覽器 MCP 的宣告與放行（見下方 §5 第三把鑰匙）
└─ scripts/publish-handbook.sh  # 手冊 → 公開鏡像（P2 常設授權）
```

## 4. Context 預算（protocol 第 10 節 `C1`～`C5`）

**超過 20KB 的檔案禁止整份載入**，先 `grep -n` 定位再局部讀。

<!-- FOUNDRY:BIG-FILES:BEGIN -->
下表**故意不寫每個檔案幾 KB**——寫死在散文裡的數字沒有人會回來改，只會愈漂愈遠；
要現值自己 `ls -l`。清單本身則是機械維護的：`--selfcheck` 的 `big-files` 會掃
`skills/` 與 `docs/`（不含 `docs/features/`，那是各模組自己的交付物），
**每個 12KB 以上的 .md 都必須列在下表**，漏列或路徑失效就擋下。
門檻以下的檔案要不要一併列出，屬編輯判斷。

| 檔案 | 通常只需要哪一部分 |
| --- | --- |
| `skills/foundry-protocol/SKILL.md` | 全 repo 最大的一份。先 `grep -n '^#\{1,3\} '` 取標題地圖；多數工單只需要其中一到兩節 |
| `docs/standards/known-drift.md` | 動手前必讀，但依分類取用：L＝平台限制、S＝API 形狀、R＝反悔錄、X＝併發競態 |
| `skills/foundry-adopt/SKILL.md` | 只在導入既有專案時讀，讀當前模組那一節即可 |
| `skills/foundry-browser/SKILL.md` | 只在要驗畫面時讀；先 `make browser` 判級，再讀對應層級那一節 |
| `docs/pilot/pilot-log.md` | 歷史紀錄，除非要查典故否則不必讀 |
| `skills/foundry-init/SKILL.md` | 只在導入全新專案時讀 |
| `skills/foundry-platform/adapters/github.md` | 兩種用途各佔一半：`platform: github` 的動詞對照，與「鏡像模式」規格。要哪一個讀哪一節 |
| `skills/foundry-platform/SKILL.md` | 9 個動詞的介面定義。只讀你要用的那個動詞那一節；§5 的「全覆蓋」裁定只在新增平台或新增文檔目標面時才需要 |
| `skills/foundry-platform/config-schema.md` | `.foundry/config.yml` 的欄位權威。依段落取用——`gates`／`push`／`model_routing`／`docs` 四段互相獨立，別整份載 |
| `skills/foundry-platform/adapters/paperclip.md` | 未達門檻但一樣別整份載：只讀當前平台那一份，不要三份都載 |
<!-- FOUNDRY:BIG-FILES:END -->

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
- **瀏覽器 MCP 要能用得湊齊三把鑰匙**：`.mcp.json` 宣告、settings `permissions.allow` 放行、
  以及**工作區信任**。少了第三把時 `.claude/settings.json` 的放行規則**整份被忽略**，
  設定檔看起來完全正確卻不生效（known-drift `L8`）。用 `make browser` 判定，不要憑設定檔外觀判斷。

## 6. 指令速查

```bash
# 文件是否符合模板必備章節（type: brd|prd|hld|lld|review-report|test-plan）
python3 tools/foundry-lint/foundry_lint.py --type prd docs/features/<模組>/PRD.md

# repo 規範自檢（雙入口同步、手冊 nav 一致性、錨點、規則 ID 引用、大檔清單、相對連結、手冊戳記）
python3 tools/foundry-lint/foundry_lint.py --selfcheck

# 測試
python3 -m unittest discover tools/foundry-lint

# 一次跑完所有閘門（等同 pre-commit 會跑的內容）
make check

# 盤點本機可用的模型供應商（foundry-model-routing 步驟 1；別憑印象回答這題）
make providers

# 盤點本機瀏覽器能力 L0～L3（foundry-browser 步驟 1；同樣別憑印象回答）
make browser

# 手冊網站本機預覽
mkdocs serve
```

## 7. 手冊改動的額外義務

動到 `docs/handbook/` 的工單，結案前必須走完 protocol 第 7 節「手冊發佈審查」四步：
**合併進 main → 用 `templates/publish-review.md` 寫審查記錄 → commit（`handbook_commit` 填實際 sha）→ 跑 `scripts/publish-handbook.sh`**。
腳本有證據閘門會核對記錄，繞不過去。這一段**沒有使用者介入點**（P2 常設授權），但漏做就是公開站與 repo 不一致。

⚠️ 新增手冊章節時要改**兩份 nav**：`mkdocs.yml` 與 `scripts/publish-handbook.sh` 內嵌的那份。
只改一份會導致公開站漏章（known-drift 已記錄此結構性漂移，`--selfcheck` 會擋）。

反方向也有一條（MYL-44）：**動到 protocol 的工單要同步手冊**。`03`／`04`／`06`／`07`
四章各掛一行「最後對照 protocol」戳記，pre-commit 在「改了 protocol 卻沒動手冊」時擋下，
`--selfcheck` 的 `handbook-stamp` 再驗戳記沒落後。判準與被擋下時的三條處置見 protocol 第 7 節。
<!-- FOUNDRY:SHARED-BODY:END -->

## 8. 工具名對應（Claude Code）

本 repo 的 workflow 文件以工具中性的語彙描述動作，在 Claude Code 中如此換算：

| 文件裡的說法 | 在 Claude Code 中 |
| --- | --- |
| 「載入 skill」 | skill 由 Paperclip runtime materialize 後自動進 context；`skills/` 下的 SKILL.md 亦可直接讀取 |
| 「局部讀取檔案」 | `Read` 工具帶 `offset`／`limit`，或 `Grep` 定位後再讀 |
| 「執行指令」 | `Bash` 工具 |
| 「發互動卡」 | 對 Paperclip API `POST /api/issues/{id}/interactions`（形狀見 known-drift `S1`） |
| 「slash command」 | `/foundry-init` 等（可選增強；缺了照文檔人工跑也成立） |

- 本檔為 Claude Code 的入口；Codex 及其他 harness 讀 `AGENTS.md`（正文相同）。
- **兩檔的共用正文必須逐字相同**（`FOUNDRY:SHARED-BODY` 標記之間），
  由 `foundry-lint --selfcheck` 機械比對；改一份就要改另一份。
