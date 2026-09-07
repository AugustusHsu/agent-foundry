# 審查報告：MYL-116 X2 開單規則的兩項機械檢查：開單者白名單、PM 開單必備欄位

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-116 |
| 分支 | `MYL-116-issue-rules-lint` |
| 審查範圍 | 第 1 輪 `main...215181f`（3 顆 commit、12 檔）；第 2 輪 `215181f..d47708d`（1 顆 commit、7 檔、+317/-34） |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-07 |
| 輪次 | 第 2 輪（複審） |

第 1 輪退回一項重大瑕疵（`I1` 的違規紅字沒有收斂出口）＋六項次要建議。本輪依角色規範
**對著上一輪的瑕疵清單逐項驗，不重新全面審查**；新發現另立第 5 節標明。

## 1. 第 1 輪瑕疵逐項複驗

### 重大瑕疵 #1：`I1` 違規沒有收斂路徑 → ✅ 已修

第 1 輪固定的驗收條件是「處置完成後 `make check` 回綠，且**沒有**動 `ISSUE_RULES_SINCE`、
**沒有** hide 那張單、**沒有**設 `FOUNDRY_LINT_OFFLINE`」。四項逐條驗：

| 驗收條件 | 結果 | 證據（本輪自己跑的） |
| --- | --- | --- |
| 處置完成 → 回綠 | ✅ | 見下方端到端探針 B／C 兩列 |
| 沒動 `ISSUE_RULES_SINCE` | ✅ | `git diff 215181f..d47708d` 該行零命中；現值仍 `MYL-125` |
| 沒 hide 任何單 | ✅ | 本輪 diff 對 `hiddenAt` 的唯一改動是把它從 `check_pm_issue_fields` 移進共用的 `fetch_authored_issues()`（次要建議 #2），過濾行為不變 |
| 沒設 `FOUNDRY_LINT_OFFLINE` | ✅ | 本輪 diff 全檔零命中 |

**端到端探針**（本輪自建）：把 `ISSUE_RULES_SINCE` 暫時放寬成 `MYL-122` 重現違規狀態，
只攔截 `/comments` 端點注入留言，**正則與作者判定都走真的那份**，其餘（工單清單、編制、
角色解析）全走線上真資料。八列比對：

| 情境 | 結果 |
| --- | --- |
| A 沒有任何標記 | 🔴 紅 3 條（MYL-122／123／124）＝重現第 1 輪描述的狀態 |
| B 標記由 Product Manager 留 | 🟢 綠 |
| C 標記由使用者留 | 🟢 綠 |
| D 標記由**違規者自己**留 | 🔴 紅 3 條 ← 自我特赦被擋 |
| E 標記由 CEO 留（在白名單內、但不是覆核者） | 🔴 紅 3 條 |
| F PM 留的標記已被刪除（`deletedAt`） | 🔴 紅 3 條 |
| G PM 留但形狀不對（冒號後沒內容） | 🔴 紅 3 條 |
| H 系統留言帶標記 | 🔴 紅 3 條 |

B／C 證明出口真的接得上（不是「剛好沒紅」），D～H 證明四道守衛各自都在擋東西。
E 那一列與卡 `dcc54306` q2 的答案（`reviewer_only`＝只認 PM 或使用者）一致——CEO 雖在
開單白名單內，但不是 `I1` 的覆核者，不算數。

### 次要建議 #1～#6 → ✅ 六項全收，且每一項都有測試守著

| # | 建議 | 落點 | 守門證據 |
| --- | --- | --- | --- |
| 1 | 單張撈不到不要整項 `skipped`（＝漏報） | `check_pm_issue_fields` 改記 `unreadable` failure、續判其餘 | 突變 N7 轉紅 3 支 |
| 2 | `I2` 共用 `fetch_authored_issues()` | 三道過濾（`projectId`／`hiddenAt`／空 `identifier`）只剩一份 | `make check` 綠；原本漏的空 `identifier` 那道已納入 |
| 3 | 白名單標籤依宣告順序 | `sorted(allowed)` → `allowed` | 突變 N8 轉紅 3 支；探針實印「使用者／CEO／Product Manager」 |
| 4 | `author_user` 不可達分支補註解 | `issue_author_violations()` 內 5 行註解，並寫明它是 fail-open | 目視確認 |
| 5 | `L28` 補「PATCH 回 200 no-op 不是 4xx」 | known-drift `L28` | 目視確認 |
| 6 | 缺 AC 的紅字補形狀說明 | 新增 `AC_FIELD` 常數＋訊息那一段 | 突變 N9 轉紅 3 支 |

