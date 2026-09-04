"""foundry-lint 測試：LLD 第 6 節的單元、整合與煙霧情境。

執行：python3 -m unittest discover tools/foundry-lint
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import foundry_lint
from foundry_lint import LintError, build_rules, check_file, extract_headings

SCRIPT = Path(__file__).resolve().with_name("foundry_lint.py")
REPO_ROOT = SCRIPT.parent.parent.parent
REAL_TEMPLATES_DIR = REPO_ROOT / "templates"
REAL_PRD = REPO_ROOT / "docs" / "features" / "foundry-lint" / "PRD.md"

FAKE_TEMPLATE = "# 模板\n\n## 1. 概述\n\n內文\n\n## 2. 需求\n\n## 3. 未決事項\n"


def run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


class ExtractHeadingsTest(unittest.TestCase):
    def test_只收二級標題(self):
        text = "# 一級\n## 甲\n### 三級\n#### 四級\n## 乙\n"
        self.assertEqual(extract_headings(text), ["甲", "乙"])

    def test_井號後多空白與行尾空白(self):
        text = "##  1. 概述  \n##\t縮排標題   \n"
        self.assertEqual(extract_headings(text), ["1. 概述", "縮排標題"])

    def test_圍欄區塊內的標題不計(self):
        text = "## 真標題\n```\n## 假標題\n```\n## 又一個\n"
        self.assertEqual(extract_headings(text), ["真標題", "又一個"])

    def test_波浪圍欄同樣跳過(self):
        text = "~~~\n## 假標題\n~~~\n## 真標題\n"
        self.assertEqual(extract_headings(text), ["真標題"])

    def test_重複標題保序不去重(self):
        text = "## 甲\n## 乙\n## 甲\n"
        self.assertEqual(extract_headings(text), ["甲", "乙", "甲"])

    def test_無標題與空字串(self):
        self.assertEqual(extract_headings(""), [])
        self.assertEqual(extract_headings("純文字\n沒有標題\n"), [])


class BuildRulesTest(unittest.TestCase):
    def test_去重保序(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.md"
            path.write_text("## 甲\n## 乙\n## 甲\n", encoding="utf-8")
            self.assertEqual(build_rules(path), ["甲", "乙"])

    def test_模板讀不到丟_LintError(self):
        with self.assertRaises(LintError) as ctx:
            build_rules(Path("/不存在/模板.md"))
        self.assertIn("無法讀取模板", str(ctx.exception))

    def test_模板無二級標題丟_LintError(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.md"
            path.write_text("# 只有一級\n內文\n", encoding="utf-8")
            with self.assertRaises(LintError) as ctx:
                build_rules(path)
            self.assertIn("模板未含任何二級標題", str(ctx.exception))


class CheckFileTest(unittest.TestCase):
    def _check(self, doc_text, required):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            doc.write_text(doc_text, encoding="utf-8")
            return check_file(str(doc), "prd", required)

    def test_缺多項全列出且維持模板順序(self):
        result = self._check("## 乙\n", ["甲", "乙", "丙"])
        self.assertEqual(result.missing, ["甲", "丙"])
        self.assertFalse(result.passed)

    def test_額外章節不影響判定(self):
        result = self._check("## 甲\n## 額外\n## 乙\n", ["甲", "乙"])
        self.assertEqual(result.missing, [])
        self.assertTrue(result.passed)

    def test_空文件缺全部(self):
        result = self._check("", ["甲", "乙"])
        self.assertEqual(result.missing, ["甲", "乙"])

    def test_受檢檔讀不到丟_LintError(self):
        with self.assertRaises(LintError) as ctx:
            check_file("/不存在/doc.md", "prd", ["甲"])
        self.assertIn("無法讀取檔案", str(ctx.exception))


class CliIntegrationTest(unittest.TestCase):
    """以 tempfile 假模板目錄＋ --templates-dir 注入，驗 exit code 與輸出。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.templates = self.tmp / "templates"
        self.templates.mkdir()
        (self.templates / "prd.md").write_text(FAKE_TEMPLATE, encoding="utf-8")

    def _doc(self, text):
        doc = self.tmp / "doc.md"
        doc.write_text(text, encoding="utf-8")
        return doc

    def _run(self, *extra):
        return run_cli("--templates-dir", str(self.templates), *extra)

    def test_通過_exit_0(self):
        doc = self._doc("## 1. 概述\n## 2. 需求\n## 3. 未決事項\n")
        proc = self._run("--type", "prd", str(doc))
        self.assertEqual(proc.returncode, 0)
        self.assertIn(f"✅ {doc} 通過 prd 模板章節檢查（必備章節 3 項齊備）",
                      proc.stdout)
        self.assertEqual(proc.stderr, "")

    def test_缺章節_exit_1_逐項列出維持模板順序(self):
        doc = self._doc("## 2. 需求\n")
        proc = self._run("--type", "prd", str(doc))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("未通過 prd 模板章節檢查，缺少 2 項必備章節：", proc.stdout)
        lines = proc.stdout.splitlines()
        self.assertEqual(lines[1:], ["  - ## 1. 概述", "  - ## 3. 未決事項"])

    def test_受檢檔不存在_exit_2_stdout淨空(self):
        proc = self._run("--type", "prd", str(self.tmp / "沒有這個檔.md"))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("無法讀取檔案", proc.stderr)

    def test_缺_type_exit_2(self):
        doc = self._doc("")
        proc = self._run(str(doc))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("usage", proc.stderr)

    def test_type_值非法_exit_2_列合法值(self):
        doc = self._doc("")
        proc = self._run("--type", "sdd", str(doc))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("prd", proc.stderr)

    def test_模板讀不到_exit_2(self):
        doc = self._doc("")
        proc = run_cli("--templates-dir", str(self.tmp / "沒有的目錄"),
                       "--type", "prd", str(doc))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("無法讀取模板", proc.stderr)

    def test_模板無二級標題_exit_2(self):
        (self.templates / "prd.md").write_text("# 只有一級\n", encoding="utf-8")
        doc = self._doc("## 甲\n")
        proc = self._run("--type", "prd", str(doc))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("模板未含任何二級標題", proc.stderr)

    def test_json_通過_可解析恰四欄位(self):
        doc = self._doc("## 1. 概述\n## 2. 需求\n## 3. 未決事項\n")
        proc = self._run("--type", "prd", "--format", "json", str(doc))
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(set(data), {"file", "type", "passed", "missing_sections"})
        self.assertEqual(data["file"], str(doc))
        self.assertEqual(data["type"], "prd")
        self.assertTrue(data["passed"])
        self.assertEqual(data["missing_sections"], [])

    def test_json_不通過_與_text_判定一致且不轉義中文(self):
        doc = self._doc("## 2. 需求\n")
        json_proc = self._run("--type", "prd", "--format", "json", str(doc))
        text_proc = self._run("--type", "prd", str(doc))
        self.assertEqual(json_proc.returncode, 1)
        self.assertEqual(json_proc.returncode, text_proc.returncode)
        data = json.loads(json_proc.stdout)
        self.assertFalse(data["passed"])
        self.assertEqual(data["missing_sections"], ["## 1. 概述", "## 3. 未決事項"])
        self.assertIn("概述", json_proc.stdout)          # ensure_ascii=False
        self.assertNotIn("\\u", json_proc.stdout)

    def test_json_模式執行錯誤仍走_stderr_純文字(self):
        proc = self._run("--type", "prd", "--format", "json",
                         str(self.tmp / "沒有這個檔.md"))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("無法讀取檔案", proc.stderr)


