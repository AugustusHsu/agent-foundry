# 測試計畫：foundry-lint 文件檢查器（MYL-21）

| 欄位 | 值 |
| --- | --- |
| 對應工單 | MYL-21（受測版本：MYL-19 產出、MYL-20 ✅ APPROVED 之 main commit `7bf8c6e`＋`1451c4f`） |
| 上游文件 | docs/features/foundry-lint/PRD.md、docs/features/foundry-lint/LLD.md |
| 作者 | QA Engineer（agent 14732ae9） |
| 最後更新 | 2026-09-03 |

## 1. 範圍

- **測**：FR-1（必備章節檢查）、FR-2（六種文件類型）、FR-3（`--type` 明確指定）、FR-4（文字輸出＋exit code 0/1/2）、FR-5（`--format json`）；PRD 第 5 節全部六項邊界情境（LLD 第 5 節對照表）。
- **不測**：
  - 章節「內容品質」判斷——PRD 第 1 節明定單級嚴格度，只驗章節存在性，內容品質不在工具範圍。
  - 實際斷網環境下的 NFR-1 驗證——本環境無法安全切斷網路；以「原始碼零網路相關 import」作靜態佐證（見 T-13），與 MYL-20 審查結論相互印證。
  - 圍欄不區分 ```／~~~ 配對的極端巢狀情境——LLD 第 4 節載明之已知簡化，非缺陷；常見情境由單元測試覆蓋。

## 2. 環境與前置

- 位置：agent-foundry repo 根目錄（本機，無需任何服務）。
- 環境：Python 3（僅 stdlib，無需 pip install）。
- 測試資料：
  - 真實文件：`docs/features/foundry-lint/PRD.md`。
  - 衍生假文件（刪章節副本、六類型骨架、空檔案等）：以 Python 從 `templates/*.md` 抽二級標題現場產生，放臨時目錄（本輪使用 run scratch 目錄 `$PAPERCLIP_RUN_SCRATCH_DIR/qa/`，任何可寫臨時目錄皆可重建）。
- 指令：
  - 手動案例：`python3 tools/foundry-lint/foundry_lint.py --type <type> [--format json] <file>`，以 `echo $?` 驗 exit code。
  - 自動化套件：`python3 -m unittest discover tools/foundry-lint`。

## 3. 測試項目

| 編號 | 對應 AC／FR | 測試內容 | 步驟摘要 | 預期結果 | 方式 |
| --- | --- | --- | --- | --- | --- |
| T-1 | FR-1 驗收 1；工單 AC1 前置 | 真實 PRD 通過檢查 | `--type prd docs/features/foundry-lint/PRD.md` | exit 0；stdout 為 LLD 第 2 節通過訊息（含「必備章節 6 項齊備」） | 手動＋自動化皆有 |
| T-2 | FR-1 驗收 2 | 刪單一必備章節後不通過 | 複製 PRD、刪「## 5. 邊界情況與錯誤處理」後檢查 | exit 1；輸出列出該章節名 | 手動＋自動化皆有 |
| T-3 | FR-1 驗收 3 | 缺多章節全列出且依模板順序 | 複製 PRD、刪「## 2. 功能需求」與「## 6. 未決事項」後檢查 | exit 1；兩項都列出，2 在前 6 在後 | 手動＋自動化皆有 |
| T-4 | FR-2 驗收 1、2；工單 AC3 | 六種 `--type` 各一組通過＋不通過 | 對六模板各造完整骨架與缺首章節版本，逐一檢查（12 案例） | 骨架版 exit 0；缺章節版 exit 1 並列出缺漏章節名 | 手動＋自動化皆有 |
| T-5 | FR-3 驗收 2；PRD 邊界 2 | 缺 `--type` | 不帶 `--type` 執行 | exit 2；stderr 出 usage（含六合法值）；stdout 淨空；不進行檢查 | 手動＋自動化皆有 |
| T-6 | FR-3 驗收 2；PRD 邊界 2 | `--type` 值非法 | `--type xyz` 執行 | exit 2；stderr 列出六個合法值；stdout 淨空 | 手動＋自動化皆有 |
| T-7 | FR-4 驗收 1；PRD 邊界 1 | 受檢檔案不存在 | 對不存在路徑執行 | exit 2（非 exit 1）；stderr 指明讀不到的路徑；stdout 淨空 | 手動＋自動化皆有 |
| T-8 | PRD 邊界 3 | 空檔案視同缺全部章節 | 對 0 byte 檔案執行 `--type prd` | exit 1；列出全部 6 項必備章節 | 手動＋自動化皆有 |
| T-9 | FR-1 驗收 4；PRD 邊界 4 | 額外章節不影響判定 | 骨架文件加「## 99. 模板外的額外章節」後檢查 | exit 0 通過 | 手動 |
| T-10 | FR-1 驗收 4；PRD 邊界 5 | 必備章節存在但內容為空 | 骨架文件章節下內容清空後檢查 | exit 0 通過 | 手動 |
| T-11 | FR-5 驗收 1、2 | JSON 輸出合法且判定一致 | `--format json` 跑通過與不通過案例；`json.loads` 解析 | 可解析；恰含 file／type／passed／missing_sections 四欄位；中文無 `\u` 轉義；判定與 exit code 與 text 模式一致 | 手動＋自動化皆有 |
| T-12 | PRD 邊界 6 | `--format json` 下發生執行錯誤 | `--format json` 對不存在檔案執行 | exit 2；stderr 純文字訊息與 text 模式一致；stdout 不輸出任何 JSON | 手動＋自動化皆有 |
| T-13 | NFR-1 | 離線可執行（靜態佐證） | `grep` 檢查兩支 .py 無 socket／urllib／http／requests import | 零筆網路相關 import | 手動（理由見第 1 節不測項） |
| T-14 | 工單 AC1 | 本測試計畫自檢 | `--type test-plan docs/features/foundry-lint/test-plan.md` | exit 0 | 手動 |
| T-15 | 回歸（LLD 第 6 節全部切入點） | 既有自動化套件全綠 | `python3 -m unittest discover tools/foundry-lint` | Ran 26 tests、OK、exit 0 | 自動化 |

## 4. 自動化策略

- 自動化測試已由 MYL-19 交付於 `tools/foundry-lint/test_foundry_lint.py`（stdlib `unittest`，26 測項：單元＋subprocess 整合＋真實 repo 煙霧），與功能程式碼同分支交付、經 MYL-20 審查。本計畫以 T-15 整套重跑作為回歸主幹；T-1～T-8、T-11、T-12 在該套件中皆有對應自動化測項，本輪另以 CLI 手動實測留下獨立證據（QA 不沿用 Developer 宣稱）。
- 僅手動的測項與理由：T-9／T-10（審查已確認套件涵蓋等價情境，QA 補獨立黑箱證據，成本一條指令）、T-13（斷網不可行，取靜態佐證）、T-14（受檢對象是本文件自身，屬交付驗收動作）。
- QA 本輪未新增測試程式碼：既有套件已覆蓋 LLD 第 6 節全部切入點，無缺口需補。

## 5. 回歸清單

無已修缺陷（本模組首次交付，MYL-20 審查零缺陷），故無缺陷回歸項；以整套自動化測試作變更回歸：

| 來源 | 測試項 | 理由 |
| --- | --- | --- |
| MYL-19 交付 | `python3 -m unittest discover tools/foundry-lint`（26 測項） | 受測模組本體的全部自動化測試，QA 重跑確認交付版本在本環境全綠 |

## 6. 執行結果

執行日期 2026-09-03，受測版本 main `1451c4f`，執行者 QA Engineer（agent 14732ae9）。**15 測項全數通過，無缺陷。**

| 編號 | 結果 | 證據（指令輸出摘要） |
| --- | --- | --- |
| T-1 | ✅ 通過 | exit 0；stdout `✅ docs/features/foundry-lint/PRD.md 通過 prd 模板章節檢查（必備章節 6 項齊備）`，逐字符合 LLD 第 2 節範例 |
| T-2 | ✅ 通過 | exit 1；stdout 末行 `  - ## 5. 邊界情況與錯誤處理` |
| T-3 | ✅ 通過 | exit 1；`缺少 2 項必備章節`，依序列出 `## 2. 功能需求`、`## 6. 未決事項`（模板順序） |
| T-4 | ✅ 通過 | 12 案例全符：brd（7 項）／prd（6）／hld（6）／lld（7）／review-report（6）／test-plan（6）骨架皆 exit 0；各缺首章節版本皆 exit 1 並列出該章節（如 brd 列 `- ## 1. 背景與問題`） |
| T-5 | ✅ 通過 | exit 2；stderr `usage: foundry-lint [-h] --type {brd,prd,hld,lld,review-report,test-plan} ...`＋`the following arguments are required: --type`；stdout 0 byte |
| T-6 | ✅ 通過 | exit 2；stderr `invalid choice: 'xyz' (choose from 'brd', 'prd', 'hld', 'lld', 'review-report', 'test-plan')`；stdout 0 byte |
| T-7 | ✅ 通過 | exit 2；stderr `foundry-lint: 錯誤：無法讀取檔案：<路徑>（No such file or directory）`；stdout 0 byte |
| T-8 | ✅ 通過 | exit 1；`缺少 6 項必備章節`，六項齊列（## 1.～## 6.） |
| T-9 | ✅ 通過 | 加 `## 99. 模板外的額外章節` 後仍 exit 0 |
| T-10 | ✅ 通過 | 章節內容全空仍 exit 0 |
| T-11 | ✅ 通過 | 通過案例 `{"file": ..., "type": "prd", "passed": true, "missing_sections": []}` exit 0；缺章節案例 `passed: false`、`missing_sections: ["## 5. 邊界情況與錯誤處理"]` exit 1；`json.loads` 解析成功、keys 恰為四欄位、原文含中文無 `\u` 轉義、缺漏清單與 T-2 text 模式一致 |
| T-12 | ✅ 通過 | exit 2；stdout 0 byte（無 JSON）；stderr 與 T-7 同一訊息 |
| T-13 | ✅ 通過 | `grep -nE "^(import|from) (socket|urllib|http|requests)" tools/foundry-lint/*.py` 零筆；實作僅 6 條 stdlib import |
| T-14 | ✅ 通過 | `python3 tools/foundry-lint/foundry_lint.py --type test-plan docs/features/foundry-lint/test-plan.md` → exit 0（本文件定稿後實測） |
| T-15 | ✅ 通過 | `python3 -m unittest discover tools/foundry-lint` → `Ran 26 tests in 0.652s`／`OK`／exit 0 |
