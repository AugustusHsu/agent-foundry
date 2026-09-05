---
name: foundry-browser
description: 瀏覽器與視覺能力 workflow。四種情況載入本文：① 工單需要開瀏覽器驗證前端、② 要在一個新的專案或新的 harness 上取得瀏覽器能力、③ 瀏覽器 MCP 工具呼叫失敗、④ 要建立一個具備瀏覽器能力的 agent。本文負責把「這個環境到底能做到哪一級」「不夠時怎麼補」「補不了時怎麼降級」收斂成固定四步。不得憑印象宣稱某個環境有或沒有瀏覽器能力。
---

# foundry-browser：瀏覽器與視覺能力

依 MYL-37 使用者裁定制定（裁定卡 `myl37-browser-capability-path-v1`、`myl37:browser:client-tiers-install:v1`、
`myl37:frontend-verifier:plan:f7cf0b84`）。使用者給的目的原文：

> 「我想要建立一個具有瀏覽器操控功能跟視覺的 agent，這部分可能因為所使用的平台如 claude code 或其他的
> 可能沒有這個功能，所以需要有一個 workflow 來提供檢查是否有相關功能來處理」
>
> 「如果需要在非 paperclip 的平台上使用的話，我希望能有對應的 workflow 可以協助建立相關 agent」

所以本 workflow 的目標**不是把瀏覽器裝起來**，是**讓「有沒有能力」變成可機械回答的問題**，
並在能力不足時給出明確的降級路徑，而不是讓 agent 用「應該可以」把驗證做成半套。

## 1. 什麼時候跑

| 觸發 | 情境 | 進入點 |
| --- | --- | --- |
| `BR-1` **要驗前端** | 工單的 AC 需要看實際渲染結果、互動行為或錯誤路徑 | 步驟 1 |
| `BR-2` **換環境** | 新專案、新 workspace、換 harness（Claude Code → Codex 等） | 步驟 1，跑完更新該專案設定 |
| `BR-3` **工具呼叫失敗** | MCP 工具不存在、或呼叫被權限擋掉 | 步驟 1，多半是 §3 的「兩把鑰匙只有一把」 |
| `BR-4` **要建瀏覽器 agent** | 在任何平台上建立具備瀏覽器能力的 agent | 步驟 1 → §5 |

不屬於本文範圍：測試計畫怎麼設計、斷言怎麼訂（那是 `roles/qa-engineer`）；
前端實作本身（那是 `roles/developer`）。

## 2. 能力等級 L0～L3

使用者已核可此四級（裁定卡 `myl37:browser:client-tiers-install:v1`，`tiers: accept`）。

| 等級 | 能做到 | 判定訊號 |
| --- | --- | --- |
| `L0` | 只有 HTTP：`curl`／`urllib` 取原始回應 | 一定成立 |
| `L1` | 渲染＋截圖，**不能互動** | 有 Chromium 家族或 Firefox 二進位 |
| `L2` | 互動：導航、點擊、填表、讀 console／network | L1 ＋ 有**已宣告且已放行**的瀏覽器 MCP server ＋ `npx` |
| `L3` | 深度診斷：Lighthouse 評分、效能 trace、Core Web Vitals | L2 ＋ 該 server 提供這些工具（現況只有 `chrome-devtools-mcp`） |

⚠️ 本節的 `L0`～`L3` 與 `docs/standards/known-drift.md` 的 `L1`～`L6`（平台限制）
**是不同命名空間**，不可互相引用。本文提到平台限制時一律寫全名。

**視覺（看得懂圖）是模型能力，不是機器能力**，不在上表內，要單獨驗（§2.1 第二段）。
一個 harness 可以有 L3 卻沒有視覺（那就只能靠 a11y 快照與 DOM 斷言，不能靠截圖判讀）。

### 2.1 步驟 1：盤點（機械層，不靠判斷）

```bash
python3 tools/browser-probe/probe_browser.py                 # markdown 表，可直接貼進工單留言
python3 tools/browser-probe/probe_browser.py --format json
python3 tools/browser-probe/probe_browser.py --min-level 2   # 低於 L2 則 exit 1
```

**盤點結果不得憑印象填寫，要附腳本輸出當證據。**
「文件說支援」「別的專案能用」都不是本環境可用的證據——設定是逐專案的。

視覺另外驗，因為它推不出來：

```bash
python3 tools/browser-probe/probe_browser.py --vision-fixture /tmp/vision.png
```

腳本產出一張內容固定的圖並印出預期描述；**實際讀那張圖再自我比對**。
描述不符或根本讀不到圖，就是沒有視覺能力，本輪驗證不得依賴截圖判讀。

