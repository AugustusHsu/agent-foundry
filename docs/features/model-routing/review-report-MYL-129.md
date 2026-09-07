# 審查報告：MYL-129 apply_profile.py 四個動詞與單元測試

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-129 |
| 分支 | `feat/MYL-129-apply-profile-d2` |
| 審查範圍 | 第 3 輪，即 **`D2` 退回重做後的那一輪**；`origin/main`（`9977e56`）`...cc51b2d`（實作 `d42a170`、合併 main `cc51b2d`） |
| 審查者 | Code Reviewer（agent `148355fe`） |
| 日期 | 2026-09-08 |

> **本輪仍在 `M4` waiver 底下審**（AC 12 要求寫明）：Developer 與 Code Reviewer 同一供應商。
> 但 waiver 的**載體已經換了**——第 2 輪那次靠的是 MYL-125 計畫修訂 2 的 `codex-emergency`；
> 本輪雙方都在 `claude_local`（實跑 `--dry-run` 可見九名目標全為 `claude_local`），
> 收容它的是 `.foundry/config.yml` 現行 active profile `claude-only` 的
> `waives_m4: true` ＋非空 `waiver_reason`（實跑 `--check` 原樣印出）。
> 兩者都是明文例外，本輪不列為 `M4` 瑕疵。
>
> 第 2 輪報告的原文保留在 commit `d21c1e6`；本檔以本輪內容為準。

## 0. 本輪定位與審查範圍的取捨

本單經 `D1` 回報 → PM 判 **`D2`** → 改寫 AC `2`／`4`／`5`、新增 `13`–`17` → 退回重做。
因此本輪**不是**單純對著上一輪瑕疵清單複審（上一輪是 APPROVED、沒有清單），
而是對「AC 集合本身改變了」的那一段重新取證：

- **改寫與新增的 8 條（`2`／`4`／`5`／`13`–`17`）逐條獨立取證**，包含我自己造的反向突變與打穿探針。
- **未改動的 9 條**沿用第 2 輪已核驗的結論，並以本輪 `make check` 全綠與 61 項測試全過覆蓋；
  其中受 `D2` 波及、語意可能被改壞的（`3`／`9`／`10`／`11`）另外單獨確認，理由見表內。

缺陷本體重述一次，作為判準基準：工具兩側都寫死 `modelReasoningEffort`，
而九名 agent 全是 `claude_local`（消費 `effort`）⇒ 宣告值從未生效，
而回查讀的是自己剛寫進去的那個鍵，所以回查照樣「相符」。
**本輪要驗的核心不是「鍵名改對了」，是「鍵名再錯一次會不會被擋下」。**

## 1. AC 逐條核對

（「證據」一律是我自己在隔離 clone `cc51b2d` 上跑出來的；Developer 交付回報裡的宣稱不計入。）

