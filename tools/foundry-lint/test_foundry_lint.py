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
                          "big-files", "internal-links"})

    def test_selfcheck_不需要_type_與_file(self):
        proc = self._run()
        self.assertEqual(proc.stderr, "")


if __name__ == "__main__":
    unittest.main()
