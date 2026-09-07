# 審查報告：MYL-136 `apply_profile.py` 新增 opt-in `--smoke`：套用後當場驗值域／model 代號／額度

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-136 |
| 分支 | `MYL-136-smoke-flag`（第 2 輪 `bfba989`；第 1 輪 `d4d07f3`） |
| 審查範圍 | `main...HEAD` 五檔：`apply_profile.py`（+345）、`test_apply_profile.py`（+492）、`probe_providers.py`（+47）、`known-drift.md`（+2/-1）、`foundry-model-routing/SKILL.md`（+14/-2） |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-08 |
| 輪次 | 第 2 輪（複審；第 1 輪報告見留言 `e3605ec9`） |

## 0. 收件檢查與機械層

交接物齊：三段式交付回報（留言 `f38bb5c0`）、分支名帶工單編號、commit 訊息在 commit 上。
全程在 `git clone --shared` 的隔離副本作業——共用 workspace 此刻被 MYL-118 的 run 佔在
`MYL-117-parent-mandate` 上（`X1`），未動它的 checkout。

| 第 1 層固定三條 | 結果 |
| --- | --- |
| `make check` | **rc 0**；四支 suite `376 / 84 / 34 / 107` 全 `OK`；19 項自檢全綠 |
| `git diff --name-only main...HEAD` | 五檔，全屬本單；無夾帶 |
| `git log --oneline main..HEAD` | 三顆，`✨`／`🐛` 兩顆合格；`7dc0972` 是 `git merge` 的預設英文訊息（見次要建議 3） |

`mirror-recon` 在隔離 clone 預設是 ⏭（讀不到鏡像端）。**補一條 GitHub remote 讓它真的跑過**：
✅ 來源端 80 張、鏡像端 66 張——19 項全部是實際檢查過的綠，不是跳過。

## 0b. 上一輪瑕疵逐項覆驗（複審主體）

複審對著上一輪的清單驗，不重新全面審查。第 1 輪只有一項重大瑕疵。

| # | 上一輪要求 | 結果 | 我自己驗到的證據 |
| --- | --- | --- | --- |
| 1 | 「claude 的 effort 值域錯誤被 smoke 判成 ✅、整體 exit 0」；修法 (a) 補偵測／(b) 縮宣稱，二擇一或並用，各配擋得住的反例 | ✅ **兩條都做了** | 見下方三段 |

**(a) 補偵測**——`probe_providers.py` 新增 `smoke_silent_reject` 欄（claude ＝
`("Unknown --effort value",)`、codex ＝ `()`、未實證五家 ＝ `None`），
`apply_profile.smoke_verdict()`（`:652-670`）判「rc≠0 **或** 命中該家樣態 ⇒ 沒收下」。

**端到端重現第 1 輪那個假綠燈**（替身 CLI 逐字重播實測 stderr ＋ exit 0，零額度）：

```
$ python3 tools/model-routing/apply_profile.py --smoke --target claude:claude-opus-5:bogus-effort-xyz
- ❌ `claude:claude-opus-5:bogus-effort-xyz` → exit 0，但供應商回報沒有採用送進去的值
     （命中樣態 'Unknown --effort value'）——這種靠 exit code 看不出來，見 `L33`；供應商原文：
❌ smoke 有 1 組被拒：`claude:claude-opus-5:bogus-effort-xyz`
工具 EXIT = 4
```

同一條指令，第 1 輪是 `✅` ／ `EXIT=0`。

**登記表那個樣態字串對得上真實輸出——我自己重取了一次，零額度**（用 `L33` 記的取樣法：
非法 model ＋非法 effort，警告是 CLI 在請求送出前印的）：

```
$ claude -p --model bogus-model-xyz-does-not-exist --effort bogus-effort-xyz "…"
EXIT = 1
stderr: Warning: Unknown --effort value 'bogus-effort-xyz' — ignoring it and using the
        default effort. Valid values: low, medium, high, xhigh, max.
⇒ 登記表樣態 'Unknown --effort value' 命中：True
```

這一步是必要的：整個修法建立在「那個字串真的會出現」上，而它是本次交付裡**唯一無法從
repo 內部驗證的外部事實**。取樣法本身也被證實是零成本的。

