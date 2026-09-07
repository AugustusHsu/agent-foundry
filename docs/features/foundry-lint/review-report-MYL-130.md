# 審查報告：MYL-130 MYL-125 C3：`--selfcheck` 新增 `model-routing-sync` ＋四個擋得住的反例

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-130 |
| 分支 | `feat/MYL-130-model-routing-selfcheck` |
| 審查範圍 | 第 1 輪 `d3ec5d7...70a8044`（1 顆 commit、8 檔、+569/-10）；第 2 輪 `70a8044..0452e2d`（1 顆 commit、2 檔、+39/-1） |
| 審查者 | Code Reviewer（`148355fe`） |
| 日期 | 2026-09-08 |
| 輪次 | 第 2 輪（複審） |

第 1 輪退回**一項重大瑕疵**（`active` 是 `audit_model_routing` 唯一沒有 `isinstance` 守衛的欄位，
讀到巢狀寫法時整份 `--selfcheck` 以 traceback 中止、後六項自檢完全不跑）＋五項次要建議。
本輪依角色規範**對著上一輪的瑕疵清單逐項驗，不重新全面審查**；新發現另立第 4 節第 6 項標明。

**供應商實況（AC8 的更正，兩輪一致）**：Developer（`023c9a75`）與 Code Reviewer（`148355fe`）的
`adapterType` 實查**皆為 `claude_local`**——兩邊同為 Claude，不是單描述原文寫的 Codex。
同廠由 active profile `claude-only` 的 `emergency` ＋ `waives_m4` ＋ `waiver_reason` 三欄明文收容。
單描述提到的「計畫 D2 waiver」在事實上換成了另一個 profile 的同一種收容方式，結論不變。

## 0. 機械層（角色規範第 1 層，過了才進第 3 層）

三條都在隔離 clone `.myl130-isolated` 跑；該 clone 的 `origin/main` = `d3ec5d7`，與主 workspace 的
`main`／`origin/main` 同 sha，**不是比遠端舊的假綠**。

| 指令 | 結果 |
| --- | --- |
| `make check` | 全綠。`--selfcheck` 18 項＝17 ✅ ＋ `mirror-recon` ⏭；測試 342 / 15 / 34 / 107 全 OK |
| `git diff --name-only origin/main...HEAD` | 8 檔，與第 1 輪相同，**未夾帶別單檔案**；本輪新增的兩顆之外沒有第三處改動 |
| `git log --oneline origin/main..HEAD` | 2 顆（`70a8044`、`0452e2d`），皆 gitmoji ＋繁體中文標題，合 protocol 第 7 節 |
| `git diff --stat 70a8044..0452e2d` | 2 檔、+39/-1——與交接回報一致，**五項次要建議一項都沒夾帶** |

⚠️ `mirror-recon` 的 ⏭ **不是綠燈**：隔離 clone 的 remote 指向本機路徑，`gh` 讀不到鏡像端。
與本 diff 無關，結案時另行核對鏡像（見第 5 節）。

## 1. AC 逐條核對

第 1 輪已逐條驗過並全部有證據（AC1～AC7 ✅、AC8 待報告）。本輪不重跑那八條，
但其中七條在本輪自己跑的 `make check` 裡再次被完整覆蓋一次：

| AC | 本輪覆蓋方式 | 結果 |
| --- | --- | --- |
| 1. `model-routing-sync` 進 `SELFCHECKS`、`selfcheck-names`／`entry-sync` 綠 | 本輪 `--selfcheck` 輸出第 12 行 `✅ [model-routing-sync]`，同次 `✅ [selfcheck-names]（18 項 × 4 處）`、`✅ [entry-sync]` | ✅ |
| 2. 四種反例各有測試、各自擋得住 | 342 tests OK（含四支反例）；本輪另加一輪突變證，見第 2 節 | ✅ |
| 3. 反例不空轉：各配反向案例 | 同上；本輪新增的反例也照這個體例配了反向案例 | ✅ |
| 4. `waives_m4` 三條相依規則各自擋得住 | 342 tests OK；第 1 輪的突變證 M2／M3 已證這兩道守衛不空轉 | ✅ |
| 5. 只驗 repo 內自洽、不連平台 | 本輪 diff 未觸及該界線；`test_摘要寫明本項不含平台對帳` 仍在且綠 | ✅ |
| 6. 本 repo 現況（`claude-only` ＋ waiver）為綠 | 本輪對真實 repo 跑 `--selfcheck`，該項 ✅（active `claude-only`、3 個 profile、7 家供應商） | ✅ |
| 7. unittest 全過、`make check` 全綠 | 本輪自跑：342 / 15 / 34 / 107 OK | ✅ |
| 8. 審查報告且 verdict APPROVED | 本報告 | ✅ |

