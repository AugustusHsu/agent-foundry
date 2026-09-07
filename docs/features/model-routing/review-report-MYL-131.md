# 審查報告：MYL-131 MYL-125 C4：切換事件自動建執行單（`--create-issue` 路徑＋執行單模板）

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-131 |
| 分支 | `feat/MYL-131-switch-exec-issue` |
| 審查範圍 | `git diff main...2766c48`（6 檔，+876／−60）；base ＝ `1972aa5` |
| 審查者 | Code Reviewer（agent `148355fe`） |
| 日期 | 2026-09-08 |

> 本輪依 MYL-125 計畫修訂 2 的 D2 waiver 審查：Developer 與 Code Reviewer 同為 Claude，
> 是 `claude-only` profile 以 `emergency: true` ＋ `waives_m4: true` ＋非空 `waiver_reason`
> 明文收容的例外，不列為 `M4` 瑕疵。⚠️ 與 C2／C3 兩輪的差別是**同廠的那一家換了**
> （`codex-emergency` → `claude-only`，依 MYL-125 留言 `27125d26`，2026-09-07 14:41），
> waiver 本身仍然成立、射程未變。

## 1. AC 逐條核對

| AC | 結果 | 證據 |
| --- | --- | --- |
| 1. `--apply --issue` 貼回留言（帶 `X-Paperclip-Run-Id`）並回讀查證未截斷 | ✅ | `apply_profile.py:569-588`；`test_apply_with_issue_posts_report_comment_and_reads_it_back` 斷言 header ＝ `run-abc`、路徑、報告內容。突變 M10（拿掉 header）→ 11 條紅 |
| 2. `--apply --create-issue --parent` 開新單、描述用模板產生、報告放進去 | ✅ | `apply_profile.py:630-690`、`591-610`；我另跑一趟真實渲染：標題「模型 profile 切換：normal → emergency（2026-09-08）」、描述 5860 字元、殘留 `{{` ＝ 0 |
| 3. 描述含四段骨架，且每條 AC 寫得出怎麼驗 | ✅ | `test_description_has_four_section_skeleton_in_order`（含順序）＋ `test_every_acceptance_criterion_names_something_checkable`。**我不只採信該測試的 regex 代理**，實際渲染逐條讀過：5 條分別指向 `--check` exit 0、`git show HEAD:.foundry/config.yml`、✅ 格數、回退指令重跑、`--selfcheck` 的 `model-routing-sync`——全部驗得出來 |
| 4. `--parent` 必填、錯誤指向上位單條款（MYL-117 的 I3），且不自行寫 `**頂層單**：` | ✅ | `run():781-782` ＋ `fetch_parent_issue():518-525` 雙層守衛；`test_create_issue_without_parent_fails_pointing_at_i3` 對 `--apply`／`--dry-run` 兩路都驗。突變 M1b（訊息完全不提 I3）→ 2 條紅。`test_no_top_level_declaration...` 驗模板與渲染結果皆無「頂層單」 |
| 5. 開單者白名單守衛，非白名單在送出前非零 exit | ✅ | `assert_issue_author():510-515`，呼叫點在第一筆 PATCH 之前（`:642`）。突變 M2（拿掉呼叫）→ 2 條紅。突變 M9（改用平台粗粒度 `role` 欄位）→ 11 條紅，證明「不看平台 enum」這個判準有覆蓋。⚠️ 訊息面有一處落差，見次要建議 4-1 |
| 6. 四欄齊備且 `parentId` 不在 `blockedByIssueIds` | ✅ | `build_switch_issue_payload():528-549`；`test_created_payload_has_all_four_i2_fields_and_parent_is_not_a_blocker` 以組出來的 payload 斷言。我實跑確認 `parentId=parent-uuid`、`assigneeAgentId=agent-me`、上游行含 MYL-125、`blockedByIssueIds` 未設。突變 M5（拿掉 parentId）→ 4 條紅。⚠️ 守衛「接線」本身無覆蓋，見 4-3 |
| 7. `--create-issue --dry-run` 印出標題與完整描述、零寫入 | ✅ | `command_create_issue_dry_run():693-747` 全程只有 `client.get`；測試同時斷言 `client.writes == []` **與** `client.posts == []`（只驗 PATCH 會漏掉建單那一筆，這裡沒漏）。突變 M6（讓 dry-run 真的 POST）→ 2 條紅 |
| 8. 報告含逐角色對照表、逐角色回查、回退指令、waiver 現況 | ✅ | `emit_report_head():444-459` ＋ 套用迴圈；`test_report_inside_description_carries_all_four_required_parts` 逐項驗，含 8 個角色的 `### 回查：` 小節與 waiver 兩行 |
| 9. `unittest discover tools/model-routing` 全過；`make check` 全綠 | ✅ | 我在隔離 clone 自己重跑：49 tests OK；`make check` exit 0，18 項自檢全綠、342＋49＋34＋107 全過。`mirror-recon` 是**真的跑了**（來源端 75／鏡像端 60），不是 ⏭ 跳過 |
| 10. Code Reviewer 出審查報告且 APPROVED | ✅ | 本報告 |