class RealRepoSmokeTest(unittest.TestCase):
    """對真實 repo 的煙霧測試：預設模板目錄，不帶 --templates-dir。"""

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

    def test_六種類型以模板骨架文件迴圈驗證(self):
        for doc_type, template_name in foundry_lint.TYPE_TO_TEMPLATE.items():
            with self.subTest(doc_type=doc_type):
                headings = extract_headings(
                    (REAL_TEMPLATES_DIR / template_name).read_text(encoding="utf-8"))
                skeleton = "\n".join(f"## {h}" for h in headings) + "\n"
                with tempfile.TemporaryDirectory() as tmp:
                    doc = Path(tmp) / f"{doc_type}.md"
                    doc.write_text(skeleton, encoding="utf-8")
                    proc = run_cli("--type", doc_type, str(doc))
                self.assertEqual(proc.returncode, 0, proc.stderr)


class MkdocsSlugTest(unittest.TestCase):
    """slugify 必須複製 markdown.extensions.toc 的 unicode=False 行為。

    這是 MYL-25 的成因：中文標題的錨點不是中文字面。
    """

    def test_中文被整段丟掉只留_ASCII(self):
        self.assertEqual(foundry_lint.mkdocs_slug("1. 主開發流程鏈"), "1")
        self.assertEqual(foundry_lint.mkdocs_slug("3. HITL 發卡"), "3-hitl")

    def test_去掉行內標記後才_slugify(self):
        self.assertEqual(foundry_lint.mkdocs_slug("**Bold** and `code`"),
                         "bold-and-code")

    def test_重複標題加底線序號(self):
        anchors = foundry_lint.anchors_of("## Alpha\n## Alpha\n## Alpha\n")
        self.assertEqual(anchors, {"alpha", "alpha_1", "alpha_2"})

    def test_純中文標題產生空_slug_不列為錨點(self):
        self.assertEqual(foundry_lint.anchors_of("## 總覽\n"), set())