### 2.2 步驟 2：判級並宣告

在工單留言寫明「本次以 `L<n>` 執行」。這句話決定了後面哪些斷言算數。

### 2.3 步驟 3：不夠就補（依平台，見 §3）

補完**重跑步驟 1 回查**，不看安裝指令回報成功，看盤點輸出的等級變了沒。

### 2.4 步驟 4：補不了就降級，並把降級寫進報告

降級不是失敗，**隱瞞降級才是**。報告必須寫明三件事：

1. 實際跑在哪一級、為什麼上不去。
2. **因此哪幾條斷言沒被驗到**——逐條列，不是一句「部分未驗」。
3. 那幾條斷言改由誰、用什麼方式補（人工測試、退回 QA Engineer 改測試計畫、或延到能力就位）。

| 降到 | 還能做 | 一定做不到 |
| --- | --- | --- |
| `L2`（無 L3） | 全部互動與斷言 | Lighthouse 評分、效能數據 |
| `L1`（無 L2） | 首屏渲染、視覺回歸、靜態 a11y 檢查 | 任何需要點擊或填表的斷言、錯誤路徑驗證 |
| `L0`（無 L1） | HTTP 狀態碼、回應標頭、SSR 後的 HTML 內容 | 任何依賴 JS 執行的結論 |

## 3. 怎麼補：三把鑰匙，缺一不可

MYL-37 實測得出的配方——**這是本文最容易被跳過、也最常導致失敗的一節**：

| 鑰匙 | 檔案 | 少了會怎樣 |
| --- | --- | --- |
| **宣告** | `.mcp.json`（project scope） | 工具根本不存在 |
| **放行** | settings 的 `permissions.allow` | **工具載入了，但每一次呼叫都被權限擋掉** |
| **信任** | `~/.claude.json` 的 `projects[<路徑>].hasTrustDialogAccepted` | **`.claude/settings.json` 的 `permissions.allow` 整份被忽略**——設定檔看起來完全正確，卻不生效 |

三個實測結論，都是反直覺的，不要再重推一次：

- ❌ **不能靠 `dangerouslySkipPermissions`**。帶著 `--allow-dangerously-skip-permissions`
  但 `permission-mode default` 時，MCP 呼叫照樣被擋。加了允許規則之後才不依賴任何權限提示通道。
- ⚠️ **Paperclip 的 run 以 `--setting-sources=project,local` 啟動（排除 `user`）**。
  所以全域裝的 MCP server（例如 `serena`）Paperclip 的 run 根本拿不到，
  設定必須落在 project／local scope 才算數。這也是全域慣例「新增 MCP 預設 `--scope project`」的機械理由。
- ⚠️ **信任閘門只擋版控的那份**。實測同一組規則：放 `.claude/settings.json` 全被擋
  （harness 明說 `Ignoring 2 permissions.allow entries ... this workspace has not been trusted`），
  改放 `.claude/settings.local.json` 則全通。這是設計如此——不讓 clone 來的 repo 自己給自己開權限。

### 3.1 於是版控與可用性互相拉扯，兩份都要寫

| 檔案 | 跟版控走 | 未信任時生效 | 角色 |
| --- | --- | --- | --- |
| `.claude/settings.json` | ✅ | ❌ | 可攜的權威宣告；換機器 clone 下來就有 |
| `.claude/settings.local.json` | ❌（被全域 gitignore 排除） | ✅ | 讓本機**現在**就能跑 |

**新工作區的標準動作**：跑 §2.1 盤點 → 若回報 `allowed_but_untrusted`，二選一——
把規則複製一份到 `.claude/settings.local.json`（立即生效，每台機器各做一次），
或請使用者把該路徑的 `hasTrustDialogAccepted` 設為 true（一次設定，之後 `settings.json` 就生效）。
⚠️ 後者是**使用者層設定變更**，依 `H6` 要問過再動，agent 不得自行改 `~/.claude.json`。

⚠️ Paperclip materialize 出來的 workspace **從沒被互動式開啟過，預設一律未信任**。
所以「在我的 repo 裡有效」不代表「在 Paperclip 的 run 裡有效」，兩邊都要用盤點腳本各驗一次。

本 repo 已依此配好（`.mcp.json` ＋ 兩份 settings），可直接當範本抄。

## 4. 兩個 client 怎麼選

實測（各自起 server 列出實際工具清單，非讀文件推論）：

