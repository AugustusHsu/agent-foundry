# LLD：foundry-lint 文件檢查器

| 欄位 | 值 |
| --- | --- |
| 狀態 | 定稿 |
| 上游 HLD | docs/features/foundry-lint/HLD.md |
| 作者 | Tech Lead（agent 0c250b49） |
| 最後更新 | 2026-09-03 |

## 1. 範圍

覆蓋 HLD 第 2 節全部四個元件（CLI 入口、規則來源、章節檢查器、輸出器），即整個 foundry-lint 工具，單檔實作於 `tools/foundry-lint/foundry_lint.py`。

需求對照表（PRD 全部已確認需求 → 本文設計段落）：

| 需求 | 對應設計段落 |
| --- | --- |
| FR-1 必備章節檢查 | 第 3 節（HeadingRules／CheckResult）、第 4 節步驟 3–5 |
| FR-2 六種文件類型全支援 | 第 3 節 `TYPE_TO_TEMPLATE` 映射、第 4 節步驟 2 |
| FR-3 `--type` 明確指定 | 第 2 節 CLI 介面、第 5 節參數錯誤列 |
| FR-4 文字輸出＋exit code | 第 2 節輸出／錯誤規格、第 4 節步驟 6 |
| FR-5 `--format json` | 第 2 節 JSON 輸出規格、第 3 節 CheckResult |
| NFR-1 離線可執行 | 第 7 節（僅 stdlib、無網路呼叫） |
| PRD 第 5 節全部邊界情境 | 第 5 節逐條對應 |

## 2. 介面定義

### CLI：`foundry-lint`

```
foundry_lint.py --type <type> [--format {text,json}] [--templates-dir <path>] <file>
```

執行方式：`python3 tools/foundry-lint/foundry_lint.py ...`，或直接 `tools/foundry-lint/foundry_lint.py ...`（檔案帶 shebang `#!/usr/bin/env python3` 與執行權限）。

- **輸入**：
  | 參數 | 型別／合法值 | 必填 | 說明 |
  | --- | --- | --- | --- |
  | `--type` | `brd`／`prd`／`hld`／`lld`／`review-report`／`test-plan` | 是 | 文件類型，argparse `choices` 強制 |
  | `--format` | `text`（預設）／`json` | 否 | 輸出格式，argparse `choices` 強制 |
  | `--templates-dir` | 目錄路徑 | 否 | 模板目錄覆寫，預設見第 4 節步驟 2；主要供測試注入假模板 |
  | `<file>` | 檔案路徑（positional） | 是 | 受檢文件，一次一份 |

  argparse 設定 `prog="foundry-lint"`；`--type` 或 `--format` 值不合法、缺少必填參數時，由 argparse 原生行為輸出 usage 與合法值清單至 stderr 並以 **exit 2** 結束（不需自訂錯誤處理即滿足 FR-3 驗收 2）。

- **輸出（成功執行檢查時，stdout）**：

  `--format text`，通過：
  ```
  ✅ docs/features/foundry-lint/PRD.md 通過 prd 模板章節檢查（必備章節 6 項齊備）
  ```
  `--format text`，不通過（缺漏逐項一行，順序同模板；標題前綴 `## ` 原樣呈現以便與模板肉眼對照）：
  ```
  ❌ docs/features/foundry-lint/PRD.md 未通過 prd 模板章節檢查，缺少 2 項必備章節：
    - ## 5. 邊界情況與錯誤處理
    - ## 6. 未決事項
  ```
  `--format json`（`json.dumps(..., ensure_ascii=False, indent=2)`，欄位固定四個，此即 PRD 遺留待定案的 JSON 詳細結構）：
  ```json
  {
    "file": "docs/features/foundry-lint/PRD.md",
    "type": "prd",
    "passed": false,
    "missing_sections": [
      "## 5. 邊界情況與錯誤處理",
      "## 6. 未決事項"
    ]
  }
  ```
  `file` 為使用者輸入的路徑原文（不做 resolve）；`missing_sections` 元素格式為 `"## " + 標題文字`；通過時為 `[]` 且 `passed` 為 `true`。兩種 format 的判定與 exit code 完全一致（FR-5 驗收 2）。