| AC | 結果 | 證據 |
| --- | --- | --- |
| 1. `--list` 印 profile／active／waiver | ✅ | 沿用第 2 輪；`apply_profile.py:410-420` 三分支未動，`test_list_includes_active_and_waiver` 通過 |
| 2. 🔁 `--check` 三態＋兩個時點 | ✅ | **三態**：`test_three_states_have_three_distinguishable_exit_codes` 走完整 `main()` 驗 0／1／3。**真實平台**：以 Code Reviewer 金鑰實跑 `--check` → **exit 3**、印成因與替代路徑、**沒有**輸出逐格差異表。**兩個時點**：`test_check_covers_both_time_points_before_and_after_apply` 先驗套用前報不符、套用後轉綠，且綠是靠替身自己那張消費端表核對出來的 |
| 3. `--dry-run` 零寫入 | ✅ | `test_dry_run_never_writes` 斷言 `writes == []`；真實金鑰實跑 `--profile claude-only --dry-run` exit 0、印 8 筆 PATCH、零寫入 |
| 4. 🔁 逐角色回查、不符即停、**回查讀消費端的鍵** | ✅ | `:775-785` 回查走 `differs()` → `effort_key_for()`。中斷語意：`test_second_verification_failure_stops_before_third_patch`。**保護力不是零**由我自己重驗：只突變寫入端（`patch_body` 把鍵改名）時套件紅；只突變讀取端（`differs` 的 `live_key`）時 61 項紅 7 錯 16 |
| 5. 🔁 body 只含兩欄、effort 鍵由 adapterType 決定、無 `instructions*`、不用 `replaceAdapterConfig` | ✅ | `:292-299`；`test_patch_body_is_limited_and_has_no_instructions_key` 同時涵蓋 `codex_local`／`claude_local` 兩個鍵名，並斷言 `replaceAdapterConfig` 不出現。真實 `--dry-run` 的 body 是 `{"adapterConfig": {"effort": ..., "model": ...}, "adapterType": "claude_local"}`——**`effort` 這個鍵就是缺陷已修的直接證據** |
| 6. 供應商不可用依 `M5` 拒絕 | ✅ | `ensure_ready` 未動；`test_unavailable_provider_refuses_apply` 通過 |
| 7. 登記表外的 adapter 停下不試寫 | ✅ | `:340-352` 未動；另新增 `test_effort_key_refuses_to_guess_for_unverified_adapters`，且該測試先斷言「登記表裡真的還有 `effort_key` 為 `None` 的列」再打反例，反例不空轉 |
| 8. `--apply` 固定印回退指令 | ✅ | `:768-773`，仍在第一筆 PATCH 之前；相關測試通過 |
| 9. 沿用單一登記表、工具內無第二份對照 | ✅ | `grep -n 'modelReasoningEffort\|["'"'"']effort["'"'"']' apply_profile.py` **零命中字串常值**，只命中 `effort_key_for`／`effort_value` 這些識別字。且這條已被機械化（見 AC 13） |
| 10. 非 CEO 乾淨失敗 | ✅ | `:751-753` 的身分檢查在 AC 14 預檢**之前**——順序重要，否則 PM／Dev 金鑰會先撞到「讀不到」而不是「你不是 CEO」。`test_non_ceo_fails_before_first_patch` 通過 |
| 11. 測試全過且零真實寫入 | ✅ | `python3 -m unittest discover tools/model-routing` → **61 tests, OK**；全部走 `FakeClient`／fixture。我自己的真實平台操作只有 `--check` 與 `--dry-run` 兩條唯讀路徑 |
| 12. `make check` 全綠＋APPROVED＋寫明 waiver 與輪次 | ✅ | 隔離 clone 跑 `make check` 全綠（18 項自檢＋342／61／34／107 tests 全過）；waiver 與「本輪是 `D2` 退回重做後那一輪」寫在本報告表頭與 §0 |
| 13. 🆕 effort 鍵名依 adapterType 取，只有一個取鍵函式 | ✅ | `effort_key_for()`（`:208-232`）是唯一來源，組 body（`:297`）／`--check` 比對（`:368-379`）／`--apply` 回查（同一條 `differs`）三處共用。**守衛自己也打穿過**：我在檔內種一份字面 `{"claude_local": "effort"}` 拷貝，套件恰好紅 1 項且就是 `test_effort_key_has_exactly_one_source_and_no_literal_second_copy` |
| 14. 🆕 `--apply` 回查能力預檢 | ✅ | `:351-354` 掛在第一筆 PATCH 前那趟 GET 上。`test_apply_precheck_stops_before_the_first_patch_when_readback_is_impossible` 把被遮蔽的角色放在**最後一名**（`qa-engineer`），所以它證明的是整個迴圈跑完才可能寫入，不是「剛好第一名就擋下」；斷言 `writes == []`、`posts == []` |
| 15. 🆕 替身有「消費端」概念、兩種 PATCH 語意 | ✅（有一處未照字面，見 §6-1） | `FakeClient.patch` 換型走取代、同型走合併；`consumed_effort()` 走測試自己的 `CONSUMED_EFFORT_KEY`。**我對照在跑的 build 覆核了語意**：`@paperclipai/server 2026.831.1` 的 `dist/routes/agents.js:3209`（同型合併）／`:3212-3222`（換型取代＋保留 `ADAPTER_AGNOSTIC_KEYS`），而 `@paperclipai/shared/dist/constants.js:64-73` 那張表**不含任何 effort 鍵** ⇒「換型時 effort 鍵消失」成立；`applyCreateDefaultsByAdapterType`（`:1553-1578`）對 `claude_local` **沒有** effort 分支、不回填，Developer 這項宣稱也成立 |
| 16. 🆕 反向突變自證 | ✅ | 我自己跑，不採信報告數字：登記表 effort 鍵全換假名 ⇒ **61 項紅 18 項**；精確重現原缺陷（`claude_local` 的鍵改回 `modelReasoningEffort`）⇒ **紅 16 項**。三格路徑各有測試：同型 `claude-only`、`claude→codex→claude` 往返、`--check` 對「鍵整個不存在」報不符。對照組是這個缺陷當初躲過的那 12 項測試（第 2 輪，紅 2 項） |
| 17. 🆕 `update_active_config` 的 no-op 不是失敗 | ✅ | `:476-495` 改判 `re.subn` 的 `replaced` 計數；`test_applying_the_already_active_profile_is_idempotent_not_an_error` 連跑兩次都 exit 0。反例不空轉：`test_update_active_config_still_refuses_a_config_without_the_active_line` 證明真的漏了 `active:` 那行仍然擋得住 |