## 2. 四維檢查

複審只看修正本身與它引進的面。

- **正確性**：第 1 輪的重大瑕疵 #1 **已修，且三種方式各自驗過**（見第 3 節的複驗表）。
  修正沒有引進新的錯誤行為：`parse_config` 對任一鍵的值域只有 `str` 與 `dict` 兩種
  （純量／區塊純量走 `str`，`鍵:` 開巢狀走 `dict`，陣列不支援而被忽略），
  所以 `isinstance(active, dict)` 這一道**涵蓋了整個非字串值域**，不存在第三種漏網型別。
  唯一的落差是訊息措辭在 `active:` 留空時會說「是一個區塊」——判次要，見第 4 節第 6 項。
- **規格符合度**：`config-schema.md:118` 寫明 `model_routing.active` 的型別是**字串**、
  「須是 `profiles` 的鍵之一」。新訊息「值只能是單一 profile 的鍵（`active: normal-mixed`），
  不是一份 profile 的內容」與該行一致，沒有新增或收緊 schema 沒說的東西。未偏離。
- **安全性**：無發現。本輪 diff 不新增任何輸入來源，只是把一條既有路徑上的例外轉成 failure，
  方向是 fail-closed（原本崩掉會讓後面六項閘門一起不跑，屬 fail-open 的實質效果）。
- **可維護性**：無發現。守衛擺在成員判定**之前**、體例與同函式其餘六處
  （`:3144`／`:3165` 後的 `profiles`、`:3200` 的 `default_provider`、`:3210`／`:3219` 的 `roles`、
  `:3234` 的 `waiver_reason`）一致；註解寫明「為什麼要擺在成員判定之前」，
  下一個動這段的人不會把它移到 `elif` 之後而靜靜復原這個 bug。

## 3. 重大瑕疵清單

**本輪無新的重大瑕疵。** 第 1 輪那一項的複驗如下——第 1 輪固定的驗收條件有三條，逐條驗：

| 第 1 輪固定的驗收條件 | 結果 | 證據（本輪自己跑的） |
| --- | --- | --- |
| `active` 非字串時 append 一條可讀 failure，**不得拋例外** | ✅ | 端到端探針 A（見下） |
| 補反例測試，且**移除守衛後轉紅**（不空轉） | ✅ | 突變證 B（見下） |
| `make check` 維持全綠 | ✅ | 第 0 節 |

**端到端探針 A（本輪自建，在 `$PAPERCLIP_RUN_SCRATCH_DIR` 的副本上做，未動分支）**——
把 `.foundry/config.yml` 的 `  active: claude-only` 換成 `  active:` 換行後 `    claude-only: true`，
跑真的那支 CLI：

```
✅ [entry-sync] … ✅ [org-sync]（前 11 項全過）
❌ [model-routing-sync] 模型路由宣告自洽（不含平台對帳）（active `{'claude-only': 'true'}`、3 個 profile、7 家登記供應商…）
  - .foundry/config.yml 的 `model_routing.active` 是一個區塊——它要填的是「目前生效的是哪一個 profile」，
    值只能是單一 profile 的鍵（`active: normal-mixed`），不是一份 profile 的內容
✅ [handbook-stamp] … ✅ [pm-issue-fields]（後六項照常跑完）
foundry-lint --selfcheck：1 項未通過，1 項跳過未檢查   ← exit 1
```

**18 項一項不少全部跑完**，排在後面的 `handbook-stamp`、`init-copy-list`、`selfcheck-names`、
`mirror-recon`、`issue-authors`、`pm-issue-fields` 六項都有輸出——這正是第 1 輪那條瑕疵的殺傷面，
現在關上了。副本上的設定檔驗完即還原，`diff` 對原檔為空。

**突變證 B（本輪自建）**：把守衛整段拿掉、退回 `if not active:` 的原形，重跑：

| 突變 | 結果 |
| --- | --- |
| 移除 `isinstance(active, dict)` 守衛 → 整份測試 | `ERROR: test_a_active_寫成區塊時回一條可讀_failure_而不是拋例外`（`TypeError: unhashable type: 'dict'`）＋ `FAIL: test_可攜那半套在目標專案全綠`——**同一個原因造成的兩個紅** |
| 同上 → 端到端 CLI | 回到 `TypeError` at `foundry_lint.py:3155`，traceback 中止 |
| 還原守衛 | 342 OK |

交接回報寫的是「恰好 1 個 error」，實測是 **1 error ＋ 1 failure**。這不是報告錯誤方向的問題——
第二個紅來自 `PortableSuiteInTargetProjectTest`，也就是**這個反例同時進了可攜的那半套**，
在目標專案的 fixture 上也跑得到。證據比回報宣稱的更強一格，數字差異在此記明。

