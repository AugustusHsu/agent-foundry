# 審查報告：MYL-85 補一項 `--selfcheck`：驗設定欄位名與 schema 版本

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-85（審查單 MYL-111） |
| 分支 | `feat/MYL-85-config-schema-selfcheck` |
| 審查範圍 | 第 4 輪，tip `34fe1824`（行完整性守衛在 `00803c5d`，其後 `34fe1824` 補一段 docstring）；前三輪為 `3b44ddc`／`480a163`／`e378f8f` |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |

## 1. AC 逐條核對

| AC | 結果 | 證據 |
| --- | --- | --- |
| AC1 新增一項 `SELFCHECKS` | ✅ | `check_config_schema` 註冊於 `foundry_lint.py:2787`；`--selfcheck` 輸出含 `✅ [config-schema] …（schema v2、4 個必填欄位、3 組值域，掃 59 份文件）` |
| AC2 配真的擋得住的反例測試 | ✅ | `ConfigSchemaTest` 25 條全過；**非空轉已證**：把行守衛改成 `if False:` 後，恰好新增那 3 條轉紅（含 9 個 field 的 subTest sweep），見 §3 實驗 A |
| AC3 分辨設定欄位與散文提到平台 | ✅ | 第 1 輪查證：三層判準（資訊字串／鍵頂格／必填欄位當證據）；`test_不是_Foundry_設定的_yaml_圍欄不誤報`、`test_散文提到舊欄位名不誤報` 皆綠。刻意的漏報方向已寫在 `foundry_config_fences()` docstring |
| AC4 不回溯改 `docs/features/` | ✅ | `CONFIG_FIELD_SCAN_SKIP_PREFIXES = (("docs", "features"),)`（`foundry_lint.py:1181`）；`test_歷史交付物不在掃描範圍內`／`test_排除的只有_docs_features` 一正一反 |
| AC5 `make check` 全綠、測試全過 | ✅ | 隔離 clone 上 `--selfcheck` 14 項全綠 exit 0；`unittest discover tools/foundry-lint` → `Ran 246 tests OK`。⚠️ `mirror-recon` 為 ⏭（clone 無 GitHub remote，環境所致）——**⏭ 不計為綠燈**，見 §2 |
| AC6 入口檔 §6 自檢列舉同步 | ✅ | `selfcheck-names` 綠：`15 項 × 4 處`，機械把關，未寫死總項數 |
| AC7 `org-sync` 不再多報假的「重複」 | ✅ | `org-sync` 綠（9 名）；第 1 輪已查證改法只在真有重複鍵時報，配一正一反兩條 |
| AC8 `org.yml` 的 `ai_platform` 值域把關 | ✅ | `foundry_lint.py:1528` `if org_path.exists() and "ai_platform" in enums:`；只驗「有填就要合法」未驗成必填。**本項是前三輪反覆失效的那一項，第 4 輪經 B4 實測關閉**（見 §3） |
| AC9 `table-shape` 納入根目錄雙入口 | ✅ | `TABLE_SCAN_FILES = ("CLAUDE.md", "AGENTS.md")`（`foundry_lint.py:930`）；`table-shape` 綠（掃 86 份） |

## 2. 四維檢查

- **正確性**：無發現。核心風險是「讀 `config-schema.md` 這份外部權威時只讀錯一格而不出聲」，四輪逐層收斂後已封閉，收斂性論證見 §3。行守衛的形式性質我另行查證過：`fields` 由 `top_rows` 經**只丟失不增生**的函式導出（少於四格跳過、regex 不中跳過、dict 同名塌縮），故 `len(fields) ≤ len(top_rows)` 恆成立，等號成立**充要於**「每一列都貢獻一個相異欄位名」。因此它雖寫成計數比對，形式上等價於白名單，不是那種認不得就靜靜跳過的相等比對。我實際找過抵銷攻擊（讓兩個計數同步減一以藏住加粗）：不存在——刪列同減兩邊，加粗只減 `fields`。
- **規格符合度**：無發現。AC8 歸屬 `config-schema` 而非 `org-sync` 成立——枚舉值域的權威在 `config-schema.md`，`org-sync` 的 docstring 原就寫明「枚舉合法性歸 config-schema」。AC4 的排除與 `V5` 是同一條取捨（風險方向是誤管而非漏管），一致。
- **安全性**：無發現。本項只讀 repo 內檔案、不執行外部輸入、不處理機敏資料。
- **可維護性**：`RETIRED_CONFIG_FIELDS` 手維護的取捨（開發者主動請我確認）**成立**：清單封閉且只有正名才會增長，而正名必經核可＋遞增 `foundry` 版本號；反向從「版本沿革」表剖析改名要讀散文，失敗方向是靜默漏掉，比手維護一則更糟。且已配一條廉價後盾（現名一定在表裡、舊名一定不在）。`count_cells()` 重構成 `table_cells()` 薄包裝行為無變化，`CountCellsTest` 原樣通過。次要建議見 §4。

## 3. 重大瑕疵清單

無。四輪累計提出四項，全數關閉；因為本單的爭點正是「守衛會不會靜默失效」，把關閉方式與證據留在這裡：