## 2. 四維檢查

- **正確性**：三態的 exit code 分得開（0／1／3），`2` 讓給 argparse 是對的。順序面三處都對：身分檢查 → 回查能力預檢 → 第一筆 PATCH；`update_active_config` 在全部回查通過之後。`differs()` 對「換型時現況鍵與目標鍵不同源」的處理是這次改動裡最容易寫錯的一格，實作選了「宣告值掛目標鍵、實況值讀現況 adapter 真正消費的鍵」，方向正確——反過來寫會把現況的舊 effort 讀成 `None`，看起來像沒設定。**無重大瑕疵**。
- **規格符合度**：與 MYL-125 計畫修訂 2 §4、`L4`／`L5`／`L25` 一致。AC 15 最後一句未照字面實作，但那一句與 AC 16 互斥、照字面做會讓 AC 16 不可能成立——這是 AC 文字問題不是實作問題，依 protocol 第 5 節「AC 寫錯由 PM 改」移交 §6，不列瑕疵。
- **安全性**：全程零真實寫入（我自己只跑唯讀的 `--check`／`--dry-run`）。PATCH body 仍是明確 allowlist；不用 `replaceAdapterConfig` 的判斷有原始碼依據（`dist/routes/agents.js:3204-3206` 確實在該旗標下才走 `assertCanManageInstructionsPath`）。讀不到設定時 fail-closed，且**不**把遮蔽值渲染成差異表——這是防「整片假警報導致有人去『修』一個沒壞的東西」。
- **可維護性**：鍵名的權威收斂到 `PROVIDERS.effort_key` 一處，且「不准有第二處」由測試機械擋住，不必靠人記得。註解密度偏高但都在解釋「為什麼這樣寫」而非複述程式碼，與本 repo 慣例一致。

## 3. 重大瑕疵清單

無。

## 4. 次要建議

不擋結案，Developer 可自行決定是否採納；若要動，建議併進後續 C5（MYL-132）實跑那一輪，不為此單獨開單。

1. **差異表 effort 那一列的欄名與值可能不同源**（`apply_profile.py:368-379`）。欄名固定用 `declared_key`，但換型時值取自 `live_key`。只在 `adapterType` 那一列同時報不符時才會出現，判定不受影響，但讀差異表的人可能以為現況真的有那個鍵。建議欄名帶上兩個鍵。
2. **`UNVERIFIABLE_GUIDANCE` 的成因句比實況窄**（`:74-84`）。在跑的 build 是**階梯式**：先查 `agents:configure`，不通過再查 `agents:suggest-changes`（`@paperclipai/server/dist/services/authorization.js:1030-1052`）。本公司九名都沒有第二條 grant（`.foundry/org.yml` 的 `permissions` 只出現 `assign_tasks`／`configure_agents`／`create_skills`），所以這句話**現況為真**；但誰拿到 `agents:suggest-changes` 之後它就會誤導。
3. **替身的 `PRESERVED_ON_TYPE_CHANGE` 比平台窄，且註解引錯了樹**（`test_apply_profile.py:36-38`）。實際保留的是 `ADAPTER_AGNOSTIC_KEYS`（`env`／`promptTemplate`／`instructionsFilePath`／`cwd`／`timeoutSec`／`graceSec`／`bootstrapPromptTemplate`／`paperclipSkillSync`）＋instructions bundle。**不影響本輪結論**（那張表不含 effort 鍵）。另：註解引的 `agents.ts:1893/1896/1900` 是 `code/Python/paperclip` 那棵樹的行號，**不是在跑的** `@paperclipai/server 2026.831.1`；引用時建議標明版本或改引 `dist/` 路徑，否則下一個人核對會對不上行號而誤判宣稱有假。
4. **反向突變的數字我沒能重現**。Developer 報「61 項紅 29 項」，我用兩種配方（改登記表值、改 `effort_key_for` 回傳）各自重跑**都是 18 項**；精確重現原缺陷那一種是 16 項。判準是「套件必須紅」，兩邊都滿足、**結論不變**，所以不列瑕疵。但證據裡的數字沒附可重跑的配方時，複審只能自己另跑一份、對不了帳——建議往後報突變結果時附上突變指令本身。