class RuleIdRegistryTest(unittest.TestCase):
    def test_展開波浪號範圍(self):
        text = "## 11. 規則 ID 索引\n\n| ID | x |\n| --- | --- |\n| `H1`～`H4` | 閘門 |\n"
        declared, prefixes, _ = foundry_lint.parse_rule_id_registry(text)
        self.assertEqual(declared, {"H1", "H2", "H3", "H4"})
        self.assertEqual(prefixes, {"H"})

    def test_斜線列舉逐個登記(self):
        text = "## 11. 規則 ID 索引\n\n| `G-A`／`G-B`／`G-C` | 關卡 |\n"
        declared, _, _ = foundry_lint.parse_rule_id_registry(text)
        self.assertEqual(declared, {"G-A", "G-B", "G-C"})

    def test_沒有索引節時回空集合(self):
        self.assertEqual(foundry_lint.parse_rule_id_registry("# 無")[0], set())


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

    def test_新增章節只改一份_nav_被擋下(self):
        (self.root / "docs" / "handbook" / "09-new.md").write_text(
            "# 9. 新章\n", encoding="utf-8")
        res = self._named("nav-sync")
        self.assertFalse(res.passed)
        self.assertEqual(len(res.failures), 2)  # 兩份 nav 各報一次
        self.assertTrue(all("09-new.md" in f for f in res.failures))

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
                          "big-files", "internal-links", "handbook-stamp"})

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