| 能力 | `chrome-devtools-mcp` 1.8.0（29 工具） | `@playwright/mcp` 0.0.80（24 工具） |
| --- | --- | --- |
| 導航／點擊／填表／a11y 快照／console／network 讀取／截圖 | ✅ | ✅ |
| Lighthouse 評分、效能 trace、heap snapshot | ✅ **獨有** | ❌ |
| 跨瀏覽器（firefox／webkit）、裝置模擬、連上你正在用的瀏覽器 | ❌ | ✅ **獨有** |
| **測試進行中**按 URL 攔截單一端點 | ❌ 無此工具 | ✅ `browser_run_code_unsafe` → `page.route()` |
| 啟動時就固定的 URL 黑名單 | ✅ `--blockedUrlPattern`（URLPattern 語法） | ✅ `--blocked-origins`（只到 origin 粒度） |
| 全站斷網 | ✅ `emulate` 的 `networkConditions: Offline` | ✅ |

**核心的「檢查／審查前端頁面」兩邊都滿足，差別在外圍。** 判準：

- 要 **Lighthouse／效能數據** → `chrome-devtools-mcp`。
- 要**故障注入**（只擋某一條 API、其他照常）→ `@playwright/mcp`。
  `chrome-devtools-mcp` 的 `--blockedUrlPattern` 雖然也吃 URL 樣式，但它是**啟動旗標**：
  測試中途無法加上或解除，所以做不到「先擋 → 驗錯誤路徑 → 解除 → 驗重試成功」這種序列。
  用 `evaluate_script` 猴補 `window.fetch` 可以繞，但那是應用層 hack（只蓋 `fetch`、
  每次導航要重注入、且改動了受測程式的執行環境，等於讓驗證工具自己變成變因）——**不列為常態手段**。
- 兩個都掛沒有衝突（工具名不同前綴），且 MCP 工具在本 harness 是**延遲載入**
  （只有工具名進 context，schema 用到才取），所以兩個都掛的 context 成本約是 53 個名稱，不是 53 份 schema。
  ⚠️ 這一條推翻了「兩個都掛違反 context 預算」的舊說法，該說法已作廢。

### 4.1 兩個踩過的坑

- `chrome-devtools-mcp` 的 `--pageIdRouting` 預設為 true：多數工具**必須帶 `pageId`**，
  要先 `new_page` 或 `list_pages`。第一次呼叫漏帶會整批失敗。
- `@playwright/mcp` 預設**封鎖 `file:` 協定**且把檔案存取限制在 workspace root，
  開本機 HTML 檔要先起 http server（或加 `--allow-unrestricted-file-access`，不建議）。
  它也會把快照／截圖寫進 `--output-dir`，本 repo 指向 `.playwright-mcp/`（已 gitignore）。

## 5. 建立一個有瀏覽器能力的 agent（`BR-4`）

先跑 §2.1 盤點。等級不足就先做 §3，**不要先建 agent 再補能力**——
建好卻沒有工具的 agent 會在第一張工單就卡住，而且看不出是設定問題還是判斷問題。

| 平台 | 承載處 | 動作 |
| --- | --- | --- |
| **Claude Code**（無 agent 註冊表） | repo 本身 | `.mcp.json` ＋ 兩份 settings（§3.1）寫進該 repo；角色規範靠 repo 根的 `AGENTS.md`／`CLAUDE.md` 雙入口進 context。**不需要任何平台權限**，但要過信任閘門。 |
| **Paperclip** | agent 記錄 | `POST /api/companies/{cid}/agents` 建 agent（需 `canCreateAgents`），工具仍靠上一列的 `.mcp.json` ＋ settings。平台的工具閘道（`tools/mcp/import-json`、`tool-profiles`、`trust-rules`）**全部 board-only**，agent 打過去一律 `Board access required`——那一層只多給綁定與審計，**不是取得能力的必要條件**。⚠️ materialize 出來的 workspace 預設未信任，見 §3.1。 |
| **其他 harness** | 視其設定格式 | 先確認它讀不讀 `.mcp.json`；不讀就照它自己的 MCP 設定路徑寫一份，然後**回到 §2.1 用盤點腳本驗證**，不要假設寫了就生效。 |

⚠️ **`.mcp.json` 綁的是「情境」不是「人」**：放在共用 repo 裡，該 repo 的**所有** agent 都拿得到工具。
要讓工具只屬於某一個 agent，必須靠平台的 tool-profile 綁定（Paperclip 為 board-only）。
建 agent 時如果宣稱「只有它有瀏覽器」，先確認這句話在你的承載處成不成立。