## 5. 分支收尾檢查

- **分支狀態：已合併並刪除遠端分支。** `cc51b2d` 以 `--no-ff` 併入 `main`（`origin/main` 先前為 `9977e56`，是 `cc51b2d` 的祖先，無衝突），本報告隨後 commit 在 `main` 上；`feat/MYL-129-apply-profile-d2` 與第一版的 `feat/MYL-129-apply-profile`（早已隨 `1972aa5` 進 main）皆已刪除遠端分支。
- `git diff --name-only origin/main...cc51b2d` 只有 5 個檔案，全屬本單：`apply_profile.py`／`test_apply_profile.py`／`probe_providers.py`／`test_probe_providers.py`／`templates/switch-execution-issue.md`（最後一項是 AC 13 的下游——切換執行單模板原本把 `modelReasoningEffort` 寫死在 AC 3 裡，不改就會留下第二份錯的契約）。**沒有夾帶別單的變更。**
- 兩顆 commit 皆為 gitmoji ＋繁體中文標題；`d42a170` 是實作、`cc51b2d` 是合併 main，沒有 rebase／改寫歷史。

## 6. 移交 Product Manager（AC 文字更正，不影響本輪 Verdict）

兩項都是 **AC 原文與已查證的實況不一致**，依 protocol 第 5 節「只有 Product Manager 有權修改工單的 AC」移交；
**都不需要 Developer 重做**，程式現況是對的。

1. **AC 15 最後一句與 AC 16 互斥。** AC 15 寫「所有斷言一律走 AC 13 的取鍵函式，不得字面寫死鍵名」，
   但斷言若從被測程式取期望值，突變時兩側一起動、斷言恆成立——那正是這個缺陷躲過 12 項測試的機制，
   也會讓 AC 16「突變後套件必須紅」不可能成立。Developer 改用測試自有的 `CONSUMED_EFFORT_KEY`
   （來源是 adapter 原始碼，與工具無關），滿足 AC 15 第一句與 (a)(b) 兩點的目的。
   **建議把最後一句改成**：斷言的期望值不得取自被測程式；鍵名的期望值來源必須與 `apply_profile` 無關。
2. **AC 2／AC 14 括號裡的背景寫錯了權限鍵。** 現文寫閘門查 `agents:create`、且「CEO 也沒有」。
   我在**在跑的** build 上覆核：閘門是 `agent_config:read`，其 grant 階梯先查
   **`agents:configure`**、再查 `agents:suggest-changes`（`@paperclipai/server/dist/services/authorization.js:1030-1052`，
   由 `dist/routes/agents.js:1086` 的 `assertCanReadConfigurations` 呼叫）。CEO 持有 `agents:configure`
   ⇒ **CEO 讀得到、`--apply` 的回查在 CEO 金鑰下成立**，與 AC 14 括號裡「完整的 `--apply` 目前只有
   board／使用者金鑰跑得完」的結論相反。這一條會直接影響 C5（MYL-132）由誰執行，建議一併更正。
   （程式本身**沒有**依賴權限鍵判斷——判準是回傳的 `adapterConfig` 是不是空 dict，這個設計是對的，不必動。）

## Verdict

**✅ APPROVED**