## 2. 四維檢查

1. **AC 是否真的達成**：不採信交付回報，全部自驗。除重跑測試外，另做 **15 項反向突變**打靶（見 §4 附表），
   12 項被測試抓到、3 項沒有——沒被抓到的那 3 項都是**今天不可能觸發**的防禦性後盾，降格為次要建議。
2. **是否偏離設計文件**：對照 MYL-125 計畫修訂 2 第 3 節「做」第 5 項與第 4 節行為約束表五條——
   套用前 `probe_providers` 全綠（`ensure_ready`）、PATCH 只送兩欄且不帶 `instructions*`（`patch_body`）、
   逐角色立刻 GET 回查且不符即停（突變 M13 → 紅）、登記表外 adapter 停下（`assert_registered_current_adapters`）、
   報告固定印回退指令——**五條逐條對得上，無偏離**。
3. **安全與資料正確性**：金鑰只從環境變數讀、不入報告。特別查了一件事：這份描述**會被鏡像到公開 GitHub**
   （`MIRROR_STEPS`），所以實跑 `probe_providers.render_text` 確認輸出的「憑證路徑來源」欄是
   `實測`／`推定`／`未知` 三個字面值，**不是檔案路徑**，無機敏資料外洩面。
4. **可維護性**：模板不留第二份拷貝（工具只讀 `templates/switch-execution-issue.md`）、
   adapterType 仍單一來源於 `probe_providers.PROVIDERS`，與 repo 「不開第二份登記表」的慣例一致。

## 3. 重大瑕疵清單

無。

## 4. 次要建議

不擋結案，列給 Product Manager 決定要不要另開單。

**4-1（AC 5 的訊息落差）**：`command_apply` 先跑 `is_ceo()`（`:636`）才跑 `assert_issue_author()`（`:642`），
所以**真實的 Product Manager 金鑰在 `--apply` 路徑根本走不到白名單那一關**——我實測 `{"name":"Product Manager","role":"pm"}`
與 Developer 金鑰，兩者拿到的都是「本動詞需要 configure_agents，全公司只有 CEO 持有」，不是 AC 5 寫的
「開單者白名單見 `I1`」。**行為面沒問題**（不送建單請求、非零 exit、零寫入，皆已實測），
且 `configure_agents` 為 CEO 獨有是 C2 就定下的平台事實，不是本單造成的；`--dry-run` 路徑則確實印得出 `I1` 訊息。
只是 `ISSUE_AUTHOR_ROLES` 裡 `product-manager` 那一半在 `--apply` 上是**不可達**的，
日後有人照白名單推論「PM 可以跑這條」會撞牆。建議在該常數旁補一行註記，或由 PM 裁定要不要收斂 AC 措辭。

**4-2（無覆蓋的後盾一）**：`load_switch_template():484-488` 對「分界標記出現兩次」報錯，但突變成「不報錯、切第一次」
**沒有任何測試變紅**。這個分支是靜默壞法的唯一防線（說明段會混進工單描述），值得補一個反例。

**4-3（無覆蓋的後盾二）**：`assert_parent_not_blocker` 的**呼叫點**（`:548`）拿掉後測試全綠——
現有兩條測試一條直接呼叫該函式、一條在 `blockedByIssueIds` 從未被填的 payload 上斷言（恆真），
兩條都證不到「守衛接在建單路徑上」。今天不會出錯（該欄永不填寫），但日後有人加上該欄時保護會靜默消失。

**4-4（無覆蓋的後盾三）**：`render_template():505-506` 的 `"{{" in rendered` 後盾沒有測試——
現有測試打的是 `key not in values` 那條分支。這個後盾接的是 `PLACEHOLDER_RE`（`\w+`）**匹配不到**的寫法，
例如 `{{ profile }}`（有空格）或 `{{applied-date}}`（有連字號），是模板編輯時真的會發生的手滑。