- **錯誤（一律 stderr＋exit 2，stdout 不輸出任何內容）**：
  | 條件 | stderr 訊息格式 |
  | --- | --- |
  | 參數錯誤（缺 `--type`、值不合法、缺檔案參數） | argparse 原生 usage＋錯誤訊息（含合法值清單） |
  | 受檢文件不存在／不可讀 | `foundry-lint: 錯誤：無法讀取檔案：<路徑>（<OSError 原因>）` |
  | 模板檔不存在／不可讀 | `foundry-lint: 錯誤：無法讀取模板：<路徑>（<OSError 原因>）` |
  | 模板中抽不出任何二級標題 | `foundry-lint: 錯誤：模板未含任何二級標題，無法建立規則：<路徑>` |

  **執行錯誤在 `--format json` 模式下同樣輸出上述 stderr 純文字、不輸出 JSON**（此即 PRD 第 5 節遺留待定案的錯誤輸出格式）。理由：參數錯誤發生在 format 尚未確定之前，統一走 stderr 讓 stdout 保有「有 JSON ＝ 檢查有完成」的不變式；機器呼叫方以 exit code 2 辨識執行錯誤。

- **exit code**：`0`＝通過；`1`＝不通過；`2`＝執行／使用錯誤。全域僅在 `main()` 末端以 `sys.exit()` 統一回傳，禁止中途散落 exit。

## 3. 資料模型

全部為程式內型別，無持久化資料。

```python
TYPE_TO_TEMPLATE: dict[str, str] = {
    "brd": "brd.md", "prd": "prd.md", "hld": "hld.md", "lld": "lld.md",
    "review-report": "review-report.md", "test-plan": "test-plan.md",
}  # --type 合法值即此 dict 的 keys，argparse choices 直接取 TYPE_TO_TEMPLATE.keys()

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")   # ATX 標題：抽 level 與標題文字
FENCE_RE   = re.compile(r"^\s{0,3}(```|~~~)")        # 圍欄程式碼區塊開閉

# extract_headings(text: str) -> list[str]
#   回傳「二級標題的標題文字」有序清單（不含 "## " 前綴、已去除首尾空白），
#   保序、不去重（去重由呼叫端以集合處理）。

# CheckResult（dataclass）
@dataclass
class CheckResult:
    file: str                  # 使用者輸入的受檢路徑原文
    doc_type: str              # --type 值
    required: list[str]        # 模板抽出的必備標題文字，模板順序
    missing: list[str]         # 缺漏標題文字，維持 required 的順序
    @property
    def passed(self) -> bool: return not self.missing
```

比對鍵為「標題文字」（`##` 之後、去首尾空白），因此 `##  1. 概述`（多一空白）與 `## 1. 概述` 視為相同；標題文字本身逐字比對，含編號與全形標點（ADR-3）。輸出層再統一補回 `## ` 前綴。

## 4. 內部流程

`main(argv)` 依序：

1. **解析參數**（argparse，規格見第 2 節）。
2. **定位模板**：`templates_dir = args.templates_dir or (Path(__file__).resolve().parent.parent.parent / "templates")`（腳本在 `tools/foundry-lint/` 下，往上兩層即 repo 根；不依賴 cwd，在 repo 任何位置執行皆可）。`template_path = templates_dir / TYPE_TO_TEMPLATE[args.type]`。
3. **建立規則**：讀模板檔（UTF-8），`required = 去重保序(extract_headings(text))`；讀檔失敗或 `required` 為空 → 依第 2 節錯誤表輸出、exit 2。
4. **掃描受檢文件**：讀檔（UTF-8）失敗 → exit 2；成功則 `found = set(extract_headings(text))`。空檔案得空集合，自然導向「缺全部」（PRD 第 5 節空檔案列，不需特判）。
5. **比對**：`missing = [h for h in required if h not in found]`，組 `CheckResult`。
6. **輸出與收尾**：依 `--format` 呼叫 `render_text` 或 `render_json` 寫 stdout；`sys.exit(0 if result.passed else 1)`。

