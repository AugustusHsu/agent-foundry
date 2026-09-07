# 審查報告：MYL-129 apply_profile.py 四個動詞與單元測試

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-129 |
| 分支 | `feat/MYL-129-apply-profile` |
| 審查範圍 | 第 2 輪複審；增量 `b8ed70a..e083950`，全分支 `origin/main...e083950` |
| 審查者 | Code Reviewer（agent `148355fe`） |
| 日期 | 2026-09-07 |

> 本輪依 MYL-125 計畫修訂 2 的 D2 waiver 審查：Developer 與 Code Reviewer 同為 Codex，
> 是 `codex-emergency` profile 以 `waives_m4: true` 及非空 `waiver_reason` 明文收容的例外，
> 不列為 `M4` 瑕疵。

## 0. 複審結論

上一輪四項重大瑕疵均已修復，本輪沒有新增重大瑕疵：

| 上輪瑕疵 | 結果 | 本輪證據 |
| --- | --- | --- |
| 缺 `--issue` 與完整 Markdown 執行報告 | ✅ | `apply_profile.py:353-363,382-414`；公開介面測試驗到盤點、active 前後、逐角色前後值、逐格回查、M6 依據與回退指令 |
| 中途失敗沒有回退指令 | ✅ | 回退指令在第一筆 PATCH 前印出（`:348-363`）；第 2 名回查失敗測試確認指令仍存在、active 未更新、第 3 名零呼叫 |
| `--check` 未顯示 active waiver | ✅ | `:239-245`；一致與不一致兩路測試都驗到 waiver 及理由 |
| 權限遮蔽被誤報為平台漂移 | ✅ | `:203-209,251-255`；實際以 Code Reviewer 憑證執行時 exit 1、明示「權限遮蔽」，且沒有輸出假差異表 |

## 1. AC 逐條核對

| AC | 結果 | 證據 |
| --- | --- | --- |
| 1. `--list` 列出 profiles、active 與 waiver | ✅ | 實跑 exit 0，列出 `codex-emergency`／`normal-mixed`、active、`waives_m4` 與完整 `waiver_reason`；`:226-236` |
| 2. `--check` 一致為 0；不一致逐格且非 0 | ✅ | fixture 的一致／逐格差異兩路均通過；真實 Reviewer 憑證遇遮蔽時乾淨拒絕，不把未知值冒充實況；`:239-263` |
| 3. `--dry-run` 列 PATCH 且零寫入 | ✅ | 真實只讀實跑 exit 0、列 8 筆 PATCH；`test_dry_run_never_writes` 明確斷言 `writes == []`；`:266-276` |
| 4. 每角色 PATCH 後立刻 GET；不符即停 | ✅ | `:365-375`；`test_second_verification_failure_stops_before_third_patch` 證明第 2 名失敗時只有 2 次寫入、第 3 名未被呼叫、active 不變 |
| 5. PATCH body 僅限定欄位 | ✅ | `:144-152` 與限定 key 測試；top-level 只有 `adapterType`／`adapterConfig`，內層只有 `model`／`modelReasoningEffort`，沒有 `instructions*` |
| 6. 供應商不可用依 M5 拒絕 | ✅ | `:283-289`；fixture 驗到 M5 指引、非零路徑與零寫入 |
| 7. 未登記 adapter 需人工確認並停下 | ✅ | 全部角色在首筆 PATCH 前預檢（`:171-187,345-346`）；fixture 驗到「需人工確認」且零寫入 |
| 8. `--apply` 固定提供完整回退指令 | ✅ | `:348-363` 在任何 PATCH 前輸出含原 active 與 `--issue` 的完整指令；成功與第 2 名失敗兩路皆有測試 |
| 9. adapterType 對照沿用單一登記表 | ✅ | `rg 'adapter_type\|claude_local\|codex_local' apply_profile.py` 僅命中 `PROVIDERS` 的兩個取值點（`:136,173`），工具內沒有第二份 adapter 對照 |
| 10. 非 CEO 在首筆 PATCH 前拒絕 | ✅ | 身分檢查位於 targets／probe／agent 預檢及 PATCH 之前（`:338-340`）；fixture 斷言零寫入且訊息逐字符合 AC |
| 11. model-routing tests 全過且不做真實寫入 | ✅ | `python3 -m unittest discover tools/model-routing`：27 tests，OK；其中 apply_profile 12 tests 全用 fake HTTP／fixture |
| 12. `make check` 全綠且 Reviewer APPROVED | ✅ | 隔離 clone 自跑 `make check` exit 0：17 項 selfcheck、305＋27＋34＋107 tests 全部通過；本報告即 APPROVED 證據 |

## 2. 四維檢查

- **正確性**：上一輪四個錯誤路徑均有回歸測試；PATCH／GET 順序、短路停止、active 最後才更新均符合規格。
- **規格符合度**：與 MYL-125 計畫修訂 2 §4、`foundry-model-routing` §2.3／§2.4、known-drift `L4`／`L5`／`L25` 一致。
- **安全性**：測試未發出真實平台寫入；PATCH body 採明確 allowlist；非 CEO 與未知 adapter 均在首筆寫入前失敗；權限遮蔽採 fail-closed。
- **可維護性**：adapterType 只依賴 `probe_providers.PROVIDERS`；HTTP 層可注入 fake；報告、waiver 與逐格比對各自封裝，無阻擋級重複邏輯。

## 3. 重大瑕疵清單

無。

## 4. 次要建議

無。

## 5. 分支收尾檢查

- 分支狀態：本報告 commit 後依 protocol 第 7 節在 APPROVED 之後合併；來源工單只在合併、推送與鏡像結案同步完成後轉 `done`。
- `git diff --name-only main...e083950` 只有工具本體與測試；兩顆 Developer commit 皆為 gitmoji＋繁體中文標題，且只含本單變更。
- 遠端送審 tip 為 `e083950`；`b8ed70a` 仍為祖先，沒有 rebase／改寫；與最新 `origin/main` 的 `git merge-tree --write-tree` 無衝突。

## Verdict

**✅ APPROVED**
