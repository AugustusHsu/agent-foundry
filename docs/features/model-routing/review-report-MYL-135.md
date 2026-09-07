# 審查報告：MYL-135 known-drift 收容 effort 值域知識（`L31`），`apply_profile.py` 註解降為指標

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-135 |
| 分支 | `MYL-135-known-drift-l31` |
| 審查範圍 | 單一 commit `6966d82`；`docs/standards/known-drift.md`（+1 列）、`tools/model-routing/apply_profile.py`（註解 14 行→3 行），合計 +4/-14 |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-08 |

## 0. 收件檢查與機械層

交接物齊：三段式交付回報（留言 `7da42533`）、分支名帶工單編號、commit 訊息已落在 commit 上。

第 1 層固定三條（在 `git clone --shared` 的隔離副本執行——共用 workspace 此刻被
`MYL-117` 的 run 佔在別的分支上，`X1`）：

| 指令 | 結果 |
| --- | --- |
| `make check` | **rc 0**；18 項自檢全綠；四支 suite `342 / 49 / 34 / 107` 全 `OK` |
| `git diff --name-only main...HEAD` | 兩檔，皆屬本單，無夾帶 |
| `git log --oneline main..HEAD` | 一顆 commit，gitmoji ＋繁體中文標題，合格 |

**額外補的一條（本輪判斷加做，非固定三條）**：分支基底是共用 workspace 的本地 `main`
（`9977e56`），而權威 `main` 是 `origin/main`（`6d7d52f`）——**基底落後 4 顆 commit，且那 4 顆
正是 MYL-129 對同一支 `apply_profile.py` 的大幅改寫**。只驗分支原樣不足以擔保合併後仍成立，
故另建 `merge-test` 合併 `origin/main` 後重跑：

- 合併**自動成功、無衝突**（MYL-129 動的是第 64 行以後，本單動的是第 30–35 行）。
- 合併後 `make check` **rc 0**，18 項自檢全綠，四支 suite `342 / 61 / 34 / 107` 全 `OK`
  （`model-routing` 由 49 增為 61 是 MYL-129 帶進來的測試，非本單影響）。
- 合併後複核 `MODEL_TARGETS` 六格與註解三行，內容與分支上一致。

## 1. AC 逐條核對

證據皆為本輪自行執行，未採信交付回報的宣稱。

| AC | 結果 | 證據 |
| --- | --- | --- |
| `grep -c '^\| L31 \|'` 回 `1` | ✅ | 回 `1`；位置在 §1 表尾（`known-drift.md:51`，介於 `L30`:50 與 `## 2.`:53 之間） |
| 該列涵蓋 (a) 值域隨 model 而異，寫得出 `gpt-5.5` 只到 `xhigh` | ✅ | 第 3 欄 (a) 段明寫；**獨立重跑 `codex debug models`**：`gpt-5.6-sol` 與 `gpt-5.6-terra` ＝ `low, medium, high, xhigh, max, ultra`；`gpt-5.5` ＝ `low, medium, high, xhigh`（**無 `max`**）。與條文相符 |
| (b) 兩份 CLI 自述過時且不得當權威 | ✅ | 見下方「引用位置獨立查核」四格全對 |
| (c) catalog 與 API enum 兩集合不重疊（點名 `ultra`） | ✅ | 條文明寫兩份值域。**獨立查核**：全 catalog 出現過的 effort 值 ＝ `{low, medium, high, xhigh, max, ultra}`——有 `ultra`、且**完全沒有 `none`／`minimal`**，正是條文說的分岔方向 |
| 指向 CLI 原始碼的行號都帶版本／樹別註記 | ✅ | `L31` 只有兩處行號引用，皆帶註：`codex-local/src/index.ts:27`（`0.3.1` 樹；`2026.831.1` 對應 `dist/index.js:84`，兩棵樹同文）／`claude-local/src/index.ts:20`（`0.3.1` 樹；`2026.831.1` 對應 `dist/index.js:37`） |
| `apply_profile.py` 不再含三條事實的敘述副本 | ✅ | `grep -n 'supported_reasoning_levels\|invalid_enum_value\|過時' …` **回空（rc 1）**；另做語意面複讀，見第 2 節 |
| `grep -n 'L31' …` 至少一筆 | ✅ | `apply_profile.py:35` |
| `grep -n 'xhigh' …` 仍取得到「不要改成 `xhigh`」 | ✅ | `apply_profile.py:33`：「這張表 high 層的 effort 用 `"max"`，**不要改成 `"xhigh"`**」 |
| `MODEL_TARGETS` 值一格未動 | ✅ | `git diff main HEAD -- tools/model-routing/apply_profile.py \| grep -E '^[+-][^+-]' \| grep -vc '^[+-]#'` ⇒ **0**（非註解行零變更）；合併後另肉眼複核六格 |
| `make check` 全綠 | ✅ | 分支原樣與合併 `origin/main` 後各一次，皆 rc 0 |
| 兩支 suite 全過 | ✅ | `tools/model-routing` `OK`、`tools/foundry-lint` `342 OK` |