## 4. 次要建議

不擋結案。第 1 輪五項的處置逐項記錄，第 6 項是本輪新發現。

1. **（第 1 輪第 1 項，未採納）** 摘要行在 `active` 非字串時會把 dict 的 repr 直接印進去
   （本輪實測印出 ``active `{'claude-only': 'true'}``）。
   Developer 選擇不夾帶，**這個取捨是對的**：它不影響可讀性下限（失敗訊息那一行已經說清楚該填什麼），
   而複審輪次裡混入非必要改動會擴大複審面。維持現狀。
2. **（第 1 輪第 2 項，屬新需求）** `run_selfcheck`（`:3612`）是 `[check(root) for check in SELFCHECKS]`，
   任一檢查拋非 `LintError` 例外仍會讓整份自檢中止。本單的守衛只堵住**這一個**入口，
   結構性的逐項例外隔離沒做。Developer 已依缺陷收容判準不塞進本單、回報 Product Manager，做法正確。
3. **（第 1 輪第 3 項，屬新需求）** `review_provider_distinct: false` 是比 `waives_m4` 更寬鬆的
   `M4` 出口（一個布林就繞過，不需 `emergency`、不需寫改回條件）。實作照 schema 寫是對的，
   收不收斂歸 Product Manager。
4. **（第 1 輪第 4 項）** profile 名「全段唯一」在 `parse_config` 的 dict 語意下無從驗起。價值低，記著即可。
5. **（第 1 輪第 5 項）** 反例的反向案例有三個實質等同「起點是綠的」。不算缺陷，加註解即可。
6. **（本輪新發現）** `foundry_lint.py:3150` 的守衛把「`active:` 留空」也歸進「是一個區塊」。
   `parse_config` 對 `鍵:` 後面沒有值也沒有子鍵的情形回**空 dict**，於是本輪實測
   （同一支 CLI，把 `  active: claude-only` 換成單獨一行 `  active:`）拿到的是
   「`model_routing.active` 是一個區塊」那一條，摘要欄印 ``active `{}```——**語意上那是「缺席」**，
   而修正前那條路徑走的正是 `elif not active:` 的「缺席」訊息。擋是照樣擋下、
   訊息中段「它要填的是『目前生效的是哪一個 profile』，值只能是單一 profile 的鍵」
   仍給得出可行動的指示，所以**不升格成瑕疵**；要修只是把第 3150 行改成
   `if isinstance(active, dict) and active:`，讓空的那格落回原本的「缺席」分支。
   留給下一個動這段的人順手處理。

## 5. 分支收尾檢查

APPROVED 的前置條件，本輪逐項執行（protocol 第 7 節）：

| 項目 | 結果 |
| --- | --- |
| 一單一分支、分支名帶工單編號 | ✅ `feat/MYL-130-model-routing-selfcheck` |
| 分支上只有本單變更 | ✅ 8 檔，見第 0 節 |
| commit 訊息格式 | ✅ 兩顆皆 gitmoji ＋繁體中文標題 |
| 合併回 main 在 APPROVED 之後 | ✅ 本報告 commit 後才合併，順序與 MYL-116／MYL-128 一致 |
| 不留孤兒分支 | ✅ 合併後刪除本機與遠端分支（刪已合併的遠端分支屬 `P1`） |
| 手冊同步義務 | 不適用——本單未動 `docs/handbook/`，亦未動 protocol，`handbook-stamp` 綠 |

**不屬本單、但要記在明處的一件事**：MYL-129（C2）的 commit 至今**沒有併進 main**，
`apply_profile.py` 在 main 上不存在。本單刻意把基底放 main、沒把那兩顆帶進來（那是別張單的合併決定），
所以本單合併後 main 上仍然沒有 `apply_profile.py`。這會擋住 C4（MYL-131）——那張單要在
`apply_profile.py` 上加 `--create-issue`。已由 Developer 於上一輪回報 Product Manager，此處重申。

## Verdict

**✅ APPROVED**

第 1 輪唯一的重大瑕疵已修，三條固定驗收條件逐條有本輪自跑的證據：端到端 18 項全部跑完、
突變證證明新反例綁得住那一道守衛、`make check` 全綠。八條 AC 全數有證據，
四維無新的重大瑕疵，分支依 protocol 第 7 節收尾完成。

**下一步**：合併進 main、刪分支、同步鏡像後結案。第 4 節第 2、3 兩項屬新需求，
歸 Product Manager 決定是否另開單；第 6 項是本輪新發現的次要瑕疵，不擋結案。