`extract_headings` 的圍欄處理（唯一有決策含量的內部邏輯）：逐行掃描，遇 `FENCE_RE` 匹配行則翻轉 in_fence 旗標並跳過該行；in_fence 為真時整行跳過；其餘行以 `HEADING_RE` 匹配，`len(group(1)) == 2` 才收入。已知簡化：不區分 ``` 與 ~~~ 的配對、不比對圍欄長度——對本 repo 文件足夠，已記入 HLD 第 6 節風險並由測試覆蓋常見情境。

## 5. 錯誤處理與邊界

PRD 第 5 節逐條對應（處理位置指第 4 節步驟）：

| PRD 情境 | 處理位置 | 策略 |
| --- | --- | --- |
| 檔案不存在／無法讀取 | 步驟 4，`try/except OSError` | stderr 指明路徑與原因，exit 2；不與「不通過」混淆 |
| 未提供 `--type` 或值不合法 | 步驟 1，argparse | 原生 usage 含六個合法值，exit 2，不進行檢查 |
| 受檢文件為空檔案 | 步驟 4–5，無特判 | 空集合 → 缺全部必備章節，exit 1，逐項列出 |
| 含模板以外的額外章節 | 步驟 5 | 只做 `required` 單向查找，額外章節天然不影響判定 |
| 必備章節存在但內容為空 | 步驟 5 | 只比對標題存在性，判定通過 |
| `--format json` 下發生執行錯誤 | 步驟 1–4 | 同文字模式輸出 stderr 純文字、exit 2；stdout 不輸出 JSON（第 2 節已定案） |

本文追加（PRD 未列但實作必遇）：模板檔讀不到、模板無二級標題 → 均 exit 2（第 2 節錯誤表）；受檢文件含 UTF-8 解碼錯誤 → 以 `errors="replace"` 讀入繼續檢查（標題行通常不受影響，避免整份文件因單一壞位元組報 exit 2）。

## 6. 測試切入點

測試檔：`tools/foundry-lint/test_foundry_lint.py`，**stdlib `unittest`**（不引入 pytest，維持零依賴；執行：`python3 -m unittest discover tools/foundry-lint`）。

- **單元測試（直接 import 函式）**：
  - `extract_headings`：抓二級、忽略一／三級；`##` 後多空白；行尾空白；圍欄區塊內 `## ` 行不計；`~~~` 圍欄；重複標題保序。
  - 比對邏輯：缺多項全列出且維持模板順序（FR-1 驗收 3）；額外章節不影響；空文字缺全部。
- **整合測試（`subprocess` 跑 CLI，驗 exit code 與輸出）**：
  - 以 `tempfile` 建假模板目錄＋假文件，配 `--templates-dir` 注入：通過→0、缺章節→1、檔案不存在→2、`--type` 缺／非法→2（FR-3、FR-4 驗收）。
  - `--format json`：輸出可被 `json.loads` 解析、含四欄位、判定與 exit code 與 text 模式一致（FR-5 驗收）。
- **對真實 repo 的煙霧測試**：以預設模板目錄檢查 `docs/features/foundry-lint/PRD.md`（`--type prd`）應通過；複製一份刪除 `## 5. 邊界情況與錯誤處理` 應不通過並列出該標題（FR-1 驗收 1、2；FR-2 可對六模板各造一份骨架文件迴圈驗證）。
- **需要 mock 的外部依賴**：無（純本機檔案讀取）。

## 7. 實作注意事項

- **只准 stdlib**：`argparse`、`re`、`json`、`sys`、`pathlib`、`dataclasses`、`tempfile`／`unittest`（測試）。出現任何 `pip install` 即違反 ADR-1 與 NFR-1。
- 讀檔一律 `encoding="utf-8", errors="replace"`；`\r\n` 行尾由 `HEADING_RE` 的 `\s*$` 吸收，不需另外處理。
- JSON 輸出必須 `ensure_ascii=False`（章節名是中文，`\uXXXX` 轉義會讓機器可讀但人不可讀）。
- stdout 只在檢查完成時寫入；所有錯誤訊息走 stderr——維持第 2 節的 stdout 不變式，方便呼叫方 `foundry-lint ... > result.json`。
- `sys.exit` 只出現在 `main()` 收尾與 argparse 內部；函式層以回傳值／例外溝通，方便單元測試。
- 檔案記得 `chmod +x` 並帶 shebang `#!/usr/bin/env python3`。
- 無並發、效能、執行順序陷阱（單檔單次讀取，文件尺寸為 KB 級）。