**(b) 縮宣稱**——`SMOKE_BOUNDARY`（`:531-541`）拿掉「三種失敗**它都看得到**」，
改成「**「不收」看不看得見逐家不同**」＋「請讀那一行，不要把整體讀成『都看得到』」；
且逐組印出偵測強度，**由登記表機械推導**（`smoke_detection_note`，`:600-604`），
不留第二份會漂開的拷貝。實跑兩組對照：

```
- ✅ `claude:claude-opus-5:max`（偵測強度：exit code ＋輸出樣態比對——…字樣一改比對就靜默失效…）
- ✅ `codex:gpt-5.6-sol:max`（偵測強度：exit code——不收就炸，不依賴輸出字樣）
```

## 1. AC 逐條核對

| AC | 結果 | 證據（我自己跑的） |
| --- | --- | --- |
| `--help` 列出 `--smoke`，說明寫明「驗值域／model 代號／額度，不驗平台是否寫對（那是 `--check`）」 | ✅ | 實跑 `--help`：`--smoke` 在，邊界整段在，含「**不驗**平台把 config 寫對了沒有…回讀平台是 `--check` 的職責」。**第 1 輪這格是「字面成立、內容不實」，本輪成立**——那句話現在與實測相符 |
| 不帶 `--smoke` ⇒ 零供應商呼叫 | ✅ | `test_apply_without_smoke_calls_no_provider_at_all`；我的突變 M15（`run()` 的 `smoke=args.smoke`→`smoke=True`）讓它連同另兩支一起紅 |
| 帶 `--smoke` 只打相異三元組，斷言 **2**（≠角色數 3、≠表格 6 格） | ✅ | 突變 M16（不去重）→ `test_smoke_runs_once_per_distinct_triple_…` 等 3 支紅 |
| 反例：某組被拒 ⇒ (i) 整體非零 (ii) 點得出哪一組 (iii) 帶出原文 | ✅ | 上方端到端輸出三項齊備；突變 M8／M9（兩條路徑各自失敗不回非零）分別紅 |
| `--apply` 收尾印一行可貼上、帶實際寫入值的 `--smoke` 指令 | ✅ | 突變 M19（拿掉那行）→ `test_apply_prints_a_pasteable_…` 紅 |
| `make check` 全綠、`unittest discover tools/model-routing` 全過 | ✅ | rc 0、`376/84/34/107`；補 GitHub remote 後 19 項自檢全綠（`mirror-recon` 實跑 ✅） |
| 驗收零供應商額度消耗（全部替身） | ✅ | 全套測試在 `PATH=/usr/bin:/bin`（兩家 CLI 皆不可見）下跑完全過；另有 `setUpModule` 把 `subprocess.run` 換成會 raise 的替身當第二層 |

## 2. 四維檢查

（本輪為複審，四維只覆蓋第 2 輪的改動面。）

- **正確性**：上一輪那個洞已補，且補在判準本身（`smoke_verdict`）而不是呼叫端，
  兩條路徑（`--smoke` 單獨／`--apply --smoke`）共用同一個判準。`None` 與 `()` 的區別由
  `smoke_silent_reject_for()` 強制（`:583-597`），且 `smoke_argv_for()` 一併要求該欄已登記
  （`:623`）——半套登記在**花掉第一毛錢之前**停下，我用突變 M2／M4 各驗過一次（§6）。無新發現。
- **規格符合度**：MYL-134 五條裁定逐條成立。第 5 條（邊界不得講得比實際大）是上一輪
  卡住的那條，本輪由「縮宣稱 ＋ 逐組強度 ＋ 強度由登記表推導」三件事一起達成——
  第三件是關鍵：宣稱與事實之間沒有第二份手抄拷貝可以漂開。
- **安全性**：無發現。codex 側維持 `--sandbox read-only`；探針提示詞無注入面；
  新增的樣態比對只讀輸出、不執行任何東西；誤判方向是安全的（誤 ❌ 而非誤 ✅）。
- **可維護性**：良好。事實一份放 `L33`、決定貼著 `PROVIDERS` 那張表，符合 MYL-135 才立下的
  判準；並**訂正了 `L31`** 那句只對 codex 成立的「失敗是響的」——不訂正的話 repo 裡會有
  兩條互相矛盾的紀錄。註解說得出「為什麼 `()` 不能寫成 `None`」，這正是下一個人會踩的地方。