### 5.1 驗收：建完要跑一次最小端到端

不要用「工具列表裡有」當驗收。最小驗收是一次真的故障注入：

1. 起一個本機 http server，頁面上有兩個按鈕分別打 `/api/items/label`（批量）與 `/api/items/42/label`（單張）。
2. `page.route('**/api/items/label', r => r.abort())`。
3. 點批量 → 預期失敗橫幅；點單張 → 預期成功。
4. **兩者結果不同**才算通過——只驗到「都失敗」代表你擋的是整站，等於沒驗到精準攔截。

## 6. 安全硬規則

- **兩套 profile 硬分離**：驗證一律用隔離 profile（`--isolated`，無登入態）；
  需要登入態的日常任務用另一份設定，**絕不共用**。
  本 repo 的 `.mcp.json` 把 `--isolated` 寫死，讓這條規則由設定保證，而不是只靠自律。
- `browser_run_code_unsafe` 依其自述為 RCE-equivalent：**僅限本機 dev server**，
  程式片段必須寫進報告，**不得在持有登入態時對外部站點使用**。
- 對正式站只做唯讀瀏覽；任何破壞性操作依 protocol `H5` 升級給使用者。
- 需要付費的服務（Lighthouse 之外的第三方掃描等）依 `H3` 升級，不自行採用。

## 7. 唯讀檢視模式（`F1`／`F2`）

規則本體是 protocol `F1`（等級邊界）與 `F2`（效力邊界），本節只寫怎麼執行。
**適用對象**：Frontend Verifier 以外、需要親眼確認畫面的角色（現況是 CEO 與 PM）。

| 邊界 | 可以 | 不可以 |
| --- | --- | --- |
| **等級**（`F1`） | `L1`：開頁、等渲染、截圖 | 一切互動——點擊、填表、導航到要操作才到得了的狀態、故障注入、跑 Lighthouse |
| **效力**（`F2`） | 當「要不要叫 Frontend Verifier 去驗」的判斷材料 | 當關卡證據、當缺陷成立的依據 |

⚠️ **上限是角色給的，不是環境給的。** §2.1 盤出 `L2`／`L3` 只說明這台機器做得到，
不解除 `F1`；判「我這次能做到哪裡」要先看自己是誰，再看盤點結果，兩者取小。

### 7.1 為什麼這條邊界靠規則、不靠工具

因為在本 repo 的承載處**切不開**：`.mcp.json` 綁的是「情境」不是「人」（§5 末），
repo 裡放了瀏覽器 MCP，該 repo 的所有 agent 就都拿得到——**CEO 早就有工具了**，
本節不是在給它能力，是在限定它怎麼用。

平台的 tool-profile 是唯一能綁到人的機制，但它解不了這題，兩個原因：

1. **board-only**（§5 表格第二列）：agent 打過去一律 `Board access required`，規則層改不動它。
2. **粒度是「工具」不是「等級」**：`L1` 與 `L2` 共用同一批 MCP 工具——截圖與點擊出自同一個
   server，要擋互動就得把整個 server 拿掉，連截圖也一起沒了。那不是限制等級，是取消能力。

⇒ 所以 `F1`／`F2` 在 protocol 標的是 `【自律】`，**沒有機械後盾**。
反過來也一樣：宣稱「某個角色沒有瀏覽器」之前先照 §2.1 盤點，不要憑角色設定的外觀判斷。

## 8. 證據要求

- 截圖要說明**「載入到什麼狀態、由哪個 selector 或 uid 確認」**，不是配一句「看起來沒問題」。
- 一個 viewport 過了不等於跨 viewport 過了；不外推未驗證的結論。
- 靜態內容用 `curl` 就好，不為了用瀏覽器而開瀏覽器。
- 截圖以 attachment／work-product 上傳（`mediaKind: image`，看板可預覽），不只貼本機路徑。

## 9. 檔案地圖

| 檔案 | 內容 |
| --- | --- |
| `SKILL.md`（本文） | 四步流程、L0～L3 分級、補齊與降級、建 agent 的跨平台做法、唯讀檢視模式 |
| `tools/browser-probe/probe_browser.py` | 步驟 1 的盤點腳本（MCP server 登記表也在這裡） |
| `.mcp.json` ＋ `.claude/settings.json` | 本 repo 的「三把鑰匙」實例，可當範本（第三把在 `~/.claude.json`，不在 repo 內） |
| `skills/roles/frontend-verifier/SKILL.md` | 執行這類驗證的角色判準 |
| `docs/standards/known-drift.md` | 平台限制與反悔錄 |
