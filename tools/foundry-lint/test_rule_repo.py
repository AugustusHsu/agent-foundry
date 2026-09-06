"""foundry-lint 測試：**以 agent-foundry 自身為 fixture** 的那一半（MYL-91）。

執行：python3 -m unittest discover tools/foundry-lint（與可攜那半套一起被 discover）

## 為什麼要有這個檔

`test_foundry_lint.py` 被 `foundry-init` 的複製清單整包帶到每個目標專案，而它裡面
有一批測試的前提是「跑在規則本體上」——變異 `docs/handbook/`、讀
`docs/features/foundry-lint/PRD.md`、斷言 `.foundry/config.yml` 的值是 agent-foundry
那一份。這些東西目標專案依規格就沒有，於是那些專案第一次跑 `make check` 就是
`FAILED (failures=22, errors=26)`（MYL-91 實測）。

**分檔而不是 `skipTest`**：`--selfcheck` 那半套（MYL-87）用 `is_rule_repo()` 跳過是
安全的，因為 `init-copy-list` 的判準旗標與對照端是同一個目錄；手冊三項旗標≠對照物，
MYL-87 就刻意做成兩層。本檔這批屬於後者、而且做不出第二層（50 條各要各的物件），
單層跳過的失效方向是「規則本體少了 `skills/foundry-init/` ⇒ 48 條一起靜默變 ⏭」，
正是判準①要擋的。分檔則讓它們在規則本體**無條件執行**，沒有旗標可以關掉。

放進本檔的判準：**依賴規則本體預先存在的內容**——兩種形狀都算，
①`docs/` 等不在複製清單上的素材；②`.foundry/` 兩份設定檔的**實際值**。
自己造反例寫檔不算（`RepoCopyTestCase` 那批留在可攜檔）。

⚠️ ②是 MYL-91 第 1 輪審查補進來的：原本只寫 ①，於是「可攜檔裡寫死
`ai_platform: paperclip`」這一格從網眼漏掉，宣告 `codex` 的目標專案照樣紅。
形狀相近但**不**屬於本檔的例子：反例自己把兩份檔的值都寫定（不管現值是什麼），
那是可攜的——`OrgSyncTest` 的 `ai_platform` 那兩條就是。

界線由本檔的 `PortableSuiteInTargetProjectTest` 機械把關，兩件事一起做：
把 root 削成目標專案的形狀（`ABSENT_IN_TARGET`），以及把 `.foundry/` 換成
目標專案自己的宣告（`_retarget_foundry_dir`）——少了後者，②整類都逃得掉。
"""
# FOUNDRY:RULE-REPO-ONLY —— 本檔以 agent-foundry 自身為 fixture，foundry-init 不複製它


import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import foundry_lint
# 匯入的同時會跑到可攜檔的模組層設定（關掉出網、清掉繼承來的 `GIT_*`），
# 那兩件事對本檔一樣必要——不要在這裡再抄一份。
from test_foundry_lint import REPO_ROOT, RepoCopyTestCase, run_cli

REAL_PRD = REPO_ROOT / "docs" / "features" / "foundry-lint" / "PRD.md"


class RealRepoDocsSmokeTest(unittest.TestCase):
    """對真實 repo 的煙霧測試：素材是 `docs/features/foundry-lint/PRD.md`。

    原本在 `RealRepoSmokeTest`，MYL-91 依「要不要預先存在的 docs」拆出來。
    """

    def test_真實_PRD_通過_且不依賴_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli("--type", "prd", str(REAL_PRD), cwd=tmp)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("✅", proc.stdout)

    def test_刪除必備章節的_PRD_副本不通過(self):
        text = REAL_PRD.read_text(encoding="utf-8")
        target = "## 5. 邊界情況與錯誤處理"
        # 該字串也出現在 PRD 內文，須整行比對只刪標題行本身
        kept = [line for line in text.splitlines() if line.strip() != target]
        self.assertEqual(len(text.splitlines()) - len(kept), 1)
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "PRD-缺章節.md"
            copy.write_text("\n".join(kept) + "\n", encoding="utf-8")
            proc = run_cli("--type", "prd", str(copy))
        self.assertEqual(proc.returncode, 1)
        self.assertIn(f"  - {target}", proc.stdout)

class RealConfigTest(unittest.TestCase):
    """`.foundry/config.yml` 讀得出來——斷言的是 agent-foundry 自己那份的值。

    原本在 `ConfigParserTest`（parser 本身的兩條與 repo 無關，留在可攜檔）。
    """

    def test_真實設定檔讀得出_platform(self):
        cfg = foundry_lint.read_config(REPO_ROOT)
        self.assertEqual(cfg.get("devtools_platform"), "paperclip")


class RealOrgTest(unittest.TestCase):
    """`.foundry/org.yml` 的內容——斷言的是 agent-foundry 自己那份的宣告。

    分工：值域成員本身（`configure_agents` 在不在 `ORG_PERMISSIONS` 裡）與值域
    的反例都是可攜的，守在 `OrgSyncTest`；這裡守的是「**本 repo** 的 CEO 確實
    登記了它」——那是本 repo 的資料，目標專案沒有義務長成一樣。
    """

    def test_CEO_登記了_configure_agents(self):
        text = (REPO_ROOT / foundry_lint.ORG_REL).read_text(encoding="utf-8")
        ceo = next(r for r in foundry_lint.parse_org(text)["roles"] if r["id"] == "ceo")
        self.assertIn(
            "configure_agents", ceo["permissions"],
            "CEO 的 `agents:configure` 登記不見了——那是 MYL-79 卡 `0bd69c99` Q5 核可"
            "補上的既有現況，移除它要走 `org.yml` 的核可路徑，不是順手改")