### 引用位置獨立查核（不採信「已實查過」的宣稱）

| 引用 | 實際內容 | 版本 |
| --- | --- | --- |
| `codex-local/src/index.ts:27` | `… (minimal\|low\|medium\|high\|xhigh) passed via -c model_reasoning_effort=…` | `package.json` ＝ `0.3.1` ✅ |
| `adapter-codex-local/dist/index.js:84` | **與上一行逐字相同** | `2026.831.1` ✅ |
| `claude-local/src/index.ts:20` | `- effort (string, optional): reasoning effort passed via --effort (low\|medium\|high)` | `0.3.1` ✅ |
| `adapter-claude-local/dist/index.js:37` | **與上一行逐字相同** | `2026.831.1` ✅ |

四格全中：行號指到的內容、兩份自述的值域、以及「兩棵樹同文」這個宣稱，都成立。
`0.3.1` 樹取自 `code/Python/paperclip/packages/adapters/`，`2026.831.1` 取自實跑的 npx 快取
（`~/.npm/_npx/…/node_modules/@paperclipai/`）——兩棵樹是不同的東西，條文有區分，正確。

### 唯一未獨立重跑的半條，與替代擔保

(c) 的「伺服器 400 回的 enum」那半邊**我沒有重打**：那要真的送一個非法值去撞供應商伺服器，
屬 `H3`（要花錢）的動作，為了複驗一條已 APPROVED 的觀測而消耗額度不成比例。改以**搬運忠實度**
擔保——把 `L31` 寫的值域與 `main` 上被本單刪掉的原註解逐字正規化比對：

```
L31        : ['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']
原註解(main): ['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']
⇒ 相同（值與順序皆同）
```

原註解是 MYL-133 第 1 輪 APPROVED 併入 main 的內容，該輪已對這發 400 做過獨立重跑。
故本單在這半條上是**零失真搬運**，證據強度承接自 MYL-133，不因本單而衰減。
Developer 在交付回報風險 1 主動點名這是唯一缺口——揭露準確，處置同意。

## 2. 四維檢查

- **正確性**：無發現。本單非註解行零變更，無執行路徑改動；`MODEL_TARGETS` 六格未動已機械證明。
  另打穿一處交付回報**沒有點名**的宣稱：`L31` 處置欄斷言「本 repo **刻意不對值域做機械驗證**」——
  這是一句對 repo 現況的斷言，若別處其實藏了值域白名單，`L31` 就會是一份錯的權威。`grep` 全
  `tools/` 與 `.foundry/`：命中的只有 `MODEL_TARGETS` 的兩格字面值與那句決定本身；
  `probe_providers.PROVIDERS` 持有的是 `effort_key`（**鍵名**，MYL-129 加的），不是值域。宣稱成立。

- **規格符合度**：無偏離。本單無 HLD／LLD，工單 AC 即規格，逐條對上。
  **放 §1 而非 §2** 是 PM 於 MYL-134 的裁定，Developer 維持原判並在 commit 訊息寫明理由（工單要求）。
  我核對兩節前言：§1「權限邊界或**平台能力邊界**」容得下「值域不歸我方所有」；§2「會回 4xx
  但**錯誤訊息不會告訴你原因**」確實不合——這條的 400 自帶完整合法值域，訊息講得很清楚。
  裁定與執行皆成立，不重議。
  **銷案宣稱查核**：對照 `review-report-MYL-133.md` §4，建議 1 ＝行號帶版本註（報告當時甚至逐字
  建議「（0.3.1 樹；2026.831.1 的 `dist/index.js:84` 同文）」，`L31` 照辦）、建議 2 ＝ `ultra` 分岔點
  （`L31` 已收）。兩條確實被本單吸收，不是空頭宣稱。

