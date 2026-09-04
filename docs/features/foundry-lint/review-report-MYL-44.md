# 審查報告：MYL-44 MYL-39C 手冊同步三層閘門 ＋ 發佈腳本戳記旁路 ＋ 公開站同步 DoD

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-44 |
| 分支 | `feat/MYL-44-handbook-stamp` |
| 審查範圍 | `fbd70ff`、`415d772`（12 檔：lint ＋ 測試 ＋ 發佈腳本 ＋ protocol ＋ 四章手冊 ＋ 三處說明） |
| 審查者 | Tech Lead（依 MYL-41 前例兼任 Code Reviewer，見下方「審查者身分」） |
| 日期 | 2026-09-04 |

**審查者身分**：本單無獨立 Code Reviewer 交接，比照 MYL-41（`de35664`）由執行者依
`role-code-reviewer` 判準自審並存檔。第 1、2 層全為機械證據，第 3 層的判斷已刻意找反例
而非確認既有結論——下方兩項次要建議即由此產生。

## 1. AC 逐條核對

| AC | 結果 | 證據 |
| --- | --- | --- |
| 層 0 pre-commit 觸發器可運作：改 protocol 未動手冊時擋下，且訊息說得出接下來要做什麼 | ✅ | 隔離 clone（`$RUN_SCRATCH/verify`，`pre-commit install` 後）改 protocol 單檔 `git add` 再 commit → hook `foundry-handbook-sync` `Failed`／exit 1，`git log -1` 確認 commit 未發生；訊息列出四章章名與三條處置 (1)(2)(3)，並把 (2) 的目標 sha 算好填進去（實測輸出 `fbd70ff`） |
| 層 1：`foundry_lint` 新增 `handbook-stamp` 自檢，驗四章戳記存在、格式合法、sha 不落後 | ✅ | `--selfcheck` 輸出第 7 項 `✅ [handbook-stamp] …（protocol 最新 8433b97）`；同一 clone 上以 `--no-verify` 造出 protocol-only commit `64779c1` 後，四章各報一則「戳記停在 `8433b97`，其後有 1 顆…」exit 1；補推戳記後回綠 |
| `03`／`04`／`06`／`07` 四章各有戳記行，初始值填 protocol 當前實際 sha | ✅ | 四檔標題後第一個非空行皆為 `> 最後對照 protocol \`8433b97\`（2026-09-04）`；`git log -1 --format=%H -- skills/foundry-protocol/SKILL.md` 於分支開工時即 `8433b97…`（MYL-40 那顆） |
| protocol §7 增訂戳記-only 輕量路徑 | ✅ | §7 新增「手冊同步戳記（MYL-44 增訂）」整節（含 `【機械】` 標記與違反後果），並在「手冊發佈審查」的規則清單增訂戳記-only 免獨立審查記錄那條 |
| `publish-handbook.sh` 旁路實作完成，且夾帶實質內容時仍 `exit 1`（必須有反向測試） | ✅ | 腳本層級：隔離 clone 截取閘門段執行，戳記-only 情境 exit 0 並印出被略過的兩顆 commit；追加一顆夾帶「偷渡進公開站的一句話。」的 commit 後 exit 1 且指名該行。單元層級：`test_旁路_夾帶實質內容仍擋下`、`test_旁路_刪掉一段內文仍擋下`、`test_旁路_刪掉整章不算戳記變更`、`test_旁路_CLI_通過印出_commit_清單_夾帶時_exit_1` |
| 單元測試全過；`make check` 通過 | ✅ | `make check` exit 0：selfcheck 七項全綠、foundry-lint 79 項（新增 23 項）、model-routing 15、browser-probe 34 |
| 走完 protocol §7 手冊發佈審查四步 | ⏳ | 本報告 APPROVED 後執行；四步的證據落在 `docs/publish-reviews/MYL-44.md` 與工單留言 |
| DoD：結案時公開站已與 main 的 `docs/handbook/` 一致（Frontend Verifier 驗） | ⏳ | 發佈後委派 Frontend Verifier；本單 blocked 於該子單直到回報 |