class SelfcheckTest(unittest.TestCase):
    """在真實 repo 的副本上做變異，證明每項檢查都真的擋得住。

    「永遠會通過的檢查」等於沒有檢查，所以每一項都配一個反例。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        shutil.copytree(
            REPO_ROOT, self.root,
            ignore=shutil.ignore_patterns(".git", "site", "__pycache__"),
        )

    def _run(self):
        return run_cli("--selfcheck", "--repo-root", str(self.root))

    def _named(self, name):
        results = foundry_lint.run_selfcheck(self.root)
        return next(r for r in results if r.name == name)

    def test_真實_repo_全部通過_exit_0(self):
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("全部通過", proc.stdout)

    def test_雙入口正文不同步被擋下(self):
        p = self.root / "AGENTS.md"
        p.write_text(p.read_text(encoding="utf-8").replace("## 1. 這個 repo 是什麼",
                                                           "## 1. 這個 repo 是啥"),
                     encoding="utf-8")
        res = self._named("entry-sync")
        self.assertFalse(res.passed)
        self.assertIn("共用正文不一致", res.failures[0])

    def test_缺入口檔被擋下(self):
        (self.root / "AGENTS.md").unlink()
        res = self._named("entry-sync")
        self.assertFalse(res.passed)
        self.assertIn("AGENTS.md 不存在", res.failures[0])

    def test_新增章節沒改_nav_被擋下(self):
        (self.root / "docs" / "handbook" / "09-new.md").write_text(
            "# 9. 新章\n", encoding="utf-8")
        res = self._named("nav-sync")
        self.assertFalse(res.passed)
        self.assertTrue(all("09-new.md" in f for f in res.failures), res.failures)

    def test_腳本裡又內嵌一份_nav_被擋下(self):
        """MYL-55：投影用的 nav 一律轉寫 mkdocs.yml，不准再手寫第二份。"""
        (self.root / "scripts" / "sneaky.sh").write_text(
            'cat > x <<EOF\nnav:\n  - 1. x: 01-first-run.md\nEOF\n', encoding="utf-8")
        res = self._named("nav-sync")
        self.assertFalse(res.passed)
        self.assertTrue(any("第二份 nav" in f for f in res.failures), res.failures)

    def test_腳本只提到章節名而沒有_nav_不算第二份(self):
        """反例：redirect 腳本列舊站頁名（沒有 `nav:`）不該被誤判。"""
        (self.root / "scripts" / "innocent.sh").write_text(
            'PAGES=(01-first-run 02-commands)\n', encoding="utf-8")
        res = self._named("nav-sync")
        self.assertTrue(res.passed, res.failures)

    def test_nav_指向不存在章節被擋下(self):
        (self.root / "docs" / "handbook" / "08-cross-platform.md").unlink()
        res = self._named("nav-sync")
        self.assertFalse(res.passed)
        self.assertTrue(any("指向不存在的章節" in f for f in res.failures))

    def test_中文字面錨點被擋下(self):
        p = self.root / "docs" / "handbook" / "07-workflows.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n[看這節](#總覽)\n",
                     encoding="utf-8")
        res = self._named("anchors")
        self.assertFalse(res.passed)
        self.assertIn("#總覽", res.failures[0])

    def test_未登記的規則_ID_被擋下(self):
        p = self.root / "docs" / "handbook" / "05-troubleshooting.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n違反 `H9` 要退件。\n",
                     encoding="utf-8")
        res = self._named("rule-ids")
        self.assertFalse(res.passed)
        self.assertIn("`H9`", res.failures[0])

    def test_登記了但_protocol_沒定義的_ID_被擋下(self):
        p = self.root / "skills" / "foundry-protocol" / "SKILL.md"
        p.write_text(p.read_text(encoding="utf-8").replace("| `C1`～`C5` |",
                                                           "| `C1`～`C6` |"),
                     encoding="utf-8")
        res = self._named("rule-ids")
        self.assertFalse(res.passed)
        self.assertTrue(any("`C6`" in f and "找不到它的定義" in f
                            for f in res.failures))

    def test_known_drift_自有_ID_不被誤判(self):
        """known-drift 的 L*／S*／R*／X* 前綴未登記於 protocol，應略過而非報錯。"""
        res = self._named("rule-ids")
        self.assertTrue(res.passed, res.failures)

    # ── rule-marks（MYL-47）──────────────────────────────────────────
    #
    # 受測對象是 protocol 本體，所以每個反例都直接改副本裡的 SKILL.md。
    # 這裡刻意連「不該被擋」的兩個形狀也各配一則：漏標與誤殺同樣是缺陷，
    # 而誤殺更難發現——它會逼下一個人把誠實的標記改成假的去迎合檢查。

    def _protocol(self):
        return self.root / "skills" / "foundry-protocol" / "SKILL.md"

    def _sub_protocol(self, old, new):
        p = self._protocol()
        text = p.read_text(encoding="utf-8")
        self.assertIn(old, text, "反例的錨點字串已不在 protocol 裡，測試要跟著改")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_違反行沒有標記被擋下(self):
        """增訂時漏標——本檢查存在的主要理由。"""
        self._sub_protocol(
            "要退回的不只是一條設定。`【自律】`", "要退回的不只是一條設定。")
        res = self._named("rule-marks")
        self.assertFalse(res.passed)
        self.assertTrue(any("沒有以標記收尾" in f for f in res.failures),
                        res.failures)

    def test_標記順序顛倒的合併形被擋下(self):
        """放行的是字面相同的三種，不是自由組合。

        錨點要帶前文：`replace(..., 1)` 換的是第一個命中，而合併形第一次出現
        是在圖例表裡——只寫標記本身會改到圖例，測到的變成另一項失敗。

        這則同時釘住「不能只比對行尾後綴」：顛倒後的尾巴正好是合法的
        `【自律】`，用 `endswith` 判會放行，而它讀起來剛好少掉機械那一半。
        """
        self._sub_protocol("那點失誤。`【自律】`＋`【機械】`",
                           "那點失誤。`【機械】`＋`【自律】`")
        res = self._named("rule-marks")
        self.assertFalse(res.passed)
        self.assertTrue(any("不是合法字面" in f for f in res.failures),
                        res.failures)

    def test_第三種標記值被擋下(self):
        """「有沒有工具會擋」沒有中間態，`【半機械】` 之類的值一律擋。"""
        self._sub_protocol("要退回的不只是一條設定。`【自律】`",
                           "要退回的不只是一條設定。`【半機械】`")
        res = self._named("rule-marks")
        self.assertFalse(res.passed)
        self.assertTrue(any("第三種標記值" in f and "半機械" in f
                            for f in res.failures), res.failures)

    def test_圖例漏列合法結尾被擋下(self):
        """圖例與程式常數必須是同一份——本單就是被這一項抓出來的。"""
        self._sub_protocol(
            "| `【自律】`＋`【機械】` | 該小節含多條規則、後盾程度不同", "| ~~ | ")
        res = self._named("rule-marks")
        self.assertFalse(res.passed)
        self.assertTrue(any("圖例沒有列出合法結尾" in f for f in res.failures),
                        res.failures)

    def test_違反文正文引用另一個標記不被誤判(self):
        """§7 兩段違反文在敘述裡引用 `【自律】`，收尾卻是 `【機械】`。

        用 contains 判會把它們誤殺，所以只認行尾。
        """
        text = self._protocol().read_text(encoding="utf-8")
        self.assertIn("從 MYL-40 標記表上的 `【自律】` 轉為機械攔截", text,
                      "這則反例的前提沒了——protocol 已無「敘述裡引用標記」的違反行")
        self.assertTrue(self._named("rule-marks").passed)

    def test_沒有違反行的小節不被要求補標記(self):
        """哪些小節該配後果是編輯判斷，不歸機械管（第 1～3 節整節留白）。"""
        res = self._named("rule-marks")
        self.assertTrue(res.passed, res.failures)
        self.assertIn("違反段", res.summary)

    # ── 界定前綴（MYL-99）─────────────────────────────────────────────
    #
    # 覆蓋判定原本是 `startswith("**違反：**")`，於是三種寫法悄悄掉出覆蓋：
    # 規則 ID 冠在前（`` **`O4` 違反：** ``）、限定語塞進粗體內
    # （`**違反（本節矩陣整體）：**`）、以及寫成清單項目（`- **違反：**`）。
    # 前兩種是 MYL-79 第 1 輪的實際漏網——覆蓋數從 26 掉到 25，而檢查照樣綠。
    #
    # 這幾則一律比「覆蓋數有沒有變」而不寫死數字：數字會隨 protocol 增訂漂掉，
    # 寫死只會養出一則每次增訂都要順手改的測試，而改它的人不會知道自己在放行什麼。

    _MARK_COUNT_RE = re.compile(r"（(\d+) 行違反段）")

    def _mark_count(self):
        res = self._named("rule-marks")
        m = self._MARK_COUNT_RE.search(res.summary)
        self.assertIsNotNone(m, f"覆蓋數不在 summary 裡了：{res.summary}")
        return int(m.group(1))

    def test_規則_ID_冠在違反前照樣計入覆蓋(self):
        before = self._mark_count()
        self._sub_protocol("**違反：**（`O4`）沒有這條時",
                           "**`O4` 違反：**沒有這條時")
        self.assertEqual(self._mark_count(), before,
                         "規則 ID 冠到「違反」前面之後，那一行掉出覆蓋了")

    def test_限定語塞進粗體內照樣計入覆蓋(self):
        before = self._mark_count()
        self._sub_protocol("**違反：**（本節矩陣整體）兩個方向",
                           "**違反（本節矩陣整體）：**兩個方向")
        self.assertEqual(self._mark_count(), before,
                         "限定語移進粗體之後，那一行掉出覆蓋了")

    def test_帶界定前綴的違反行漏標被擋下(self):
        """覆蓋數只是徵狀，這則才是後果：改寬之前，這個形狀漏標沒有人會出聲。"""
        self._sub_protocol("**違反：**（`O4`）沒有這條時",
                           "**`O4` 違反：**沒有這條時")
        self._sub_protocol("是每天都會踩到。`【自律】`", "是每天都會踩到。")
        res = self._named("rule-marks")
        self.assertFalse(res.passed)
        self.assertTrue(any("沒有以標記收尾" in f for f in res.failures),
                        res.failures)

    def test_清單項目形式的違反行漏標被擋下(self):
        """§9 有一段違反行寫成 `- **違反：**`，行首是項目符號而不是 `**`。"""
        self._sub_protocol(
            "於是它會慢慢漂到沒有人說得清它該做什麼。`【自律】`",
            "於是它會慢慢漂到沒有人說得清它該做什麼。")
        res = self._named("rule-marks")
        self.assertFalse(res.passed)
        self.assertTrue(any("沒有以標記收尾" in f for f in res.failures),
                        res.failures)

    def test_散文裡的粗體違反句不被計入(self):
        """放寬的是**界定前綴**，不是「粗體裡出現『違反：』就算」。

        圖例節本來就有一行 `- **沒有「違反：」行的小節…**`，把這類句子算進
        覆蓋，等於要求一段散文去補標記——誤殺比漏標更難救，它會逼下一個人
        把誠實的敘述改成假的標記去迎合檢查。
        """
        before = self._mark_count()
        p = self._protocol()
        p.write_text(
            p.read_text(encoding="utf-8")
            + "\n- **本節不談違反：**這是散文，不是後果段。\n", encoding="utf-8")
        self.assertEqual(self._mark_count(), before)
        self.assertTrue(self._named("rule-marks").passed)

    def test_protocol_不存在被擋下(self):
        self._protocol().unlink()
        res = self._named("rule-marks")
        self.assertFalse(res.passed)
        self.assertIn("不存在", res.failures[0])

    def _big(self, rel):
        """在副本裡放一個超過門檻的 .md，回傳它的 repo 相對路徑。"""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * (foundry_lint.BIG_FILE_BYTES + 1), encoding="utf-8")
        return rel

    def test_大檔沒列進入口檔清單被擋下(self):
        self._big("skills/foundry-plenty/SKILL.md")
        res = self._named("big-files")
        self.assertFalse(res.passed)
        self.assertTrue(any("skills/foundry-plenty/SKILL.md" in f and "沒有列它" in f
                            for f in res.failures))

    def test_清單列了不存在的路徑被擋下(self):
        (self.root / "docs" / "pilot" / "pilot-log.md").unlink()
        res = self._named("big-files")
        self.assertFalse(res.passed)
        self.assertTrue(any("docs/pilot/pilot-log.md" in f and "路徑不存在" in f
                            for f in res.failures))

    def test_門檻以下的檔案不必列(self):
        p = self.root / "skills" / "foundry-tiny.md"
        p.write_text("x" * (foundry_lint.BIG_FILE_BYTES - 1), encoding="utf-8")
        self.assertTrue(self._named("big-files").passed)

    def test_docs_features_不納入掃描(self):
        """各模組交付物不該逼入口檔隨模組數膨脹。"""
        self._big("docs/features/某模組/HLD.md")
        self.assertTrue(self._named("big-files").passed)

    def test_缺少大檔清單標記被擋下(self):
        p = self.root / "CLAUDE.md"
        p.write_text(p.read_text(encoding="utf-8").replace(foundry_lint.BIG_BEGIN, ""),
                     encoding="utf-8")
        res = self._named("big-files")
        self.assertFalse(res.passed)
        self.assertTrue(any("CLAUDE.md 缺少" in f for f in res.failures))

    def test_門檻常數與入口檔散文不一致被擋下(self):
        """改了 BIG_FILE_BYTES 卻沒改那句話，程式與散文就各說各話。"""
        p = self.root / "CLAUDE.md"
        kb = foundry_lint.BIG_FILE_BYTES // 1024
        p.write_text(p.read_text(encoding="utf-8").replace(f"{kb}KB", f"{kb + 4}KB"),
                     encoding="utf-8")
        res = self._named("big-files")
        self.assertFalse(res.passed)
        self.assertTrue(any("門檻" in f and "對不上" in f for f in res.failures))

    def test_相對連結指向不存在的檔案被擋下(self):
        """MYL-41 的原始缺陷：用裸章節檔名連手冊，從所在目錄解析會落空。"""
        p = self.root / "docs" / "publish-reviews" / "MYL-24.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n見 [第 3 章](03-workflow.md)。\n",
                     encoding="utf-8")
        res = self._named("internal-links")
        self.assertFalse(res.passed)
        self.assertEqual(len(res.failures), 1)
        self.assertIn("docs/publish-reviews/MYL-24.md", res.failures[0])
        self.assertIn("docs/publish-reviews/03-workflow.md", res.failures[0])

    def test_正確的相對連結不誤報(self):
        p = self.root / "docs" / "publish-reviews" / "MYL-24.md"
        p.write_text(
            p.read_text(encoding="utf-8")
            + "\n見 [第 3 章](../handbook/03-workflow.md)。\n",
            encoding="utf-8",
        )
        self.assertTrue(self._named("internal-links").passed)

    def test_錨點與外部_URL_不誤報(self):
        p = self.root / "docs" / "handbook" / "05-troubleshooting.md"
        p.write_text(
            p.read_text(encoding="utf-8")
            + "\n[同頁](#1)、[站外](https://example.com/x.md)、"
            "[信](mailto:a@b.c)、[協定相對](//cdn.example.com/y.md)\n",
            encoding="utf-8",
        )
        self.assertTrue(self._named("internal-links").passed)

    def test_反引號與圍欄內的連結語法不掃(self):
        """散文裡的路徑示例不該誤報（MYL-39 計畫 v3 §7 明確不做）。"""
        p = self.root / "docs" / "handbook" / "05-troubleshooting.md"
        p.write_text(
            p.read_text(encoding="utf-8")
            + "\n寫法是 `[第 3 章](03-workflow.md)` 這樣。\n"
            "\n```markdown\n[範例](完全不存在.md)\n```\n",
            encoding="utf-8",
        )
        self.assertTrue(self._named("internal-links").passed)

    def test_帶錨點的相對連結只驗檔案存在(self):
        p = self.root / "docs" / "handbook" / "05-troubleshooting.md"
        p.write_text(
            p.read_text(encoding="utf-8")
            + "\n[在](03-workflow.md#隨便一個不存在的錨點)、[不在](沒這檔.md#1)\n",
            encoding="utf-8",
        )
        res = self._named("internal-links")
        self.assertFalse(res.passed)
        self.assertEqual(len(res.failures), 1)
        self.assertIn("沒這檔.md", res.failures[0])

    def test_指向目錄的相對連結算存在(self):
        p = self.root / "CLAUDE.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n[手冊](docs/handbook/)\n",
                     encoding="utf-8")
        self.assertTrue(self._named("internal-links").passed)

    def test_json_格式可解析且與_exit_code_一致(self):
        (self.root / "AGENTS.md").unlink()
        proc = run_cli("--selfcheck", "--repo-root", str(self.root),
                       "--format", "json")
        self.assertEqual(proc.returncode, 1)
        data = json.loads(proc.stdout)
        self.assertFalse(data["passed"])
        self.assertEqual({c["name"] for c in data["checks"]},
                         {"entry-sync", "nav-sync", "anchors", "rule-ids",
                          "rule-marks", "big-files", "internal-links",
                          "version-shape", "table-shape", "config-schema",
                          "org-sync", "handbook-stamp", "init-copy-list",
                          "selfcheck-names", "mirror-recon"})

    def test_selfcheck_不需要_type_與_file(self):
        proc = self._run()
        self.assertEqual(proc.stderr, "")

    def test_手冊章節少了戳記行被擋下(self):
        """副本沒帶 .git，落後與否驗不了，但字面缺漏照樣要擋。"""
        p = self.root / "docs" / "handbook" / "03-workflow.md"
        kept = [ln for ln in p.read_text(encoding="utf-8").splitlines()
                if not foundry_lint.STAMP_RE.match(ln)]
        p.write_text("\n".join(kept) + "\n", encoding="utf-8")
        res = self._named("handbook-stamp")
        self.assertFalse(res.passed)
        self.assertTrue(any("03-workflow.md" in f and "第一個非空行" in f
                            for f in res.failures), res.failures)

    # ── init-copy-list（MYL-86）─────────────────────────────────────────
    #
    # 反例都改副本的 `Makefile`，因為漂移的實際方向就是那個：兩次都是往
    # Makefile 加了一行、沒回頭改 foundry-init 的複製清單。

    def _append_makefile(self, text):
        p = self.root / "Makefile"
        p.write_text(p.read_text(encoding="utf-8") + text, encoding="utf-8")

    def test_test_target_多一個不在複製清單的目錄被擋下(self):
        """本檢查存在的主因：`test:` 加了一行、清單沒跟。"""
        self._append_makefile(
            "\ntest-extra:\n\t@python3 -m unittest discover tools/brand-new\n")
        res = self._named("init-copy-list")
        self.assertFalse(res.passed)
        self.assertTrue(any("tools/brand-new/" in f and "複製清單沒有列它" in f
                            for f in res.failures), res.failures)

    def test_非_test_target_引用的目錄同樣被擋下(self):
        """AC3 選了「掃整份 Makefile」，`providers`／`browser` 那類也算數。"""
        self._append_makefile("\nprobe:\n\t@python3 tools/only-probe/run.py\n")
        res = self._named("init-copy-list")
        self.assertFalse(res.passed)
        self.assertTrue(any("tools/only-probe/" in f for f in res.failures),
                        res.failures)

    def test_只出現在註解裡的目錄不誤報(self):
        """註解提到不等於會跑到；誤殺會逼下一個人把說明刪掉去迎合檢查。"""
        self._append_makefile("\n# 早年這裡還有 tools/retired-thing/，已移除\n")
        self.assertTrue(self._named("init-copy-list").passed)

    def test_複製清單的錨點漂掉時報錯而不是放行(self):
        """找不到清單就等於沒比對——這種時候印 ✅ 比印 ❌ 危險得多。"""
        p = self.root / "skills" / "foundry-init" / "SKILL.md"
        text = p.read_text(encoding="utf-8")
        self.assertIn("\n3. 複製流程檔到", text,
                      "反例的錨點字串已不在 SKILL.md 裡，測試要跟著改")
        p.write_text(text.replace("\n3. 複製流程檔到", "\n三、複製流程檔到", 1),
                     encoding="utf-8")
        res = self._named("init-copy-list")
        self.assertFalse(res.passed)
        self.assertTrue(any("錨點漂了" in f for f in res.failures), res.failures)

    def test_目錄被移到不複製那一行就不算列過(self):
        """CR R2 的反證：不截斷的話這個情境印綠，而目標專案的 make check 會掛。

        Makefile 原封不動，只把 `tools/publish-docs/` 從複製項改寫到那條反向的
        `- 不複製：` 上——複製清單的字面還在，但語意已經反過來了。
        """
        p = self.root / "skills" / "foundry-init" / "SKILL.md"
        text = p.read_text(encoding="utf-8")
        kept = [ln for ln in text.splitlines()
                if "`tools/publish-docs/`（全目錄）" not in ln]
        self.assertEqual(len(kept), len(text.splitlines()) - 1,
                         "反例預期只砍掉一行；清單寫法變了，測試要跟著改")
        moved = "\n".join(kept).replace(
            "   - 不複製：`skills/foundry-init/`",
            "   - 不複製：`skills/foundry-init/`、`tools/publish-docs/`", 1)
        self.assertIn("不複製：`skills/foundry-init/`、`tools/publish-docs/`", moved,
                      "反例的「不複製」那行已不是這個寫法，測試要跟著改")
        p.write_text(moved + "\n", encoding="utf-8")
        res = self._named("init-copy-list")
        self.assertFalse(res.passed)
        self.assertTrue(any("tools/publish-docs/" in f and "複製清單沒有列它" in f
                            for f in res.failures), res.failures)

    def test_不複製那行以前的項目照樣算數(self):
        """截斷點不能砍過頭，也不能被散文裡的「不複製」提前觸發。

        現行清單最後一條複製項（`skills/roles/`）的說明文字裡就有一句
        「照舊不複製。」——截斷條件是**行首**的 `- 不複製：`，所以那句不算數。

        真被它提前截斷時的失效方向是**靜默綠，不是假紅**（CR R3 實測）：四個
        `tools/` 項在 SKILL.md 都排在那句散文**之前**，一個都掉不出區塊，自檢
        照樣印 ✅「清單列 4 個」。實際擋住它的是下面那條
        `assertIn("照舊不複製", block)`——放寬正則時只有它會紅。
        所以看到它紅而自檢是綠的，別把它當誤報刪掉：綠的那邊才是壞的。
        """
        self.assertTrue(self._named("init-copy-list").passed)
        block, why = foundry_lint.init_copy_list_block(
            (self.root / "skills" / "foundry-init" / "SKILL.md")
            .read_text(encoding="utf-8"))
        self.assertEqual(why, "")
        self.assertIsNone(foundry_lint.INIT_EXCLUDE_RE.search(block))
        self.assertIn("照舊不複製", block, "散文裡那句「不複製」不該把區塊切掉")
        self.assertEqual(set(foundry_lint.INIT_LISTED_RE.findall(block)),
                         set(foundry_lint.makefile_tools_dirs(
                             (self.root / "Makefile").read_text(encoding="utf-8"))))

    def test_清單列得比_Makefile_多不算失敗(self):
        """反方向不管：清單有 `templates/` 那類與 Makefile 無關的項目。"""
        p = self.root / "Makefile"
        p.write_text(
            p.read_text(encoding="utf-8").replace(
                "\t@python3 -m unittest discover tools/publish-docs\n", ""),
            encoding="utf-8")
        self.assertTrue(self._named("init-copy-list").passed)

    # ── selfcheck-names（MYL-89）────────────────────────────────────────
    #
    # 反例都改副本的四個抄寫點，因為漂移的實際方向就是那個：新增一項檢查、
    # 四處忘了改。⚠️ **本檢查上線當天四處就是同步的**，所以「跑起來綠」證明不了
    # 它擋得住任何東西——能證明的只有下面這幾個反例。

    #: 四處各自的分隔符不同（`Makefile` 與入口檔是「、」，hook 名是「／」）。
    NAME_SITES = (
        ("Makefile", "、init 複製清單"),
        (".pre-commit-config.yaml", "／init 複製清單"),
        ("CLAUDE.md", "、init 複製清單"),
        ("AGENTS.md", "、init 複製清單"),
    )

    def _mutate_site(self, rel, old, new):
        p = self.root / rel
        text = p.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1,
                         f"{rel} 裡「{old}」不是剛好一處，反例的假設變了，測試要跟著改")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_四處任一漏抄一項檢查名都被擋下(self):
        """AC1：訊息要點名是哪個檔案漏了哪一項，不能只說「對不上」。"""
        for rel, listed in self.NAME_SITES:
            with self.subTest(site=rel):
                p = self.root / rel
                original = p.read_text(encoding="utf-8")
                self._mutate_site(rel, listed, "")
                res = self._named("selfcheck-names")
                p.write_text(original, encoding="utf-8")  # 一次只讓一處是壞的
                self.assertFalse(res.passed)
                self.assertTrue(
                    any(rel in f and "init-copy-list" in f and "init 複製清單" in f
                        for f in res.failures), res.failures)

    def test_四處多寫一項對不到的檢查名被擋下(self):
        """多寫的那一項會讓人去找一個不存在的檢查。"""
        self._mutate_site("Makefile", "、init 複製清單", "、init 複製清單、幻覺檢查")
        res = self._named("selfcheck-names")
        self.assertFalse(res.passed)
        self.assertTrue(any("Makefile" in f and "幻覺檢查" in f for f in res.failures),
                        res.failures)

    def test_錯字同時報成漏一項與多一項(self):
        """錯字是漂移最常見的形狀，而它在集合比對下必然兩邊都響。"""
        self._mutate_site("AGENTS.md", "、鏡像對帳", "、鏡像對賬")
        res = self._named("selfcheck-names")
        self.assertFalse(res.passed)
        self.assertTrue(any("mirror-recon" in f and "漏了" in f for f in res.failures),
                        res.failures)
        self.assertTrue(any("鏡像對賬" in f and "多了" in f for f in res.failures),
                        res.failures)

    def test_抄寫點的錨點漂掉時報錯而不是放行(self):
        """找不到那一行就等於沒比對——這種時候印 ✅ 比印 ❌ 危險得多。"""
        self._mutate_site("Makefile", "selfcheck: ## repo 規範自檢：",
                          "selfcheck: ## 本 repo 的規範自檢：")
        res = self._named("selfcheck-names")
        self.assertFalse(res.passed)
        self.assertTrue(any("Makefile" in f and "錨點漂了" in f for f in res.failures),
                        res.failures)

    def test_抄寫點整份不見時報錯而不是放行(self):
        """跳過判準只看 `is_rule_repo()`：規則本體少了一處抄寫點照樣紅。

        若把判準寫成「那一行在不在」，這裡會從 ❌ 變成 ⏭——那是把閘門放鬆。
        """
        (self.root / ".pre-commit-config.yaml").unlink()
        res = self._named("selfcheck-names")
        self.assertFalse(res.passed)
        self.assertFalse(res.skipped, "規則本體缺抄寫點時被跳過")
        self.assertTrue(any(".pre-commit-config.yaml" in f and "不存在" in f
                            for f in res.failures), res.failures)

    def test_登記表少一項時擋下(self):
        """把登記表自己綁死在 `SELFCHECKS` 上——少了這條它就只是第五份手抄。"""
        labels = {k: v for k, v in foundry_lint.SELFCHECK_LABELS.items()
                  if k != "mirror-recon"}
        with mock.patch.object(foundry_lint, "SELFCHECK_LABELS", labels):
            res = self._named("selfcheck-names")
        self.assertFalse(res.passed)
        self.assertTrue(any("mirror-recon" in f and "SELFCHECK_LABELS` 沒有它" in f
                            for f in res.failures), res.failures)

    def test_登記表多一項時擋下(self):
        """`staged-handbook-sync` 不在 `SELFCHECKS`（只在 pre-commit 跑）。

        列進登記表就會逼四處寫上一項 `--selfcheck` 根本不跑的東西。
        """
        labels = dict(foundry_lint.SELFCHECK_LABELS)
        labels["staged-handbook-sync"] = "層 0 觸發器"
        with mock.patch.object(foundry_lint, "SELFCHECK_LABELS", labels):
            res = self._named("selfcheck-names")
        self.assertFalse(res.passed)
        self.assertTrue(any("staged-handbook-sync" in f and "沒有註冊它" in f
                            for f in res.failures), res.failures)

    def test_標籤互為子字串時擋下(self):
        """護欄：比對走包含關係，標籤互相包含會讓漏抄**靜默通過**。

        現行 14 項互不包含，所以這個反例得自己造一個——未來新增一項標籤叫
        「手冊」時，四處只要寫了「手冊戳記」就會把它餵飽，而漏抄看不出來。
        """
        labels = dict(foundry_lint.SELFCHECK_LABELS)
        labels["handbook-stamp"] = "手冊"
        with mock.patch.object(foundry_lint, "SELFCHECK_LABELS", labels):
            res = self._named("selfcheck-names")
        self.assertFalse(res.passed)
        self.assertTrue(any("子字串" in f and "靜默通過" in f for f in res.failures),
                        res.failures)

    def test_靜態取名與實際跑出來的名稱一致(self):
        """取名走原始碼字面量而不是把 13 項跑一遍，所以要有人釘住兩者相等。

        任何一個 check 函式改成非字面量建 `SelfcheckResult`，這裡會先紅。
        """
        static = [name for _, name in foundry_lint.selfcheck_registered_names()]
        actual = [r.name for r in foundry_lint.run_selfcheck(self.root)]
        self.assertEqual(static, actual)
        self.assertEqual(list(foundry_lint.SELFCHECK_LABELS), actual,
                         "登記表的順序也照 `SELFCHECKS`，四處才好照抄")

    def test_本檢查自己也列在四處(self):
        """AC5：新增自檢本身要同步進那四處，本單是自己的第一個使用者。"""
        for rel, _ in self.NAME_SITES:
            with self.subTest(site=rel):
                self.assertIn("自檢名稱清單",
                              (self.root / rel).read_text(encoding="utf-8"))


class TargetProjectSkipTest(RepoCopyTestCase):
    """MYL-87：`foundry-init` 產出的目標專案不該一跑 `make check` 就掛。

    目標專案＝拿真實 repo 的副本，刪掉 `skills/foundry-init/`（複製清單明寫不複製）
    與 `docs/handbook/`（init 不產手冊）。**每一項跳過都配一個「該紅的情境仍然紅」
    的反例**——跳過條件寫錯的失效方向是靜默放行，那正是這幾個測試要擋的。
    """

    HANDBOOK_CHECKS = ("nav-sync", "anchors", "handbook-stamp")

    def _named(self, name):
        return next(r for r in foundry_lint.run_selfcheck(self.root) if r.name == name)

    def _make_target_project(self):
        """把 repo 副本改造成「剛 init 完的目標專案」。"""
        shutil.rmtree(self.root / foundry_lint.RULE_REPO_MARKER_REL)
        shutil.rmtree(self.root / "docs" / "handbook")
        self._fill_big_files()

    def _fill_big_files(self):
        """照 foundry-init 步驟 2.5 用 `--big-files-list` 的輸出填兩份入口檔的大檔表。"""
        rows = foundry_lint.render_big_files_list(self.root)
        block = (f"{foundry_lint.BIG_BEGIN}\n"
                 "每個 12KB 以上的 .md 都必須列在下表。\n\n"
                 "| 檔案 | 通常只需要哪一部分 |\n| --- | --- |\n"
                 f"{rows}\n")
        for name in ("CLAUDE.md", "AGENTS.md"):
            text = (self.root / name).read_text(encoding="utf-8")
            head, _, rest = text.partition(foundry_lint.BIG_BEGIN)
            _, _, tail = rest.partition(foundry_lint.BIG_END)
            self.write(name, head + block + foundry_lint.BIG_END + tail)

    # ── 判準②：跳過看得出來是跳過，且不擋 commit ──────────────────────
    def test_目標專案四項印跳過而不是失敗(self):
        self._make_target_project()
        for name in self.HANDBOOK_CHECKS + ("init-copy-list", "selfcheck-names"):
            with self.subTest(check=name):
                res = self._named(name)
                self.assertTrue(res.passed, res.failures)
                self.assertTrue(res.skipped, f"{name} 沒有跳過理由＝被印成 ✅")

    def test_目標專案的跳過會印出_跳過_字樣(self):
        """⏭ 與理由都要出現在輸出裡；印成 ✅ 會讓人以為查過了。"""
        self._make_target_project()
        text = foundry_lint.render_selfcheck_text(foundry_lint.run_selfcheck(self.root))
        self.assertIn("⏭ [nav-sync]", text)
        self.assertIn("跳過（未實際檢查）", text)
        self.assertIn("項跳過未檢查", text)

    # ── 判準①：本 repo 的同一項檢查不因此變鬆 ────────────────────────
    def test_規則本體整個手冊不見時三項仍然紅(self):
        """判準①的守門測試：只用「手冊在不在」當條件就會在這裡從 ❌ 變 ⏭。"""
        shutil.rmtree(self.root / "docs" / "handbook")
        for name in self.HANDBOOK_CHECKS:
            with self.subTest(check=name):
                res = self._named(name)
                self.assertFalse(res.passed, f"{name} 在規則本體缺手冊時被放行")
                self.assertFalse(res.skipped, f"{name} 在規則本體被跳過")

    def test_規則本體少一章時_nav_sync_仍然紅(self):
        (self.root / "docs" / "handbook" / "07-workflows.md").unlink()
        res = self._named("nav-sync")
        self.assertFalse(res.passed)
        self.assertTrue(any("07-workflows.md" in f for f in res.failures), res.failures)

    def test_規則本體缺_init_skill_檔時_init_copy_list_仍然紅(self):
        """判準旗標是**目錄**，對照端是檔案：目錄還在就不准跳過。"""
        (self.root / foundry_lint.INIT_SKILL_REL).unlink()
        res = self._named("init-copy-list")
        self.assertFalse(res.passed)
        self.assertFalse(res.skipped)
        self.assertIn("對照端沒了", res.failures[0])

    # ── 第二層條件：目標專案自建手冊後就回到照驗 ──────────────────────
    def test_目標專案自建手冊與_nav_對不上時仍然紅(self):
        """少了第二層條件，這個情境會被靜默放行。"""
        self._make_target_project()
        self._build_own_handbook()
        res = self._named("nav-sync")
        self.assertFalse(res.passed)
        self.assertFalse(res.skipped)

    def _build_own_handbook(self, *names):
        """目標專案自己建一份手冊；`names` 未給時全是它自己的章名。"""
        d = self.root / "docs" / "handbook"
        d.mkdir(parents=True, exist_ok=True)
        for name in (names or ("01-first-run.md",)):
            (d / name).write_text(f"# {name}\n", encoding="utf-8")

    # ── MYL-92：`handbook-stamp` 的第 2 層條件與另外兩項分家 ───────────
    def test_目標專案自建手冊後_handbook_stamp_仍跳過(self):
        """`STAMPED_CHAPTERS` 是 agent-foundry 自家四章，目標專案沒理由擁有。

        分家前這裡吐四條「章節不存在」，而 `foundry-init` 步驟 4 同時要求零紅字
        ——把導入者指去修一個修不掉的紅字。
        """
        self._make_target_project()
        self._build_own_handbook()
        res = self._named("handbook-stamp")
        self.assertTrue(res.passed, res.failures)
        self.assertTrue(res.skipped, "沒有跳過理由＝被印成 ✅")

    def test_分家沒有把_nav_sync_與_anchors_一起放寬(self):
        """這兩項在這個情境**應該照驗**——對照端是目標專案自己的 `mkdocs.yml`
        與章內錨點，報出來的紅是真缺陷、也修得掉。

        ⚠️ **這條擋的不是「把新條件寫進共用函式」**：實測過，那樣改不會弄壞這兩項，
        因為它們是在 `docs/handbook/` 不存在時**才**去問那支函式，而目錄不存在時
        四章必然也不在。它擋的是下一步——有人把跳過判斷上移到檢查最前面（統一成
        `handbook-stamp` 的寫法）。那個等價一上移就沒了，而在本條之前不會有測試紅。
        """
        self._make_target_project()
        self._build_own_handbook()
        for name in ("nav-sync", "anchors"):
            with self.subTest(check=name):
                self.assertFalse(self._named(name).skipped,
                                 f"{name} 被 handbook-stamp 的新判準連帶放寬了")

    def test_目標專案複製了掛戳記的章節之一就回到照驗(self):
        """真帶了那幾章就得把戳記維護齊全，缺的三章報紅是對的。"""
        self._make_target_project()
        kept, *dropped = foundry_lint.STAMPED_CHAPTERS
        self._build_own_handbook("01-first-run.md", kept)
        res = self._named("handbook-stamp")
        self.assertFalse(res.passed, "帶了掛戳記的章節還跳過")
        self.assertFalse(res.skipped)
        self.assertTrue(any(kept in f and "第一個非空行" in f for f in res.failures),
                        res.failures)
        for name in dropped:
            self.assertTrue(any(name in f and "少了一份" in f for f in res.failures),
                            res.failures)

    # ── AC4：`big-files` 沒有被關掉 ─────────────────────────────────
    def test_目標專案漏列達門檻檔案仍然紅(self):
        self._make_target_project()
        dropped = f"| `{foundry_lint.PROTOCOL_REL}` |"
        self.assertIn(dropped, (self.root / "CLAUDE.md").read_text(encoding="utf-8"))
        for name in ("CLAUDE.md", "AGENTS.md"):
            body = (self.root / name).read_text(encoding="utf-8")
            self.write(name, "\n".join(ln for ln in body.splitlines()
                                       if not ln.startswith(dropped)) + "\n")
        res = self._named("big-files")
        self.assertFalse(res.passed)
        self.assertTrue(any(foundry_lint.PROTOCOL_REL in f for f in res.failures),
                        res.failures)

    def test_big_files_list_的輸出貼回入口檔就轉綠(self):
        self._make_target_project()
        res = self._named("big-files")
        self.assertTrue(res.passed, res.failures)
        self.assertFalse(res.skipped, "big-files 不該跳過——它在目標專案一樣成立")

    def test_big_files_list_印的是掃描結果本身(self):
        """產生器與檢查共用 `scan_big_files()`，兩者必然相等——不是各掃各的。"""
        rows = foundry_lint.render_big_files_list(self.root).splitlines()
        listed = [foundry_lint.MD_PATH_RE.search(r).group(1) for r in rows]
        self.assertEqual(listed, foundry_lint.scan_big_files(self.root))
        self.assertTrue(all(foundry_lint.BIG_FILES_TODO in r for r in rows))

    def test_big_files_list_是獨立模式_不需要_type(self):
        proc = run_cli("--big-files-list", "--repo-root", str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(f"`{foundry_lint.PROTOCOL_REL}`", proc.stdout)

    # ── 互鎖：判準吊在複製清單那一行上 ───────────────────────────────
    def test_複製清單那一行留有回指本檔的註解(self):
        """MYL-87 的雙向鎖：那一行改了要先看 `RULE_REPO_MARKER_REL`。

        沒有這個測試，互指的註解被刪掉不會有任何地方報錯，判準就懸空了。
        """
        text = (self.root / foundry_lint.INIT_SKILL_REL).read_text(encoding="utf-8")
        block, why = foundry_lint.init_copy_list_block(text)
        self.assertEqual(why, "")
        # 「不複製」那一行被 `init_copy_list_block` 截掉，所以往它後面找。
        tail = text[text.index(block) + len(block):]
        self.assertIn("RULE_REPO_MARKER_REL", tail)


class PortableSuiteInTargetProjectTest(unittest.TestCase):
    """可攜的那半套測試，在目標專案形狀的 repo 上必須全綠——`make test` 的每一段。

    這是「規則本體專屬 vs 可攜」那條界線的**機械後盾**。少了它，日後把規則本體專屬
    的測試寫進可攜檔不會有任何地方報錯——紅字會出現在**別人的專案**裡，正是 MYL-86
    記載過、漂了兩次沒人看見的形狀（`tools/browser-probe/` 與 `tools/publish-docs/`
    都是往 Makefile 加了一行沒回頭改複製清單，到 MYL-78 才被發現）。

    **不會遞迴**：帶標記的檔案（含本檔）在構造出來的 root 裡已經被刪掉，
    子程序 discover 到的只有可攜那半套。
    """

    #: 規則本體專屬測試檔的標記。**不用手維護清單**——手維護的那種正是 MYL-86 的
    #: 病灶。要新增一個這種檔案，把這行字串放進檔首註解即可，三個地方
    #: （本測試、`build-fixture`／init 的複製動作、複製清單的敘述）自動跟上。
    RULE_REPO_ONLY_MARK = "FOUNDRY:RULE-REPO-ONLY"

    #: 目標專案不會有的頂層路徑，依 `skills/foundry-init/SKILL.md` §2 第 3 點與 §2.5——
    #: 清單沒列到的就不會被複製過去。`docs/` 是關鍵的那一個（規則本體專屬那批測試
    #: 要的素材全在裡面），其餘幾條是為了讓形狀真的接近目標專案。
    #: ⚠️ 這份仍是**近似**，權威是複製清單本身；最終證據是照清單手動組 fixture 跑
    #: 整條 `make check`（MYL-91 AC2）。但近似要往「比真實目標專案更貧瘠」的方向偏，
    #: 偏鬆的代價是實測過的：只刪頭四條時，`skills/foundry-adopt/` 與「讀真設定檔的
    #: **值**」兩種寫錯邊都能逃過守門（MYL-91 第 1 輪審查瑕疵 2）。
    #: `.gitignore` 刻意不列——複製清單沒帶它，但目標專案幾乎一定有自己那份。
    ABSENT_IN_TARGET = ("docs", "scripts", ".github", "mkdocs.yml",
                        "README.md", ".claude", ".mcp.json",
                        "skills/foundry-adopt",
                        foundry_lint.RULE_REPO_MARKER_REL)

    #: 目標專案形狀的 `.foundry/config.yml`：**存在但值不一樣**，這是 `ABSENT_IN_TARGET`
    #: 表達不了的那一格。init 產出的是這個形狀（§2 第 2 點）——每一欄都刻意選成與
    #: agent-foundry 自己那份不同的合法值，好讓「斷言真設定檔的值」在守門就報紅。
    TARGET_CONFIG = (
        "# 目標專案形狀的最小設定，由 PortableSuiteInTargetProjectTest 產生。\n"
        "foundry: 2\n"
        "devtools_platform: local-md\n"
        "ai_platform: codex\n"
        "platform_options:\n"
        "  local-md:\n"
        "    id_prefix: FND\n"
        "gates:\n"
        "  spec_approval: user\n"
        "  design_approval:\n"
        "    approver: user\n"
        "  external_actions: user\n"
        "push:\n"
        "  branch_push: user\n"
        "  main_push: user\n"
    )
    TARGET_AI_PLATFORM = "codex"

    def _marked_files(self, root):
        """`root` 底下所有帶標記的測試檔（相對路徑）。"""
        return sorted(
            p.relative_to(root).as_posix()
            for p in (root / "tools").rglob("test_*.py")
            if self.RULE_REPO_ONLY_MARK in p.read_text(encoding="utf-8")
        )

    def _tool_dirs(self, root):
        """`make test` 會逐一 discover 的那幾個目錄——直接問 Makefile，不另抄一份。"""
        return foundry_lint.makefile_tools_dirs(
            (root / foundry_lint.MAKEFILE_REL).read_text(encoding="utf-8"))

    def _retarget_foundry_dir(self, root):
        """`.foundry/` 換成目標專案自己的宣告——它是**存在但值不同**的那一類。

        刪掉不對（目標專案一定有 `config.yml`，`org-sync`／`mirror-recon` 都要讀它），
        原封不動也不對（那正好讓「斷言 `devtools_platform == 'paperclip'`」這種寫錯邊
        的測試在守門通過、到別人的專案才爆）。
        `org.yml` 只動 `ai_platform` 一欄：其餘欄位是 protocol 第 9／8 節的投影，
        目標專案照樣是那張圖（`O1`），改了反而不像真的。
        """
        (root / foundry_lint.CONFIG_REL).write_text(self.TARGET_CONFIG, encoding="utf-8")
        org_path = root / foundry_lint.ORG_REL
        org = org_path.read_text(encoding="utf-8")
        cur = foundry_lint.parse_org(org)["ai_platform"]
        self.assertNotEqual(
            cur, self.TARGET_AI_PLATFORM,
            "規則本體自己也宣告 %s 了——換一個值，否則這格構造不出「值不同」"
            % self.TARGET_AI_PLATFORM)
        org_path.write_text(
            org.replace("ai_platform: " + cur,
                        "ai_platform: " + self.TARGET_AI_PLATFORM),
            encoding="utf-8")

    def _target_root(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "target"
        shutil.copytree(
            REPO_ROOT, root,
            ignore=shutil.ignore_patterns(".git", "site", "__pycache__"),
        )
        for rel in self.ABSENT_IN_TARGET:
            path = root / rel
            self.assertTrue(path.exists(),
                            f"{rel} 在規則本體就不存在——這份清單漂了，要回頭對複製清單")
            shutil.rmtree(path) if path.is_dir() else path.unlink()
        self._retarget_foundry_dir(root)
        marked = self._marked_files(root)
        self.assertIn("tools/foundry-lint/test_rule_repo.py", marked,
                      "本檔沒有帶標記——留在 root 裡子程序會再跑一次本測試＝無限遞迴")
        for rel in marked:
            (root / rel).unlink()
        return root

    def _discover(self, root, tool, *extra):
        return subprocess.run(
            [sys.executable, "-m", "unittest", "discover", f"tools/{tool}", *extra],
            capture_output=True, text=True, cwd=root,
        )

    def test_可攜那半套在目標專案全綠(self):
        root = self._target_root()
        tools = self._tool_dirs(root)
        self.assertTrue(tools, "Makefile 裡一個 tools/ 目錄都沒抓到")
        for tool in tools:
            with self.subTest(tool=tool):
                proc = self._discover(root, tool)
                self.assertEqual(proc.returncode, 0, proc.stderr[-4000:])
                # 全部被搬走的話 `discover` 回 exit 5（`NO TESTS RAN`）——那不是綠，
                # 是「沒有測試」。目標專案的每個工具都得留下真的在跑的東西。
                self.assertNotIn("NO TESTS RAN", proc.stderr)
                self.assertRegex(proc.stderr, r"Ran \d+ tests")

    #: 三種「寫錯邊」的形狀，各配一個注入可攜檔的反例。三條都是實測過會逃過
    #: 收緊前那版守門的（MYL-91 第 1 輪審查瑕疵 2）：只刪 `docs`／`scripts`／
    #: `.github`／`mkdocs.yml`／`skills/foundry-init` 的話，下面第 2、3 條照樣綠。
    #: 第 3 條就是 `RealConfigTest` 被搬走的**那一條原文**——有人把它搬回可攜檔，
    #: 守門必須有反應。
    WRONG_SIDE_PROBES = (
        ("讀規則本體才有的_PRD",
         "        (REPO_ROOT / 'docs' / 'features' / 'foundry-lint'\n"
         "         / 'PRD.md').read_text(encoding='utf-8')\n",
         "FileNotFoundError"),
        ("讀不會被複製過去的_skill",
         "        (REPO_ROOT / 'skills' / 'foundry-adopt'\n"
         "         / 'SKILL.md').read_text(encoding='utf-8')\n",
         "FileNotFoundError"),
        ("斷言真設定檔的值",
         "        cfg = foundry_lint.read_config(REPO_ROOT)\n"
         "        assert cfg['devtools_platform'] == 'paperclip', cfg\n",
         "AssertionError"),
    )

    def test_把規則本體專屬的測試寫進可攜檔會被擋下(self):
        """反例：沒有它，上一條可能只是因為 root 構造得太寬鬆才綠。"""
        for name, body, expected in self.WRONG_SIDE_PROBES:
            with self.subTest(probe=name):
                root = self._target_root()
                portable = root / "tools" / "foundry-lint" / "test_foundry_lint.py"
                portable.write_text(
                    portable.read_text(encoding="utf-8")
                    + "\n\nclass WrongFileCounterExampleTest(unittest.TestCase):\n"
                      "    def test_反例_%s(self):\n" % name
                    + body,
                    encoding="utf-8")
                proc = self._discover(root, "foundry-lint", "-k", "反例")
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertIn(expected, proc.stderr)

    def test_目標專案形狀的設定檔真的與規則本體不同(self):
        """`_retarget_foundry_dir` 的守門：值一樣的話，上一條第 3 個探針就是假綠。"""
        root = self._target_root()
        target = foundry_lint.read_config(root)
        real = foundry_lint.read_config(REPO_ROOT)
        self.assertNotEqual(target.get("devtools_platform"),
                            real.get("devtools_platform"))
        self.assertEqual(foundry_lint.parse_org(
            (root / foundry_lint.ORG_REL).read_text(encoding="utf-8"))["ai_platform"],
            target.get("ai_platform"),
            "兩份檔的 `ai_platform` 對不上——真的目標專案不長這樣，`org-sync` 會紅")

    def test_標記檔真的被排除掉了(self):
        """反例的反例：標記沒被讀到的話，上面兩條都會變成在測別的東西。"""
        root = self._target_root()
        self.assertEqual(self._marked_files(root), [],
                         "帶標記的檔案沒有從目標專案形狀的 root 裡刪掉")
        self.assertTrue(self._marked_files(REPO_ROOT),
                        "規則本體一個帶標記的檔案都沒有——標記字串八成漂了")


if __name__ == "__main__":
    unittest.main()
