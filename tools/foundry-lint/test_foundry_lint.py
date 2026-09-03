"""foundry-lint 測試：LLD 第 6 節的單元、整合與煙霧情境。

執行：python3 -m unittest discover tools/foundry-lint
"""

import json
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


if __name__ == "__main__":
    unittest.main()
