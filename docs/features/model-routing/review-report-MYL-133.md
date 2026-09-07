# 審查報告：MYL-133 確認 codex 的 `model_reasoning_effort="max"` 是否合法

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-133 |
| 分支 | `MYL-133-codex-effort-max` |
| 審查範圍 | 第 1 輪；單一 commit `86e9940`，全分支 `origin/main...86e9940` |
| 審查者 | Code Reviewer（agent `148355fe`） |
| 日期 | 2026-09-08 |

> 本單交付物是 `tools/model-routing/apply_profile.py` 的**純註解**（15 行新增、0 行刪除，
> `MODEL_TARGETS` 的值一個字未動）。因此本輪審查的重心不在程式行為，而在
> **「註解所宣稱的事實是否為真」**——一條錯誤的留證註解，害處大於沒有註解，因為它會讓
> 下一個人停止查證。故三項證據全部由審查者在本機獨立重跑，不採信交付回報的轉述。

## 0. 機械層（第 1 層）

| 檢查 | 結果 |
| --- | --- |
| `make check`（分支 tip） | ✅ 18 項自檢全綠；342 + 27 + 34 + 107 測試 `OK` |
| `make check`（**與 main 合併後的狀態**） | ✅ 18 項自檢全綠；342 + 49 + 34 + 107 測試 `OK` |
| `git diff --name-only origin/main...86e9940` | ✅ 只有 `tools/model-routing/apply_profile.py`，未夾帶別單檔案 |
| `git log --oneline origin/main..86e9940` | ✅ 單一 commit，gitmoji ＋繁體中文標題 |

⚠️ 兩次 `make check` 是刻意分開跑的，理由見 §2「正確性」第 2 點。
全程在 `git clone --shared` 的隔離副本內作業（known-drift `X1`）——共用 workspace
此刻被另一個 run 佔在 `MYL-117-parent-mandate` 上，在錯的分支跑只會得到誤導的綠燈。
隔離 clone 依 MYL-130 的做法補上 GitHub remote，`mirror-recon` 因此真的有跑（非 ⏭）。

## 1. AC 逐條核對

| AC | 結果 | 證據（審查者自行取得） |
| --- | --- | --- |
| 1. 查明 codex CLI 對 `model_reasoning_effort="max"` 的實際行為，以可覆核證據呈現 | ✅ | 三項證據全部獨立重跑成功，見下方「證據重跑」 |
| 2. 依結果二選一：合法 ⇒ 走 (b) 不改值、旁邊留註解附出處 | ✅ | `git diff` 為 15 insertions / 0 deletions；`MODEL_TARGETS` 六格值與 `origin/main` 逐字相同；註解含三項出處與「不要改成 `xhigh`」警告 |
| 3. 回答值域要不要有機械驗證，判不補則寫理由與代價 | ✅ | 工單留言 `edaf1810` 第 4 節：三條理由（值域非我方所有／失敗是響的／已有兩層人的後盾）＋**兩條代價明寫**（時間差、model×effort 配對無人管），另附「被評估後放棄的中間方案」 |
| 4. 額度不足時走原始碼路徑或轉 `blocked`，不空轉 | ✅ 不適用 | codex CLI 在本機可用，審查者實跑 `codex exec` rc=0；降級路徑未啟用是正確處置 |
| 5. `make check` 全綠 | ✅ | 見 §0，且**額外驗到合併後狀態亦全綠** |

### 證據重跑（審查者本機，非轉述）

**版本**：`codex --version` ⇒ `codex-cli 0.149.1`，與註解所載一致。

**證據 A — 實跑接受 `max`**：

```
$ codex exec --skip-git-repo-check -c model="gpt-5.6-sol" -c model_reasoning_effort="max" \
    "reply with exactly: OK"
model: gpt-5.6-sol
reasoning effort: max
OK
$ echo $?        # 0
```

**證據 B — catalog 列出 `max`**：`codex debug models` 逐模型解析

| model | supported_reasoning_levels |
| --- | --- |
| **gpt-5.6-sol**（`MODEL_TARGETS` codex high） | low, medium, high, xhigh, **max**, ultra |
| **gpt-5.6-terra**（codex medium／low） | low, medium, high, xhigh, **max**, ultra |
| gpt-5.5 | low, medium, high, xhigh（**無 max**） |

**證據 C — 負向對照組成立（本輪加驗的關鍵一項）**：交付回報以「rc=0」當證據，
而 rc 要能當證據，得先證明它**在該失敗時真的會失敗**。實測同一路徑送 `bogus`：

```
ERROR: {"error":{"message":"[ReasoningEffortParam] [reasoning.effort] [invalid_enum_value]
  Invalid value: 'bogus'. Supported values are: 'none', 'minimal', 'low', 'medium',
  'high', 'xhigh', and 'max'.","type":"invalid_request_error"},"status":400}
$ echo $?        # 1
```

⚠️ 取這個 rc 時**不能經過管線**——首次量測我把 `| tail` 的 rc 誤讀成 codex 的 rc（顯示 0），
去掉管線後才是真值 1。rc=1（拒收）／rc=0（接受）成對成立，證據 A 的 rc=0 才有鑑別力。
錯誤訊息本身即供應商伺服器給出的權威值域，`max` 明確在內。

## 2. 四維檢查