## 3. 重大瑕疵清單

**無。** 第 1 輪唯一那項已修並經覆驗（見 §0b）；本輪未新增。

## 4. 次要建議

不擋結案。

1. **`L33` 的警告字樣與登記表沒有機械綁定**（突變 M20）。改掉 `known-drift.md` 裡引的那句
   `Warning: Unknown --effort value …`、讓它與 `PROVIDERS` 對不上，全套測試照樣綠。實害有限
   （`L33` 那份是給人讀的取樣說明，不是判準），而且真正會出事的形態——CLI 改版導致樣態
   對不上真實輸出——本來就沒有免費的機械擋法，程式與 `L33` 兩處都已明說。若日後覺得值得，
   `--selfcheck` 加一項「`known-drift` 引的樣態字串是 `PROVIDERS` 該欄的超字串」是可行的。
2. **`--apply --smoke --issue X` 現在貼兩則留言，跨單寫入從 1 筆變 2 筆**（`L32`，每個 run
   上限 20）。拆留言本身是對的（上一輪的建議 1），這裡只是記一筆帳：在一個要動很多張單的
   run 裡用這條路徑，記得它多吃一格。
3. **`7dc0972` 用了 `git merge` 的預設英文訊息**（`Merge remote-tracking branch 'origin/main'
   into MYL-136-smoke-flag`），不符 protocol `commit` 節的「gitmoji ＋繁體中文標題」——
   repo 裡 12 顆 merge commit 只有這一顆是這樣。**不擋結案**：改它要改寫已推送分支的歷史
   （force push ＝ `P3`，使用者專屬），代價明顯大於偏差本身；本次合併進 main 那顆由我照格式寫。
   下次併 main 進工單分支時順手帶 `-m`。

## 5. 分支收尾檢查

- **分支狀態**：已合併並刪除。
  - 合併：`--ff-only` 對齊 GitHub main（`47202a3` → `faf0af7`）後 `--no-ff` 併入，
    合併 commit ``0f37aa8``；`known-drift.md` 自動合併無衝突，四段內容逐項覆核都在。
  - 合併後 `make check`：`mirror-recon` 因上述 MYL-138 而紅（對照組同紅），
    **其餘 18 項全綠、四支 suite ``376 / 84 / 34 / 107`` 全 OK**。
  - 分支已刪（本機；未曾推到 GitHub，`git ls-remote` 確認無該 ref）。
- 本單未動 `docs/handbook/` 與 `skills/foundry-protocol/` ⇒ 不觸發第 7 節手冊發佈四步，
  亦無戳記義務（`handbook-stamp` 綠）。

## 6. 我自己下的反向突變：20 顆，19 顆被擋下

**先講一件方法上的事**：第一版突變台我用 `unittest discover -s … -t .`，20 顆全「擋下」。
細節欄全空讓我起疑，跑了**不突變的對照組**——rc 也是 1，`ImportError: Start directory is
not importable`。那 20 個綠燈是假的。改成與 `Makefile:27` 一模一樣的叫法、確認對照組
`rc=0 / Ran 84 tests / OK` 之後才重跑。**沒有先驗過對照組的突變結果一律不算數。**

以下每一顆都逐顆實跑，全程 `PATH=/usr/bin:/bin`、rc 由 `subprocess.run` 直接取（不經管線）：