class HandbookStampTest(unittest.TestCase):
    """手冊同步戳記（MYL-44）：在臨時 git repo 上驗三層閘門各自擋得住什麼。

    這一組必須有真的 git 歷史——落後的判準問的是「戳記之後的 protocol 改動有沒有
    手冊變更同行」，那是 commit 之間的關係，不是單看檔案內容能回答的事。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        (self.root / foundry_lint.HANDBOOK_REL).mkdir(parents=True)
        (self.root / foundry_lint.PROTOCOL_REL).parent.mkdir(parents=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "測試")
        self.write_protocol("初版規範\n")
        for name in foundry_lint.STAMPED_CHAPTERS:
            self.chapter(name).write_text(f"# {name}\n\n本章內文。\n", encoding="utf-8")
        self.commit("初始")
        self.restamp()
        self.commit("掛上戳記")

    # ── 輔助 ──────────────────────────────────────────────────────────
    def git(self, *args, cwd=None):
        """對臨時 repo 跑 git。

        `env` 不能省：從 worktree 裡 commit 時，git 會匯出絕對路徑的
        `GIT_DIR`／`GIT_INDEX_FILE`，它們蓋過 `-C`，於是這一整組測試會改去
        操作**外層真正的 repo**——本組 24 個測試會一起倒在 setUp，而訊息是
        「No .pre-commit-config.yaml file was found」，看不出跟 git 有關。
        """
        proc = subprocess.run(("git", "-C", str(cwd or self.root)) + args,
                              capture_output=True, text=True,
                              env=foundry_lint.git_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def clone(self, name, *extra):
        """把臨時 repo clone 出來；`extra` 給 `--depth=1` 之類的形狀參數。"""
        dst = Path(self._tmp.name) / name
        self.git("clone", "-q", *extra, f"file://{self.root}", str(dst),
                 "-b", "main", cwd=self.root)
        return dst

    def chapter(self, name):
        return self.root / foundry_lint.HANDBOOK_REL / name

    def write_protocol(self, text):
        (self.root / foundry_lint.PROTOCOL_REL).write_text(text, encoding="utf-8")

    def protocol_sha(self):
        return self.git("log", "-1", "--format=%h", "--", foundry_lint.PROTOCOL_REL)

    def set_stamp(self, name, sha, date="2026-09-04"):
        path = self.chapter(name)
        lines = path.read_text(encoding="utf-8").splitlines()
        body = [ln for ln in lines[1:] if not foundry_lint.STAMP_RE.match(ln)]
        while body and not body[0].strip():   # 反覆蓋戳記不該堆出空行
            body.pop(0)
        head = [lines[0], "", f"> 最後對照 protocol `{sha}`（{date}）", ""]
        path.write_text("\n".join(head + body) + "\n", encoding="utf-8")

    def restamp(self, sha=None, date="2026-09-04"):
        sha = sha or self.protocol_sha()
        for name in foundry_lint.STAMPED_CHAPTERS:
            self.set_stamp(name, sha, date)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def touch_chapter(self, name="03-workflow.md", text="補一句說明。\n"):
        path = self.chapter(name)
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

    def stamp_check(self):
        return foundry_lint.check_handbook_stamp(self.root)

    # ── 層 1：戳記驗證 ────────────────────────────────────────────────
    def test_四章戳記齊全且最新_通過(self):
        res = self.stamp_check()
        self.assertTrue(res.passed, res.failures)

    def test_protocol_改了沒動手冊_四章全部報落後(self):
        self.write_protocol("初版規範\n新增一條\n")
        self.commit("改規範但沒動手冊")
        res = self.stamp_check()
        self.assertFalse(res.passed)
        self.assertEqual(len(res.failures), len(foundry_lint.STAMPED_CHAPTERS))
        self.assertTrue(all("戳記停在" in f for f in res.failures), res.failures)

    def test_protocol_與手冊同一顆_commit_不算落後(self):
        """判準是『有手冊變更同行』，不是『戳記等於最新 sha』——後者永遠不可能成立。"""
        self.write_protocol("初版規範\n新增一條\n")
        self.touch_chapter()
        self.commit("規範與手冊一起改")
        res = self.stamp_check()
        self.assertTrue(res.passed, res.failures)

    def test_合併_commit_不算一顆未同步的_protocol_改動(self):
        """`--no-ff` 合併會產生一顆碰到 protocol 的 merge commit，那不是改動。"""
        self.git("checkout", "-q", "-b", "topic")
        self.write_protocol("初版規範\n分支上的一條\n")
        self.touch_chapter()
        self.commit("分支上規範與手冊一起改")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", "合併 topic", "topic")
        res = self.stamp_check()
        self.assertTrue(res.passed, res.failures)

    def test_戳記不在標題後第一個非空行被擋下(self):
        name = foundry_lint.STAMPED_CHAPTERS[0]
        path = self.chapter(name)
        lines = path.read_text(encoding="utf-8").splitlines()
        stamp = lines.pop(2)
        path.write_text("\n".join(lines + [stamp]) + "\n", encoding="utf-8")
        res = self.stamp_check()
        self.assertFalse(res.passed)
        self.assertTrue(any(name in f and "第一個非空行" in f for f in res.failures),
                        res.failures)

    def test_戳記_sha_太短不合格式(self):
        self.set_stamp(foundry_lint.STAMPED_CHAPTERS[0], "abc123")
        res = self.stamp_check()
        self.assertFalse(res.passed)
        self.assertTrue(any("第一個非空行" in f for f in res.failures), res.failures)

    def test_戳記日期格式錯不合格式(self):
        path = self.chapter(foundry_lint.STAMPED_CHAPTERS[0])
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[2] = f"> 最後對照 protocol `{self.protocol_sha()}`（2026/09/04）"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        res = self.stamp_check()
        self.assertFalse(res.passed)

    def test_戳記_sha_不是本_repo_的_commit_被擋下(self):
        self.set_stamp(foundry_lint.STAMPED_CHAPTERS[0], "0" * 40)
        res = self.stamp_check()
        self.assertFalse(res.passed)
        self.assertTrue(any("不是本 repo 的 commit" in f for f in res.failures),
                        res.failures)

    def test_戳記指向不在_HEAD_歷史上的_commit_被擋下(self):
        self.git("checkout", "-q", "-b", "側枝")
        self.write_protocol("側枝上的規範\n")
        self.commit("側枝上的改動")
        side = self.git("rev-parse", "--short", "HEAD")
        self.git("checkout", "-q", "main")
        self.set_stamp(foundry_lint.STAMPED_CHAPTERS[0], side)
        res = self.stamp_check()
        self.assertFalse(res.passed)
        self.assertTrue(any("不在 HEAD 的歷史上" in f for f in res.failures), res.failures)

    def test_掛戳記的章節少一份被擋下(self):
        self.chapter(foundry_lint.STAMPED_CHAPTERS[0]).unlink()
        res = self.stamp_check()
        self.assertFalse(res.passed)
        self.assertTrue(any("少了一份" in f for f in res.failures), res.failures)

    def test_淺_clone_擋下且指向_fetch_depth_而不是誤報戳記寫錯(self):
        """`fetch-depth: 1` 的 CI 上，戳記 sha 一律解不出來。

        MYL-44 `D1`：這個情境讓 main 連四顆 commit 的 CI 全紅，而訊息說的是
        「戳記 sha 不是本 repo 的 commit」——四章各報一次，把排查引向手冊，
        真正要改的卻是 checkout 設定。訊息錯誤的成本在這裡是三個 run。

        所以本測試盯的不只是「有擋下」，還有**擋下的理由要對**：一則訊息、
        指向 `fetch-depth`、且不得再出現那句誤導的「不是本 repo 的 commit」。
        """
        dst = self.clone("shallow", "--depth=1")
        self.assertEqual(
            self.git("rev-parse", "--is-shallow-repository", cwd=dst), "true",
            "前提沒成立：這個 clone 根本不淺，後面的斷言就沒有意義了")

        res = foundry_lint.check_handbook_stamp(dst)
        self.assertFalse(res.passed, "淺 clone 驗不了落後，不可以靜靜通過")
        self.assertEqual(len(res.failures), 1, res.failures)
        self.assertIn("fetch-depth", res.failures[0])
        self.assertFalse(any("不是本 repo 的 commit" in f for f in res.failures),
                         res.failures)

    def test_完整_clone_不觸發淺_clone_那條(self):
        """反例：同樣是 clone，帶了歷史就該照常過——別把所有 clone 都擋掉。"""
        dst = self.clone("full")
        res = foundry_lint.check_handbook_stamp(dst)
        self.assertTrue(res.passed, res.failures)

    # ── 層 0：pre-commit 觸發器 ───────────────────────────────────────
    def test_層0_改了_protocol_沒動手冊_擋下且說得出下一步(self):
        self.write_protocol("初版規範\n新增一條\n")
        self.git("add", "-A")
        res = foundry_lint.check_staged_handbook_sync(self.root)
        self.assertFalse(res.passed)
        message = res.failures[0]
        for expected in ("沒有任何變更", "(1)", "(2)", "(3)", "--amend", "--no-verify"):
            self.assertIn(expected, message)

    def test_層0_protocol_與手冊同行_放行(self):
        self.write_protocol("初版規範\n新增一條\n")
        self.touch_chapter()
        self.git("add", "-A")
        self.assertTrue(foundry_lint.check_staged_handbook_sync(self.root).passed)

    def test_層0_沒動_protocol_放行(self):
        self.touch_chapter()
        self.git("add", "-A")
        self.assertTrue(foundry_lint.check_staged_handbook_sync(self.root).passed)

    def test_層0_只有工作區有改動而沒_stage_不算(self):
        """看的是 index，不是工作區——沒進 index 的改動不在這次 commit 裡。"""
        self.write_protocol("初版規範\n新增一條\n")
        self.assertTrue(foundry_lint.check_staged_handbook_sync(self.root).passed)

    def test_層0_CLI_擋下時_exit_1(self):
        self.write_protocol("初版規範\n新增一條\n")
        self.git("add", "-A")
        proc = run_cli("--staged-handbook-sync", "--repo-root", str(self.root))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("handbook", proc.stdout)

    # ── 範圍二：發佈腳本的戳記旁路 ───────────────────────────────────
    def test_旁路_戳記_only_的手冊變更放行(self):
        base = self.git("rev-parse", "HEAD")
        self.write_protocol("初版規範\n新增一條\n")
        self.commit("改規範（模擬 --no-verify 溜過層 0）")
        self.restamp()
        self.commit("📝 補推同步戳記")
        only, commits, offending = foundry_lint.handbook_diff_is_stamp_only(self.root, base)
        self.assertTrue(only, offending)
        self.assertEqual(len(commits), 1)
        self.assertIn("補推同步戳記", commits[0])

    def test_旁路_夾帶實質內容仍擋下(self):
        """工單指名的反向測試：沒有它，這條旁路等於把發佈閘門拆了。"""
        base = self.git("rev-parse", "HEAD")
        self.write_protocol("初版規範\n新增一條\n")
        self.commit("改規範")
        self.restamp()
        self.touch_chapter(text="偷渡的一句話。\n")
        self.commit("📝 推戳記，順手夾帶內容")
        only, _, offending = foundry_lint.handbook_diff_is_stamp_only(self.root, base)
        self.assertFalse(only)
        self.assertIn("偷渡的一句話", offending)

    def test_旁路_首次掛戳記帶進的空行不算實質內容(self):
        """戳記的錨點是「標題／空行／戳記／空行／引言」，首次掛上必然多一個空行。"""
        name = foundry_lint.STAMPED_CHAPTERS[0]
        path = self.chapter(name)
        kept = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                if not foundry_lint.STAMP_RE.match(ln)]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        self.commit("拆掉戳記，回到沒掛戳記的狀態")
        base = self.git("rev-parse", "HEAD")
        self.set_stamp(name, self.protocol_sha())
        self.commit("📝 首次掛上戳記")
        only, _, offending = foundry_lint.handbook_diff_is_stamp_only(self.root, base)
        self.assertTrue(only, offending)

    def test_旁路_刪掉一段內文仍擋下(self):
        """放行空白行不能連帶放行『把內容刪光只留空行』。"""
        base = self.git("rev-parse", "HEAD")
        path = self.chapter(foundry_lint.STAMPED_CHAPTERS[0])
        kept = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                if ln != "本章內文。"]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        self.commit("刪掉一段內文")
        only, _, offending = foundry_lint.handbook_diff_is_stamp_only(self.root, base)
        self.assertFalse(only)
        self.assertIn("本章內文", offending)

    def test_旁路_刪掉整章不算戳記變更(self):
        base = self.git("rev-parse", "HEAD")
        self.chapter(foundry_lint.STAMPED_CHAPTERS[0]).unlink()
        self.commit("刪掉一章")
        only, _, _ = foundry_lint.handbook_diff_is_stamp_only(self.root, base)
        self.assertFalse(only)

    def test_旁路_基準_sha_無效時不放行(self):
        only, _, offending = foundry_lint.handbook_diff_is_stamp_only(self.root, "0" * 40)
        self.assertFalse(only)
        self.assertIn("取不到", offending)

    def test_旁路_CLI_通過印出_commit_清單_夾帶時_exit_1(self):
        base = self.git("rev-parse", "HEAD")
        self.write_protocol("初版規範\n新增一條\n")
        self.commit("改規範")
        self.restamp()
        self.commit("📝 補推同步戳記")
        ok = run_cli("--stamp-only-since", base, "--repo-root", str(self.root))
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("補推同步戳記", ok.stdout)

        self.touch_chapter(text="偷渡的一句話。\n")
        self.commit("📝 夾帶內容")
        bad = run_cli("--stamp-only-since", base, "--repo-root", str(self.root))
        self.assertEqual(bad.returncode, 1)
        self.assertIn("戳記以外", bad.stderr)


if __name__ == "__main__":
    unittest.main()