| 輪 | 瑕疵 | 關閉方式與我的驗證 |
| --- | --- | --- |
| 1 | 值域分隔符只認全形，換成 `/` ⇒ 枚舉與 AC8 值域整組靜默消失 | `M1` 實測轉紅 |
| 1 | 必填格拿整格字面比 `✅`，`✅（見下）` ⇒ 該欄位靜靜掉出 `required` | 改為封閉集合 `CONFIG_SCHEMA_REQUIRED_MARKS`，`M2` 轉紅 |
| 2 | 型別欄寫成相等比對 `typ == "枚舉"`（同族瑕疵搬到「格」這一層） | 改為白名單 `CONFIG_SCHEMA_TYPES`，`if typ not in …` 報紅。**逐格 sweep**：型別欄 9 格在 `480a163` 全綠、在 `e378f8f` 全紅 |
| 3 | 同族瑕疵再搬到「列」：`parse_schema_fields()`／`parse_schema_marks()` 的 `if m:` 沒有 else，欄位名格加粗整列消失，三道格守衛跟著消失 | 本輪新增行完整性守衛（`foundry_lint.py:1408`），battery 全數如預期 |

**第 4 輪 battery**（隔離 clone，每組套乾淨副本後直呼 `check_config_schema()`；歸因以行守衛自己的訊息字串判定）：

| 組 | 情境 | 結果 | 行守衛歸因 |
| --- | --- | --- | --- |
| B0 | 未突變、真實 repo | ✅ 綠 | — |
| B1[0]～B1[8] | 頂層表 9 列逐列欄位名加粗 | ❌ 全紅 9/9 | 每組皆 1 則，非鄰居代叫 |
| B2 | 重複欄位名（dict 塌縮） | ❌ 紅 | 1 則 |
| B3 | 該列少於四格 | ❌ 紅 | 1 則 |
| B4 | ＝ M4（加粗＋`config.yml` 合法省略＋`org.yml: banana`） | ❌ 紅 | 1 則，鄰居 0 |
| B5 | 抵銷攻擊（加粗 `ai_platform` ＋刪 `model_routing` 列） | ❌ 紅 | 1 則 |
| B6 | 只刪 `model_routing` 列（合法 schema 變更） | ✅ 綠 | — 不過度誤殺 |

三項另做的查證：

- **實驗 A（非空轉）**：把行守衛改成 `if False:` → 恰好 `test_欄位名格加粗會讓整列連同三道守衛一起消失`、`test_欄位名格逐格加粗都擋下`（9 個 field 全部）、`test_欄位表少一格時整列消失也擋下` 轉紅。守衛與測試互為對照，不是各自空轉。
- **實驗 B（測試會不會跟著突變躲開）**：第 3 輪的教訓是動態挑 fixture 的 helper 會自動改挑別的欄位。把 M4 套進 **repo 本體**再跑 `ConfigSchemaTest`：`480a163` 時代是 `Ran 20 … OK`（全躲開），本輪是 **`Ran 25 … FAILED (failures=20)`**，含 `test_真實_repo_通過`。不再躲開。
- **守衛鏈收斂**：`parse_schema_marks()` 與 `parse_schema_fields()` 用同一個 regex 打同一批列、同一個四格門檻，鍵集由建構方式決定就相同——我對 9 列各打兩種突變共 18 組比對兩者鍵集，**分歧 0 次**，故守 `fields` 即覆蓋 `marks` 的三道格守衛。至此三層（表找不找得到 → 每一列都解得出 → 每一格都是認得的字面）齊備，**再往上沒有下一層**：段落標題那一層由 `not fields or not required` 承接。

**機械層**：與**真正的** `origin/main`（`bc86675`）試合併零衝突，合併後 `Ran 245 tests OK`、`--selfcheck` 全綠。測試數已追平：`246 + 215 − 216 = 245`（base ＝ merge-base `58a0bc8`）。

⚠️ 一併記錄一個會誤導後手的環境事實：共用 workspace 的**本地** `main`（`108d18b`）比 GitHub 的 `main`（`bc86675`）**舊**——`gh-main..ws-main` 為空。對 `108d18b` 做合併測試會回「Already up to date」，那是假綠。判法是先 `git merge-base --is-ancestor` 確認不是已含，再合。

## 4. 次要建議

1. `parse_schema_marks()` 的 docstring 應註明它與 `parse_schema_fields()` **共用取列條件**（同一個 `first_table_rows()`、同一個四格門檻、同一個 `CONFIG_SCHEMA_FIELD_RE`），所以行完整性守衛守 `fields` 就一併覆蓋了它——這是目前成立的**耦合**而非保證，兩者取列條件哪天被改得不一樣，該覆蓋會無聲消失。

   **已於 `34fe1824` 採納。** 我查證過該 commit 相對 `00803c5d` 是**純註解變更**，不是照單全收：把兩個版本的 AST 去掉所有 docstring 後比對，`ast.dump` 的 md5 完全相同（`e99a33f9…`）。因此第 4 輪的全部驗證結論原樣適用於 `34fe1824`，不需再開一輪。

## 5. 分支收尾檢查

- 分支狀態：**待合併**。與 `origin/main`（`bc86675`）零衝突、合併後測試與自檢全綠，可直接合併回 main 並刪除遠端分支（`P1`）。本報告已 commit 進分支。
- 本單不動 `docs/handbook/`，不觸發第 7 節手冊發佈四步。

## Verdict

**✅ APPROVED**