## 2. AC 逐條核對

第 1 輪已判 ✅ 的五條本輪只覆驗沒有回歸；AC6 本輪判定。

| AC | 結果 | 證據 |
| --- | --- | --- |
| 1. 兩項各有反例測試，拿掉守衛會失敗 | ✅ | 本輪我自己在 `clone --shared` 的隔離副本對**原始碼**做 9 處突變（N1～N9），**9 處全部轉紅、沒有一處空轉**；還原後基準 305 項 OK |
| 2. 白名單現況不紅，MYL-113／114 不得被判違規 | ✅ | `make check` 實跑 `✅ [issue-authors]（MYL-125 起 0 張，全部 123 張）`；探針把起算點放寬到 `MYL-122` → 紅的只有 MYL-122／123／124，MYL-113／114 不在其中 |
| 3. `unittest discover` 全過、`make check` 通過 | ✅ | `make check` exit 0；305＋15＋34＋107 項全過 |
| 4. 兩項名稱進名稱清單且雙入口逐字一致 | ✅ | `selfcheck-names` ✅（17 項 × 4 處）、`entry-sync` ✅ |
| 5. 定位寫對：事後檢查不是閘門 | ✅ | 第 1 輪已驗五處措辭；本輪新增的條文段落（protocol:86）維持同一定位，且明寫「其他收斂手段一律不算數」 |
| 6. 經 Code Reviewer 審查 APPROVED | ✅ | 本報告 |

⚠️ **AC5 的行為面本輪才真正成立**：第 1 輪它只是「字面對、行為不成立」（條文承諾的處置走完
紅字仍在）。補上覆核完成標記之後，條文寫的那條路才真的走得完。

## 3. 四維檢查

- **正確性**：無發現。新增的四道守衛（形狀、作者、`deletedAt`、出口接線）各自有反例守著。
  失效方向也對：`fetch_author_review_mark()` 撈不到留言時回 `False`＝紅字留著，是**看得見**
  的失敗而不是靜靜轉綠；`issue_id` 為空時不發呼叫、直接算沒標記，同一個方向。
- **規格符合度**：條文（protocol:86）、手冊 06:64、adapter、`role-product-manager`、lint 訊息
  五處對同一件事的描述一致，且與卡 `dcc54306` 的兩個答案（`mark`＋`reviewer_only`）逐字對得上。
  第 1 輪那個「條文承諾 ↔ 實作做不到」的落差已消除。
- **安全性**：無發現，而且**這一項本輪特別查過**——`reviewer_only` 是一道授權判定，它的可靠度
  取決於留言作者欄能不能被偽造。讀伺服器原始碼確認三件事：(a) `authorAgentId`／`authorUserId`
  取自**已認證的 actor**，不吃 request body（`services/issues.js:6854`）；(b) `authorType` 雖然
  收 caller 值，但 `assertIssueCommentAuthorTypeAllowed()`（`:3427`）在 actor 是 agent 而
  `authorType !== "agent"` 時直接 422 ⇒ **agent 無法自稱 user**；(c) 平台對 `onBehalfOfUserId`
  另有主動防偽（agent 送這個欄位會被 `issue_write_attribution_spoof_rejected` 拒絕並留稽核），
  正好獨立佐證「不能拿那一格判使用者」是對的。實測面也一致：本單 14 則留言裡，agent 留的
  13 則全是 `authorType: "agent"`／`authorUserId: null`／`onBehalfOfUserId` 有值，只有使用者
  那則 `59bce78e` 是 `authorType: "user"`＋`authorUserId` 有值。