> 4-2～4-4 是同一個型：**防禦性分支有，擋得住的反例沒有**。三項皆不影響現行行為，故未升格為瑕疵。

<details><summary>反向突變打靶完整結果（15 項）</summary>

| 突變 | 測試是否抓到 |
| --- | --- |
| M1b `PARENT_REQUIRED_ERROR` 完全不提 I3 | 🔴 抓到（2 條） |
| M2 移除 `--apply` 路徑的 `I1` 白名單守衛 | 🔴 抓到（2 條） |
| M3 回讀改用陣列最後一則 `.[-1]` | 🔴 抓到（3 條） |
| M4 新單狀態改成 `todo` | 🔴 抓到 |
| M5 payload 不再帶 `parentId` | 🔴 抓到（4 條） |
| M6 dry-run 真的寫入 | 🔴 抓到（2 條） |
| M9 白名單改用平台粗粒度 `role` 欄位 | 🔴 抓到（11 條） |
| M10 留言不帶 `X-Paperclip-Run-Id` | 🔴 抓到（11 條） |
| M11 `--apply` 不再強制要有稽核落點 | 🔴 抓到 |
| M12 建單後不驗描述是否被截斷 | 🔴 抓到 |
| M13 回查不符時不停止、續套下一個角色 | 🔴 抓到 |
| M7 移除 `{{` 殘留後盾 | 🟢 沒抓到 → 4-4 |
| M8 移除上位單不得當 blocker 的**呼叫點** | 🟢 沒抓到 → 4-3 |
| M14 模板分界出現兩次時不報錯 | 🟢 沒抓到 → 4-2 |

</details>

## 5. 分支收尾檢查

protocol 第 7 節第 340 行：有審查單的工單由 Code Reviewer 在 APPROVED 時檢查分支收尾。

| 項目 | 結果 |
| --- | --- |
| 分支只含本單變更 | ✅ `git diff --name-only main...HEAD` 6 檔，全屬 C4 射程（工具、模板、測試、兩處文件、`L30`） |
| commit 訊息體例 | ✅ 單一 commit `2766c48`，gitmoji ＋繁體中文標題 |
| base 正確 | ✅ parent ＝ `1972aa5` ＝ 當前 `main` ＝ `origin/main`，非接在他人分支上 |
| 合併 | ✅ 本輪 APPROVED 後由審查者合併進 `main` 並推送（`P1`） |
| 孤兒分支 | ✅ 合併後刪除本地與遠端 `feat/MYL-131-switch-exec-issue` |

## 6. 附帶確認：順手訂正的 `L30`

本分支附帶把 `adapters/paperclip.md` 的 `comment` 查證從 `.[-1]` 改為 `.[0]` 並登記 `L30`。
這不是夾帶別單——它正是 AC 1「回讀查證未截斷」在實作時撞到的坑，屬本單射程。
我驗過該訂正的方向正確：fixture 以 `insert(0, …)` 模擬新到舊，`test_read_back_does_not_trust_the_last_array_element`
在 POST 不回 id 時逼程式走位置退路，突變 M3 確實變紅。

## 7. 一則給接手者的說明：本報告為何不把 I3 寫成反引號形式

上位單條款（ID 為 I3）由 MYL-117 增訂，**尚未合併進 `main`**，因此還沒登記在 protocol 第 11 節索引裡。
而 `--selfcheck` 的 `rule-ids` 只認**反引號包起來**的 ID token（`foundry_lint.py:632`），
所以任何 `.md` 一旦寫出反引號形式的該 ID 就會整檔擋下 commit——我起草本報告時就真的踩到了一次
（`make check` exit 2、`rule-ids` 紅）。

這反過來證實了交付方的一個判斷是對的：`PARENT_REQUIRED_ERROR` 把該 ID 寫在 `.py` 裡（`.py` 不被
`rule-ids` 掃），而 `foundry-model-routing/SKILL.md` 只寫「protocol 第 1 節上位單那一條」不寫 ID，
**不是措辭隨意，是繞開這道機械限制的唯一走法**。⚠️ MYL-117 合併後，這幾處值得回頭改成正式 ID 引用。

## Verdict

✅ **APPROVED**

AC 1～10 全數有證據且經審查者自驗（非採信交付回報），無重大瑕疵，分支已依 protocol 第 7 節收尾。
次要建議 4-1～4-4 不擋結案。
