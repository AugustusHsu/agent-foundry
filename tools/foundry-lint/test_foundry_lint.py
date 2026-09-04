"""foundry-lint 測試：LLD 第 6 節的單元、整合與煙霧情境。

執行：python3 -m unittest discover tools/foundry-lint
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import foundry_lint
from foundry_lint import LintError, build_rules, check_file, extract_headings

# 測試一律不連線。`mirror-recon` 啟用後會打 GitHub 與 Paperclip API，
# 讓單元測試依賴線上狀態，等於讓它隨時可能因為與程式無關的原因變紅。
# 連線那一段改用注入假資料驗（見 MirrorReconTest），這裡只關掉真的出網。
# 用 setdefault：想驗真實連線行為時，從外面設別的值就能覆寫。
os.environ.setdefault(foundry_lint.MIRROR_OFFLINE_ENV, "1")

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
                          "big-files", "internal-links", "handbook-stamp",
                          "mirror-recon"})

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
    def git(self, *args):
        # 環境要洗掉 `GIT_*` 再跑。pre-commit 執行 hook 時會**匯出 `GIT_DIR`**，
        # 那個變數的優先序高於 `-C`：於是這裡的 `git commit` 會跑到真 repo 的
        # git dir、連帶觸發真 repo 裝好的 pre-commit hook，而 cwd 在暫存目錄、
        # 找不到 `.pre-commit-config.yaml`，整組測試在 hook 裡必敗、在 hook 外必過。
        # （MYL-54 發現，成因與本單無關；`make test` 直接跑一直是綠的，所以
        # 沒有人看到過這個失敗。）
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        proc = subprocess.run(("git", "-C", str(self.root)) + args,
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

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


class ConfigParserTest(unittest.TestCase):
    """`.foundry/config.yml` 的迷你 parser：只支援本檔用得到的子集。"""

    def test_巢狀與註解與引號(self):
        cfg = foundry_lint.parse_config(
            "# 開頭註解\n"
            "foundry: 1\n"
            "platform: paperclip   # 行尾註解\n"
            "mirror_platform: github\n"
            "platform_options:\n"
            "  github:\n"
            "    project_owner: '@me'\n"
            "    mirror_since: \"MYL-58\"\n"
            "  paperclip:\n"
            "    project_id: abc-123\n"
            "gates:\n"
            "  external_actions: user\n"
        )
        self.assertEqual(cfg["platform"], "paperclip")
        self.assertEqual(cfg["mirror_platform"], "github")
        self.assertEqual(cfg["platform_options"]["github"]["project_owner"], "@me")
        self.assertEqual(cfg["platform_options"]["github"]["mirror_since"], "MYL-58")
        self.assertEqual(cfg["platform_options"]["paperclip"]["project_id"], "abc-123")
        self.assertEqual(cfg["gates"]["external_actions"], "user")

    def test_離開巢狀後回到頂層(self):
        cfg = foundry_lint.parse_config(
            "platform_options:\n  github:\n    a: 1\npush:\n  main_push: user\n")
        self.assertEqual(cfg["push"]["main_push"], "user")
        self.assertNotIn("push", cfg["platform_options"])

    def test_真實設定檔讀得出_platform(self):
        cfg = foundry_lint.read_config(REPO_ROOT)
        self.assertEqual(cfg.get("platform"), "paperclip")


class MirrorMarkerTest(unittest.TestCase):
    """對應標記是唯一權威，解析錯了整個對帳就沒有基準。"""

    def test_正常標記(self):
        self.assertEqual(
            foundry_lint.parse_mirror_marker("Foundry-Source: paperclip/MYL-58\n\n正文"),
            ("paperclip", "MYL-58"))

    def test_網頁編輯過的_CRLF_行尾(self):
        self.assertEqual(
            foundry_lint.parse_mirror_marker("Foundry-Source: paperclip/MYL-58\r\n\r\n正文"),
            ("paperclip", "MYL-58"))

    def test_空_body_不中斷(self):
        # API 對沒有內文的 issue 回的是 null；少擋這一層，整個對帳會被一張
        # 沒內文的 issue 中斷，而錯誤訊息不會說是哪一張。
        self.assertIsNone(foundry_lint.parse_mirror_marker(None))
        self.assertIsNone(foundry_lint.parse_mirror_marker(""))

    def test_標記不在首行不算(self):
        self.assertIsNone(
            foundry_lint.parse_mirror_marker("前言\nFoundry-Source: paperclip/MYL-58"))

    def test_人手開的_issue_沒有標記(self):
        self.assertIsNone(foundry_lint.parse_mirror_marker("一般 issue 的內文"))


class MirrorScopeTest(unittest.TestCase):
    """`mirror_since` 界線：本單只鏡像新單，舊單回填要另外核可。"""

    def test_界線含自己(self):
        self.assertTrue(foundry_lint.in_mirror_scope("MYL-58", "MYL-58"))
        self.assertTrue(foundry_lint.in_mirror_scope("MYL-59", "MYL-58"))
        self.assertFalse(foundry_lint.in_mirror_scope("MYL-57", "MYL-58"))

    def test_序號比大小不是字串比大小(self):
        self.assertTrue(foundry_lint.in_mirror_scope("MYL-100", "MYL-58"))

    def test_沒設界線時全部納入(self):
        self.assertTrue(foundry_lint.in_mirror_scope("MYL-1", ""))

    def test_形狀不符時寧可誤報不要漏報(self):
        self.assertTrue(foundry_lint.in_mirror_scope("怪名字", "MYL-58"))
        self.assertTrue(foundry_lint.in_mirror_scope("ABC-1", "MYL-58"))


def _src(ref, status, skipped=False):
    return foundry_lint.SourceIssue(ref=ref, status=status, mirror_skipped=skipped)


def _mir(number, ref, state, status="Todo", platform="paperclip"):
    return foundry_lint.MirrorIssue(number=number, source_platform=platform,
                                    ref=ref, state=state, status=status)


class MirrorReconTest(unittest.TestCase):
    """對帳的反例：每一種不同步都要有一個擋得住它的案例。

    「永遠會通過的檢查」等於沒有檢查——對帳尤其容易寫成這樣，因為它平常
    本來就該是綠的。
    """

    def recon(self, sources, mirrors, platform="paperclip"):
        return foundry_lint.reconcile_mirror(sources, mirrors, platform)

    def test_完全同步時沒有紅燈(self):
        self.assertEqual(self.recon(
            [_src("MYL-58", "in_progress"), _src("MYL-59", "done")],
            [_mir(1, "MYL-58", "open", "In Progress"),
             _mir(2, "MYL-59", "closed", "Done")]), [])

    def test_漏建被擋下(self):
        fails = self.recon([_src("MYL-58", "todo")], [])
        self.assertEqual(len(fails), 1)
        self.assertIn("漏建", fails[0])
        self.assertIn("MYL-58", fails[0])

    def test_標了_Mirror_skipped_就不算漏建(self):
        self.assertEqual(self.recon([_src("MYL-58", "todo", skipped=True)], []), [])

    def test_孤兒被擋下(self):
        fails = self.recon([], [_mir(7, "MYL-999", "open")])
        self.assertEqual(len(fails), 1)
        self.assertIn("孤兒", fails[0])

    def test_沒有標記的_issue_不算孤兒(self):
        # fetch 階段就把沒標記的濾掉了：那是人手開的單，不歸鏡像管，
        # 當殘骸清掉會誤傷。這裡驗的是「濾掉之後對帳確實安靜」。
        self.assertEqual(self.recon([], []), [])

    def test_一對多被擋下(self):
        fails = self.recon([_src("MYL-58", "todo")],
                           [_mir(1, "MYL-58", "open"), _mir(2, "MYL-58", "open")])
        self.assertTrue(any("一對多" in f for f in fails))
        self.assertTrue(any("#1" in f and "#2" in f for f in fails))

    def test_狀態不同步被擋下(self):
        fails = self.recon([_src("MYL-58", "in_review")],
                           [_mir(1, "MYL-58", "open", "Todo")])
        self.assertEqual(len(fails), 1)
        self.assertIn("狀態不同步", fails[0])
        self.assertIn("In Review", fails[0])

    def test_開關狀態不同步被擋下(self):
        fails = self.recon([_src("MYL-58", "done")],
                           [_mir(1, "MYL-58", "open", "Done")])
        self.assertEqual(len(fails), 1)
        self.assertIn("開關狀態不同步", fails[0])

    def test_cancelled_也該是關閉(self):
        self.assertEqual(self.recon([_src("MYL-58", "cancelled")],
                                    [_mir(1, "MYL-58", "closed", "Cancelled")]), [])
        self.assertTrue(self.recon([_src("MYL-58", "cancelled")],
                                   [_mir(1, "MYL-58", "open", "Cancelled")]))

    def test_沒掛進_project_被擋下(self):
        fails = self.recon([_src("MYL-58", "todo")],
                           [_mir(1, "MYL-58", "open", status="")])
        self.assertEqual(len(fails), 1)
        self.assertIn("沒有掛進 project", fails[0])

    def test_六態外的來源狀態報紅而不是自行推導(self):
        # Paperclip 實際有 `backlog`，六態對照表沒有它。這裡刻意不猜
        # 「backlog 大概等於 Todo」——猜出來的對照沒有人核可過。
        fails = self.recon([_src("MYL-58", "backlog")],
                           [_mir(1, "MYL-58", "open", "Todo")])
        self.assertEqual(len(fails), 1)
        self.assertIn("不在六態對照表上", fails[0])
        self.assertIn("不得在這裡自行推導", fails[0])

    def test_來源平台標記不符被擋下(self):
        fails = self.recon([_src("MYL-58", "todo")],
                           [_mir(1, "MYL-58", "open", "Todo", platform="linear")])
        self.assertEqual(len(fails), 1)
        self.assertIn("linear", fails[0])

    def test_六態全部有對照(self):
        for status, expected in foundry_lint.SIX_STATE_TO_GH_STATUS.items():
            with self.subTest(status=status):
                state = ("closed" if status in foundry_lint.MIRROR_CLOSED_STATES
                         else "open")
                self.assertEqual(
                    self.recon([_src("MYL-58", status)],
                               [_mir(1, "MYL-58", state, expected)]), [])


#: 讓 `check_mirror_recon` 走完「憑證齊備」那條路的最小環境。值是假的——
#: 這幾個測試都把 fetch 換成假資料，不會真的送出請求；env 齊備只是為了不讓
#: 檢查在憑證那一關就跳過（CI 上本來就沒有這幾個變數）。
_ONLINE_ENV = {
    foundry_lint.MIRROR_OFFLINE_ENV: "",
    "PAPERCLIP_API_URL": "https://example.invalid/api",
    "PAPERCLIP_API_KEY": "fake-key",
}


class MirrorReconCheckTest(unittest.TestCase):
    """`check_mirror_recon` 的三種姿態：未啟用、跳過、真的對帳。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".foundry").mkdir()

    def write_config(self, text):
        (self.root / ".foundry" / "config.yml").write_text(text, encoding="utf-8")

    ENABLED = ("platform: paperclip\nmirror_platform: github\n"
               "platform_options:\n"
               "  github:\n    mirror_since: MYL-58\n"
               "  paperclip:\n    company_id: fake-company\n")

    def test_未設定_mirror_platform_是通過不是跳過(self):
        self.write_config("platform: paperclip\n")
        res = foundry_lint.check_mirror_recon(self.root)
        self.assertTrue(res.passed)
        self.assertEqual(res.skipped, "")
        self.assertIn("不鏡像", res.summary)

    def test_離線旗標下是跳過不是通過(self):
        self.write_config(self.ENABLED)
        with mock.patch.dict(os.environ, {foundry_lint.MIRROR_OFFLINE_ENV: "1"}):
            res = foundry_lint.check_mirror_recon(self.root)
        self.assertTrue(res.passed)      # 跳過不擋 commit
        self.assertTrue(res.skipped)     # 但絕不印成 ✅
        rendered = foundry_lint.render_selfcheck_text([res])
        self.assertIn("⏭", rendered)
        self.assertIn("1 項跳過未檢查", rendered)
        self.assertNotIn("✅", rendered)

    def test_沒有對帳實作的鏡像平台是跳過(self):
        self.write_config("platform: paperclip\nmirror_platform: local-md\n")
        res = foundry_lint.check_mirror_recon(self.root)
        self.assertTrue(res.skipped)

    def test_讀不到鏡像端是跳過不是紅燈(self):
        # `gh` 沒裝／沒登入／網路不通都不是鏡像漂移。報成紅燈只會讓人
        # 學會忽略這一項，真的漂移時也一起忽略掉。
        self.write_config(self.ENABLED)
        with mock.patch.dict(os.environ, _ONLINE_ENV), \
                mock.patch.object(foundry_lint, "fetch_mirror_issues",
                                  return_value=(None, "`gh` CLI 不在 PATH 上")):
            res = foundry_lint.check_mirror_recon(self.root)
        self.assertTrue(res.passed)
        self.assertIn("gh", res.skipped)

    def test_鏡像端撈到上限視為可能截斷而報紅(self):
        # 截斷過的對帳會把漏建報成「全過」，比不對帳更危險。
        self.write_config(self.ENABLED)
        with mock.patch.dict(os.environ, _ONLINE_ENV), \
                mock.patch.object(foundry_lint, "fetch_mirror_issues",
                                  return_value=(([], True), "")), \
                mock.patch.object(foundry_lint, "fetch_source_issues",
                                  return_value=([], "")):
            res = foundry_lint.check_mirror_recon(self.root)
        self.assertFalse(res.passed)
        self.assertIn("截斷", res.failures[0])

    def test_接得起來的完整路徑會抓到不同步(self):
        self.write_config(self.ENABLED)
        with mock.patch.dict(os.environ, _ONLINE_ENV), \
                mock.patch.object(
                    foundry_lint, "fetch_mirror_issues",
                    return_value=(([_mir(1, "MYL-58", "open", "Todo")], False), "")), \
                mock.patch.object(
                    foundry_lint, "fetch_source_issues",
                    return_value=([_src("MYL-58", "done")], "")):
            res = foundry_lint.check_mirror_recon(self.root)
        self.assertFalse(res.passed)
        self.assertEqual(len(res.failures), 2)   # Status 與開關狀態各一
        self.assertIn("來源端 1 張、鏡像端 1 張", res.summary)


if __name__ == "__main__":
    unittest.main()