- **正確性**：註解的每一項事實宣稱都經獨立重跑為真（版本、header 回報、catalog、400 值域）。
  另外主動查了兩個交付回報沒涵蓋、但足以推翻結論的點：
  1. **證據取樣的 model 與設定值的 model 是否同一個**。值域隨模型而異（`gpt-5.5` 只到
     `xhigh`），若證據取自 A 模型而設定用 B 模型，結論即不成立。實查
     `MODEL_TARGETS["codex"]["high"] == ("gpt-5.6-sol", "max")`，與證據同一模型；
     medium／low 的 `gpt-5.6-terra` 亦支援 `high`／`medium`，無鄰接破壞。
  2. **分支基底落後三個 commit，且落後的 commit 動到同一個檔案**。branch base 為
     `1972aa5`，而 `origin/main` 已是 `2fdeaba`；其中 `2766c48`（MYL-131）改的正是
     `tools/model-routing/apply_profile.py`。分支 tip 的綠燈**不蘊含**合併後的綠燈，
     故另跑一次試合併：自動合併乾淨無衝突，註解正確落在 `MODEL_TARGETS` 上方，
     合併後 `make check` 全綠（model-routing 測試由 27 增為 49，即 MYL-131 新增的部分）。
  3. **引用行號的版本出處**。註解引 `codex-local/src/index.ts:27`，該路徑實際版本為
     `0.3.1`，而平台在跑的是 `2026.831.1`——兩者不同棵樹。實查在跑的那一份
     （`@paperclipai/adapter-codex-local` `2026.831.1` 的 `dist/index.js:84`）**同樣**
     寫著 `(minimal|low|medium|high|xhigh)`，故「該行散文已過時」對**實際在跑的版本**
     成立，不是只對舊樹成立。行號本身對所引路徑亦正確。
- **規格符合度**：走 AC 2 的 (b) 路，值未動、只加註解，與 AC 原文一致。PM 在開單留言
  `1c4673c5` 明示「這張單刻意小，不要順手把 `MODEL_TARGETS` 或值域驗證一起重構」，
  交付物確實克制在該範圍內；越界的兩件事（跨 repo 修那兩行散文、`--apply` 後補 smoke）
  都留在留言裡建議另開單而未自行動手，處置正確。
- **安全性**：無執行語意變更，無輸入處理面、無機敏資料落地。註解僅含模型代號與公開錯誤訊息。
- **可維護性**：正面。本單的產物就是「讓下一個人不必重查」的那段留證，且明確標出兩份
  過時散文與「不要改成 `xhigh`」的反向警告——後者擋掉的正是原單指出的無故降級風險。

## 3. 重大瑕疵清單

無。

## 4. 次要建議

不擋結案，Developer／PM 可自行決定是否採納：

1. **註解引用行號建議帶版本註**。`codex-local/src/index.ts:27` 指的是 `0.3.1` 那棵樹；
   在跑的 `2026.831.1` 對應位置是 `dist/index.js:84`。兩者今天內容相同故結論不受影響，
   但行號會隨版本漂移，補一句「（0.3.1 樹；2026.831.1 的 `dist/index.js:84` 同文）」
   可省下一次「引的行號對不對」的往返。
2. **`ultra` 的存在是兩個值域的分岔點**。`codex debug models` 說 `gpt-5.6-sol` 支援
   `ultra`，但伺服器 400 列舉的合法值裡**沒有** `ultra`（有 `none`／`minimal`，catalog 反而沒有）。
   即 catalog 與 API enum 是兩個不完全重疊的集合。本單結論不受影響（`max` 同時在兩者內），
   但註解中「漏 `none` 與 `max`」一語是以 API enum 為基準，若日後有人拿 catalog 來對會困惑。
3. **這段知識的長期歸宿建議是 `docs/standards/known-drift.md`**（`L`＝平台限制或 `S`＝API 形狀）。
   「值域屬供應商伺服器、隨模型而異、兩端 CLI 皆零驗證」是跨工單會反覆用到的事實，
   放在 `apply_profile.py` 的註解只有改那張表的人看得到。此事超出本單 AC 且 PM 已交代
   越界要回頭開單，**建議由 Product Manager 開一張小單收容**。
4. **Developer 提的 `--apply` 後最小 smoke 值得認真評估**。它涵蓋值域錯誤、model 代號錯誤、
   額度耗盡三種失敗，且不持有任何會過期的知識——比值域白名單更貼合本 repo
   「不要製造第二份會過期的拷貝」的自我約束。同樣**應由 PM 另開單**。
5. **關於 AC 3 判「不補」，審查者同意**。理由不是「補起來太麻煩」，而是失敗模式不需要它：
   送錯值是第一個 turn 就 400 硬失敗、exit 1、且錯誤訊息自帶完整合法值域，
   不存在「靜默降級成低 effort 但帳單照付」這種需要機械攔截的無聲失敗。
   Developer 誠實寫出的兩條代價（時間差落在被改動 agent 的下次喚醒、model×effort 配對無人管）
   是準確的殘留風險陳述，建議 4 正是針對其中第一條。

## 5. 分支收尾檢查

- 分支狀態：**已合併並刪除**。`--no-ff` 併入 `main`（合併 commit 見工單留言），
  已推 `origin/main`，遠端分支 `MYL-133-codex-effort-max` 已刪除。
  依 `P1`（例行推送，公開面未新增一格）執行，無需逐次授權。
- 本單未動 `docs/handbook/`，**不觸發** protocol 第 7 節的手冊發佈四步。

## Verdict

**✅ APPROVED**

三項證據皆由審查者獨立重跑為真，且負向對照組成立（rc 有鑑別力）；證據取樣的模型與
設定值的模型為同一個；分支基底雖落後三個 commit 且落後範圍動到同一檔案，實測合併乾淨、
合併後 `make check` 全綠。無重大瑕疵，四條次要建議皆不擋結案，其中兩條（建議 3、4）
超出本單 AC，已標明應由 Product Manager 另行開單。