- **可維護性**：無阻礙級發現。`issue_author_violations()` 與組訊息拆開是對的——出口查詢因此
  只對違規的那幾張發呼叫，體例與 `fetch_source_issues()` 只對疑似漏建的單翻留言一致。
  `AC_FIELD`／`UPSTREAM_FIELD` 取常數避免字面字串對映，也與既有慣例一致。

## 4. 重大瑕疵清單

無。

## 5. 本輪新發現（非阻擋，第 1 輪沒看過的東西）

依角色規範註明：以下是**新發現**，不是 Developer 沒修。三項都不影響 Verdict。

1. **已特赦的違規會被永久重複查詢**。`issue_author_violations()` 每輪都會把違規單全數選出來，
   再逐張打 `/comments` 判標記——**被標記清掉的那幾張下一輪還是會被選出來、還是要再撈一次留言**。
   這項跑在 pre-commit 的 `always_run` 上，所以歷史違規累積 N 張之後，每一次 commit 就固定多
   N 次 HTTP 呼叫，且只增不減。現況 0 張、零成本，但這是單調成長的。若哪天覺得慢，最省事的
   收法是把「已特赦」也納入 `ISSUE_RULES_SINCE` 那類一次性界線，而不是加快呼叫。
2. **特赦次數在輸出上看不見**。`res.summary` 只印「MYL-125 起 N 張，全部 M 張」，讀的人分不出
   「綠是因為沒有違規」還是「綠是因為 3 張被標記清掉了」。這與條文「標記不是把違規抹掉」的
   宣稱有一點張力。⏭ 但這是**沿用既有前例**——`mirror-recon` 的 summary 同樣不印
   `Mirror-skipped:` 的張數（`foundry_lint.py:2530`），所以不是本單引入的退步。要補的話，
   summary 加一句「其中 K 張已有覆核完成標記」即可。
3. **分支名少了類型前綴**。protocol 第 7 節寫的形狀是 `<類型>/<工單編號>-<簡述>`（例
   `feat/MYL-12-login-form`），本分支是 `MYL-116-issue-rules-lint`。核心要求（分支名含工單編號）
   有滿足，且已有前例（`myl-79-t7-platform-apply` 已合併進 main），該條又是 `【自律】`；分支
   已 push，現在改名的代價高於價值。**不要求本單處理**，下一張單起照格式開即可。

另記一件查證結果，供之後維護參考：`ISSUE_AUTHOR_CLEARED_RE` 與 `MIRROR_SKIPPED_RE` 是
**逐字同形**的（`^…[：:]\s*\S` vs `^Mirror-skipped:\s*\S`，都掛 `re.M`），刻意保持一致，
所以兩者共有的弱點（`\s*` 會跨行，措辭一改就靜默失效）在本單不算新增缺口——常數註解也寫明了。

## 6. 分支收尾檢查

- 分支狀態：**待合併**。原因＝protocol 第 7 節「合併時點」明定掛審查單的實作分支
  一律在 APPROVED **之後**才合併回 main，所以本報告簽出時尚未合併是規範要求，不是遺漏。
- 分支上 4 顆 commit 全屬本單，訊息皆為 gitmoji ＋繁體中文標題並帶工單編號。
- `git diff --name-only main...HEAD` 13 檔（含本報告）全屬本單，無夾帶。
- 遠端 `origin/MYL-116-issue-rules-lint` 已與本機同步於 `d47708d`。

**APPROVED 之後 Developer 尚須完成（不是本報告的驗收項，但屬結案條件）**：

1. 合併回 main。
2. **手冊發佈四步**（本單動了 `docs/handbook/06`）：合併 → 用 `templates/publish-review.md`
   寫審查記錄 → commit（`handbook_commit` 填實際 sha）→ `scripts/publish-wiki.sh`。
3. 合併當下重新確認 `ISSUE_RULES_SINCE = MYL-125` 沒被新單越過。**本輪覆驗：現況全公司 124 張、
   最大單號 MYL-124、`≥ MYL-125` 的單 0 張 ⇒ 此刻仍對得上**；合併前若又開了新單要再確認一次。

## Verdict

**✅ APPROVED**