| # | 突變 | 結果 |
| --- | --- | --- |
| M1 | `smoke_verdict` 拿掉樣態比對（＝回到第 1 輪） | ✅ `test_exit_zero_with_a_value_the_cli_says_it_ignored_is_not_a_green_light` |
| M2 | `smoke_silent_reject_for` 把 `None` 當成 `()` | ✅ `test_a_provider_with_no_recorded_rejection_shape_stops_before_spending` |
| M3 | `smoke_detection_note` 一律印最強那句 | ✅ `test_each_line_carries_its_own_detection_strength_…` |
| M4 | `smoke_argv_for` 不再要求樣態已登記 | ✅ 同 M2 那支（且斷言「一次額度都沒花」的那行紅） |
| M5 | `SMOKE_BOUNDARY` 改回第 1 輪那句 | ✅ `test_the_boundary_sentence_does_not_claim_one_uniform_coverage` |
| M6 | ✅ 那行不再掛偵測強度 | ✅ `test_each_line_carries_its_own_detection_strength_…` |
| M7 | 稽核留言改回擺在 smoke 之後 | ✅ `test_the_audit_comment_is_posted_before_smoke_starts_burning_minutes` 等 3 支 |
| M8 | smoke 失敗不影響 `--apply` 退出碼 | ✅ 2 支 |
| M9 | 單獨 smoke 路徑失敗不回非零 | ✅ 2 支 |
| M10 | 登記表把 claude 的樣態清成 `()` | ✅ 3 支 |
| M11 | 登記表樣態字串漂掉（對不上真實輸出） | ✅ `test_exit_zero_…`（**證明測試 fixture 與登記表是兩個獨立來源**） |
| M12 | 樣態表攤平成全域清單（會誤殺別家） | ✅ `test_the_silent_reject_shape_is_looked_up_per_provider_not_applied_globally` |
| M13 | 第一則留言不說明 smoke 還沒跑完 | ✅ `test_the_audit_comment_is_posted_before_…` |
| M14 | `tee` 只餵第二則留言（切換執行單描述漏掉 smoke 段） | ✅ `test_the_switch_issue_description_still_carries_the_whole_smoke_section` |
| M15 | smoke 變成 `--apply` 的隱含預設 | ✅ 3 支（**翻掉花錢守衛的那顆，在清空的 `PATH` 下跑**） |
| M16 | 不去重、按角色逐個打 | ✅ 3 支 |
| M17 | 逾時當成通過 | ✅ `test_timeout_and_missing_cli_are_failures_not_green_lights` |
| M18 | 邊組 argv 邊跑（未實證那家的錢先花掉才報錯） | ✅ `test_an_unproven_provider_stops_before_a_single_call_is_made` |
| M19 | 拿掉收尾那行可貼上的指令 | ✅ `test_apply_prints_a_pasteable_…` |
| M20 | `L33` 的樣態字串與登記表脫鉤（文件端漂移） | 🔵 **沒擋下**——見次要建議 1 |

M11 值得單獨講：它把登記表的樣態改成對不上真實輸出的字串，測試紅了。這證明
`CLAUDE_SILENT_DEGRADE_STDERR`（替身的**輸入**）與 `PROVIDERS`（工具的**期望**）
是兩個獨立來源——MYL-129 那種「兩側都從同一處取值、斷言恆成立」的假綠在這裡不成立。

## 7. 出範圍發現（回報 Product Manager，不夾帶進本單）

- **`mirror-recon` 目前是紅的，來源是 MYL-138**：「鏡像 issue #69 沒有掛進 project
  （讀不到 Status），來源端是 `in_progress`」。**與本單無關**——我在**不含 MYL-136 的
  `faf0af7`** 上跑同一項當對照組，一樣紅；且本單的 `make check` 在 MYL-138 出現之前是 rc 0
  （19 項全綠）。它是併行 run 的在途工作，依 MYL-103 的教訓我不代為補掛。
  ⚠️ 但它會擋住**全 workspace 的 commit**（`--selfcheck` 掛在 pre-commit 的 `always_run`）。
- **合併前 workspace 的本地 `main` 落後 GitHub main 兩顆 commit**（MYL-94 的 `R8`，
  `db1fe97`／`faf0af7`，今天由另一個 run 推上去的）。本次合併已先 `--ff-only` 對齊再合，
  未做出分岔的 main；合併後逐項確認 `R8`／`L31` 訂正／`L32`／`L33` 四段內容都在。

## Verdict

**✅ APPROVED**

上一輪唯一那項瑕疵改得比要求的更徹底：CR 開的是「補偵測**或**縮宣稱」，兩條都做了，
而且理由站得住——只補偵測，那個 ✅ 仍會被讀成和 codex 一樣強；只縮宣稱，現行 active
profile 的值域錯誤仍然抓不到。真正讓這個修法不會過期的是第三件事：**偵測強度由登記表
機械推導**，宣稱與事實之間沒有第二份手抄拷貝。

零額度做出強證據這一點也值得記：警告字樣用「非法 model ＋非法 effort」取樣、整條管線用
替身 CLI 逐字重播——兩件事分開驗、兩邊都免費，而證據強度不比花錢的那種弱。我獨立重跑了
取樣那一步，字樣與登記表相符。