## 2. 四維檢查

| 維度 | 結論 | 說明 |
| --- | --- | --- |
| AC 是否真的達成 | 通過 | 每條 AC 都自己跑過而非採信交付宣稱；層 0／層 1／旁路三者各自在隔離 clone 上做過**反向**驗證，不是只看正向綠燈 |
| 是否偏離設計文件 | 通過（有一處經判定的偏離） | 計畫 v3 §3 寫「不落後於 protocol 最新 sha」。實作改為「戳記之後每一顆 protocol 改動都要有手冊變更同行」——字面的「等於最新 sha」在同一顆 commit 內**永遠無法成立**（戳記只能指向已存在的 commit，指不到自己那顆），照字面實作會讓閘門在第一次使用就鎖死。這屬 protocol 第 6 節的「規格前提不成立」而非實作偷工，已在 `unsynced_protocol_commits` docstring 與 protocol §7 條文中寫明取代理由 |
| 安全與資料正確性 | 通過 | 旁路是這次唯一擴大放行面的改動，判定條件全由 `git diff` 決定、無自我申報成分；放寬空白行後另補「刪掉內文只留空行」的反例確認未開洞。腳本無新增網路或憑證面；`git_run` 只讀不寫 |
| 可維護性 | 通過 | 戳記正則單一來源（`STAMP_RE`），發佈腳本呼叫 `--stamp-only-since` 而非自帶第二份正則——與 `.pre-commit-config.yaml` 既有註解「同一份指令抄在三個地方正是漂移的來源」同一立場。七項自檢的說明四處（Makefile、`.pre-commit-config.yaml` hook name、雙入口 §6、CLI help）已同步且照 MYL-42 慣例不寫「共 N 項」 |

## 3. 重大瑕疵清單

無。

（審查過程中確有一項被打穿：初版判定要求每個變更行都符合戳記正則，漏了戳記錨點必然
帶進的空行，旁路在真實 repo 上第一次就走不通。該缺陷在合併前於隔離 clone 被實測抓到並
以 `415d772` 修正、補兩項雙向測試，因此不列為待處理瑕疵。記在這裡是因為它說明了一件事：
單元測試造的 repo 太乾淨，真實歷史才照出這個洞。）

## 4. 次要建議

- **腳本層級的閘門邏輯沒有自動化測試**。`publish-handbook.sh` 那段候選挑選與旁路的 shell
  邏輯，本輪是以「截取閘門段在隔離 clone 上手動執行」驗證的，`make check` 不涵蓋它。
  Python 側（`handbook_diff_is_stamp_only`）有完整雙向測試，shell 側沒有。依 code-reviewer
  「同一個缺陷不該被人工抓第二次」，建議後續補一支 shell 層級的閘門測試。不擋本單結案。
- **`--stamp-only-since ""` 落回 lint 模式**並報「需要 --type 與 file」，錯誤訊息會誤導。
  實務上不會傳空字串（腳本內先驗 `[ -n "$BASE" ]`），列為次要建議。

## 5. 分支收尾檢查

- 分支名 `feat/MYL-44-handbook-stamp` 含工單編號，符合 protocol 第 7 節。
- `git diff --name-only main...HEAD` 的 12 個檔案全屬本單範圍，未夾帶別單變更。
- `git log --oneline main..HEAD` 兩顆 commit 皆 gitmoji ＋繁體中文標題。
- 工作區另有兩個未追蹤檔（`.codex/`、`myl48-phase2-still-private.png`）屬共用 workspace 的
  併行 run 痕跡，未納入本分支任何 commit。
- 合併回 main 後刪除本分支，由結案前的最後執行者自查（本單無獨立 Code Reviewer 交接）。

## Verdict

✅ **APPROVED**

AC 六條有機械證據、兩條為合併後才執行的發佈與 DoD 驗證；四維無重大瑕疵；分支收尾條件
在合併與刪支完成時滿足。次要建議兩項不擋結案。