- **安全性**：無發現。純文件與註解改動，`L31` 未帶任何金鑰、token 或不宜公開的內容
  （條文引用的皆為本機路徑與公開的 model 代號）。`known-drift.md` 不在發佈範圍。

- **可維護性**：無會造成負擔的問題。逐句複讀 `apply_profile.py:33-35`，問「這三行有沒有任何
  一句是**事實**而不是**決定**」（Developer 點名要打穿的第二處）：
  - 33 行「這張表 high 層用 `"max"`，不要改成 `"xhigh"`」＝**決定**，貼著它拘束的那張表，正確留下。
  - 33 行括號「（MYL-133 已查證兩邊皆合法）」＝這是**這張表這兩格的單點結論**，即決定的依據；
    它不承載 `L31` 三條事實中的任何一條，也不重述查證方法或值域。**判不構成第二份拷貝**——
    真要挑，它與那條決定同生共死（model 換掉時兩者一起失效，而讀者被 `L31` 接住）。
  - 34–35 行＝**指標**。
  結論：已降乾淨。

  **`table-shape` 是否假綠**（Developer 點名的第一處）：`L31` 內文含 `minimal\|low\|…` 這類管線字元，
  全部寫成 `\|`。我按 GFM 規則自行重切一次（切格先於 inline 解析，只有 `\|` 逃得掉——MYL-98 的形狀）：
  **得 4 欄**，與 §1 表頭 `| # | 動作 | 結果 | 正解 |` 一致，各欄邊界落在語意正確的位置
  （欄 2 ＝動作 130 字、欄 3 ＝結果 952 字、欄 4 ＝正解 720 字）。逃逸字元全部落在 code span 內，
  還原後為 `|`。**不是假綠**。

## 3. 重大瑕疵清單

無。

## 4. 次要建議

1. **`L31` 引用的四個位置沒有機械後盾，這是刻意接受的，我同意不補**。Developer 在風險 2 已自陳：
   adapter 改版後行號會失效而 `internal-links` 抓不到（它不管 repo 外路徑）。我的看法是**不值得
   為它加自檢**——要檢查的目標在 repo 外、且其中一棵還在 npx 快取裡，檢查器本身的路徑就會先漂掉，
   加了只會製造一項會假紅的自檢。條目已寫明「兩棵樹同文」並留下可 `grep` 的散文，對不上時讀者
   知道要去搜那句話而不是那個行號——這個降級是對的。列此僅為留痕，非要求改動。
2. **`L31` 反向描述了 `apply_profile.py` 註解的形狀**（「`MODEL_TARGETS` 旁只留……那條決定」）。
   嚴格說這讓 known-drift 對 repo 的一處實作細節產生依賴，有人改註解時它會靜默過期。
   但這句話正是本單「決定貼著表、事實只有這裡一份」這個安排的說明，對讀者有用，
   且過期的代價只是一句話講得比現況細——**維持現狀可接受**，不建議改。

## 5. 分支收尾檢查

- 合併時點合規：本單掛審查單，合併在 APPROVED 之後（protocol 第 7 節）。
- ⚠️ **給合併者的提醒**：分支基底是**落後 4 顆 commit 的本地 `main`**。合併前必須先把 `main`
  快進到 `origin/main`（`6d7d52f`），否則會拿一個不含 MYL-129 的 main 去合併，推送時還會撞
  non-fast-forward。合併後狀態已於本輪 `merge-test` 預先驗過：無衝突、`make check` rc 0。
- 分支狀態：**已合併並刪除**（見結案留言的 commit hash）。
- 未動 `docs/handbook/` 與 protocol ⇒ 不觸發第 7 節手冊發佈四步，`handbook-stamp` 亦不適用。
- `M4`（實作與審查不得同一供應商）本輪**前提未成立**：active profile 為 `claude-only`，
  全隊同一家，屬條件未成立而非違規——與 Developer 的判讀一致。

## Verdict

**✅ APPROVED**
