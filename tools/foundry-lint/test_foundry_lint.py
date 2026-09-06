"""foundry-lint 測試：LLD 第 6 節的單元、整合與煙霧情境（**可攜的那一半**）。

執行：python3 -m unittest discover tools/foundry-lint

⚠️ **本檔會被 `foundry-init` 複製到每個目標專案**（`skills/foundry-init/SKILL.md`
§2 第 3 點），所以這裡只能放「在任何 Foundry 專案都成立」的測試——判準是
**不依賴 repo 裡預先存在的 `docs/`**。自己造反例寫檔（`RepoCopyTestCase` 那批）
不算依賴，讀 `docs/features/…/PRD.md`、變異 `docs/handbook/` 才算。

以 agent-foundry 自身內容為 fixture 的那一半在 **`test_rule_repo.py`**，
複製清單不帶它。這條界線由 `test_rule_repo.py` 的
`PortableSuiteInTargetProjectTest` 機械把關——寫錯檔案的話它會紅（MYL-91）。
"""

import json
import os
import re
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

# ── 測試程序一開始就把繼承來的 `GIT_*` 全部清掉（MYL-52 修）─────────────────
# git 呼叫 hook 時會設 `GIT_DIR`／`GIT_INDEX_FILE`。這些變數勝過 `git -C <路徑>`，
# 於是在 hook 底下跑的測試裡，`git -C <臨時目錄> init` 會回頭指到**外層 repo**：
# 臨時 repo 根本沒建起來，接著的 commit 觸發外層 pre-commit、在臨時目錄找不到
# `.pre-commit-config.yaml` 而整組紅。
#
# 症狀很難認：**單獨跑全過、在 `pre-commit` 裡跑同一組全敗**。而 `foundry-tests`
# 這個 hook 只在 staged 檔案含 `tools/` 時才觸發，所以它平常看不見，只在動到
# tools/ 的那次 commit 現形——MYL-52 就是這樣撞上的。
#
# 在**程序層**清而不是逐一傳 `env=`：`foundry_lint.git_run` 也是 shell out，
# 逐一傳只擋得住測試自己下的那幾道 git 指令，擋不住受測程式碼下的。
for _leaked in [k for k in os.environ if k.startswith("GIT_")]:
    del os.environ[_leaked]

FAKE_TEMPLATE ="# 模板\n\n## 1. 概述\n\n內文\n\n## 2. 需求\n\n## 3. 未決事項\n"


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
    """對真實 repo 的煙霧測試：預設模板目錄，不帶 --templates-dir。

    只留 `templates/` 這一支——複製清單帶走 `templates/`（全目錄），所以它在目標
    專案同樣成立。以 `docs/features/foundry-lint/PRD.md` 當素材的另外兩條移到
    `test_rule_repo.py`（MYL-91）。
    """

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


class MakefileToolsDirsTest(unittest.TestCase):
    """`makefile_tools_dirs()` 的兩種引用形狀（MYL-86）。"""

    def test_discover_與腳本路徑兩種形狀都取得到(self):
        text = ("test:\n\t@python3 -m unittest discover tools/foundry-lint\n"
                "providers:\n\t@python3 tools/model-routing/probe_providers.py\n")
        self.assertEqual(foundry_lint.makefile_tools_dirs(text),
                         ["foundry-lint", "model-routing"])

    def test_同一個目錄只算一次(self):
        text = ("a:\n\t@python3 tools/x/one.py\n"
                "b:\n\t@python3 -m unittest discover tools/x\n")
        self.assertEqual(foundry_lint.makefile_tools_dirs(text), ["x"])


class VersionShapeTest(unittest.TestCase):
    """版本號形狀（MYL-71，protocol `V5`）：兩種舊形狀各配一個擋得住的反例。

    只做「字面位數不足」那一半是不夠的——本檢查開單的主因（`V3` 的內文與
    `republish_decision()` 的錯誤訊息）用的都是**佔位符**形狀，漏掉第二種
    等於漏掉最該擋的那兩處。所以兩種形狀分開驗，不合成一個測試。
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
        return foundry_lint.check_version_shape(self.root)

    def _write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def test_真實_repo_通過(self):
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_字面位數不足被擋下(self):
        self._write("skills/drift.md", "打 `handbook-v2` tag 發一版。\n")
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("skills/drift.md:1" in f and "1 位" in f
                            for f in res.failures), res.failures)

    def test_非標準佔位符被擋下(self):
        """規則本體與錯誤訊息那一類：形狀是佔位符，位數檢查看不見它。"""
        self._write("scripts/drift.sh", "# 要修就 bump 下一版（打 handbook-v<N+1>）\n")
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("scripts/drift.sh:1" in f and "佔位符" in f
                            for f in res.failures), res.failures)

    def test_合法四碼與標準佔位符不被誤殺(self):
        self._write("tools/ok.py", '"""打 handbook-v0.0.0.1，形狀 handbook-v<a>.<b>.<c>.<d>。"""\n')
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_glob_與正則寫法不被誤殺(self):
        """`tag_pattern` 的 glob 與 GitLab adapter 的 `\\d+` 版正則都是設定值，不是版本號。"""
        self._write("skills/patterns.md",
                    "glob 是 `handbook-v*.*.*.*`，粗篩是 `handbook-v*`，\n"
                    "GitLab 側要翻成 `/^handbook-v\\d+\\.\\d+\\.\\d+\\.\\d+$/`。\n")
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_多一位與非數字尾巴不歸本檢查管(self):
        """`V4` 違反段明列的兩個 `fnmatch` 缺口，是說明文字不是舊形狀。"""
        self._write("skills/gaps.md",
                    "`handbook-v0.0.0.1.2`（多一位）與 `handbook-v0.0.0.x`（非數字）都通得過。\n")
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_豁免清單擋住誤管(self):
        """反例測試與綁 sha 的歷史證據改成四碼就對不上，白名單是這一格的機械化身。"""
        for rel in ("tools/publish-docs/test_site_docs.py",
                    "docs/publish-reviews/MYL-63.md",
                    "docs/standards/known-drift.md",
                    "docs/features/cross-platform/HLD.md",
                    "docs/pilot/pilot-log.md",
                    ".foundry/config.yml"):
            self.assertTrue(foundry_lint.version_shape_allowed(rel), rel)
        self.assertFalse(foundry_lint.version_shape_allowed("docs/handbook/03-workflow.md"))
        self.assertFalse(
            foundry_lint.version_shape_allowed("skills/foundry-protocol/SKILL.md"))

    def test_豁免路徑裡的舊形狀不被擋下(self):
        self._write("docs/publish-reviews/MYL-99.md", "當時發的是 `handbook-v1`。\n")
        res = self._run()
        self.assertTrue(res.passed, res.failures)


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

    # ── 層 1.5：跳過判準（MYL-92）──────────────────────────────────────
    #
    # 本類的 fixture **不是規則本體**（沒造 `skills/foundry-init/`），所以底下每一條
    # 打的都是第 2 層條件本身。三條合起來把它夾在唯一正確的位置上：四章全不在才跳、
    # 留一章就不跳、有第 1 層時一律不跳。

    def _drop_all_stamped_chapters(self):
        for name in foundry_lint.STAMPED_CHAPTERS:
            self.chapter(name).unlink()

    def test_四章一份都不在時整項跳過而不是報四條不存在(self):
        """目標專案自建手冊的情境：手冊在，但那四章是別人家的。

        改判準之前這裡吐四條「掛戳記的章節少了一份」，指名一個目標專案沒有理由
        擁有、也修不掉的東西。
        """
        self._drop_all_stamped_chapters()
        self.chapter("01-first-run.md").write_text("# 1. 第一次上工\n", encoding="utf-8")
        res = self.stamp_check()
        self.assertTrue(res.passed, res.failures)
        self.assertTrue(res.skipped, "沒有跳過理由＝被印成 ✅")
        self.assertIn("沒有任何一份掛戳記的章節", res.skipped)

    def test_只複製了四章其中一章時不跳過_缺的三章照樣紅(self):
        """反例：擋住「`docs/handbook/` 裡有東西就一律跳過」那種寫法。

        真複製了掛戳記的章節，就該把戳記維護齊全——這時的紅是對的、也修得掉。
        """
        kept, *dropped = foundry_lint.STAMPED_CHAPTERS
        for name in dropped:
            self.chapter(name).unlink()
        res = self.stamp_check()
        self.assertFalse(res.passed, "留著一章還跳過，等於第 2 層條件寫成了『有手冊就跳』")
        self.assertFalse(res.skipped)
        self.assertEqual(len(res.failures), len(dropped), res.failures)
        self.assertTrue(all("少了一份" in f for f in res.failures), res.failures)
        self.assertFalse(any(kept in f for f in res.failures), res.failures)

    def test_規則本體四章刪光仍然紅而不是跳過(self):
        """判準①的守門測試：第 1 層一成立，第 2 層就完全不參與判斷。"""
        (self.root / foundry_lint.RULE_REPO_MARKER_REL).mkdir(parents=True)
        self.assertTrue(foundry_lint.is_rule_repo(self.root), "前提沒成立")
        self._drop_all_stamped_chapters()
        res = self.stamp_check()
        self.assertFalse(res.passed, "規則本體把四章刪光被放行")
        self.assertFalse(res.skipped, "規則本體被跳過")
        self.assertEqual(len(res.failures), len(foundry_lint.STAMPED_CHAPTERS),
                         res.failures)

    def test_規則本體戳記落後仍然紅(self):
        """判準①的另一半：跳過判準換掉之後，落後偵測沒有跟著失效。"""
        (self.root / foundry_lint.RULE_REPO_MARKER_REL).mkdir(parents=True)
        self.write_protocol("初版規範\n新增一條\n")
        self.commit("改規範但沒動手冊")
        res = self.stamp_check()
        self.assertFalse(res.passed)
        self.assertFalse(res.skipped)
        self.assertTrue(all("戳記停在" in f for f in res.failures), res.failures)

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


class ConfigParserTest(unittest.TestCase):
    """`.foundry/config.yml` 的迷你 parser：只支援本檔用得到的子集。"""

    def test_巢狀與註解與引號(self):
        cfg = foundry_lint.parse_config(
            "# 開頭註解\n"
            "foundry: 2\n"
            "devtools_platform: paperclip   # 行尾註解\n"
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
        self.assertEqual(cfg["devtools_platform"], "paperclip")
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

    ENABLED = ("devtools_platform: paperclip\nmirror_platform: github\n"
               "platform_options:\n"
               "  github:\n    mirror_since: MYL-58\n"
               "  paperclip:\n    company_id: fake-company\n")

    def test_未設定_mirror_platform_是通過不是跳過(self):
        self.write_config("devtools_platform: paperclip\n")
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
        self.write_config("devtools_platform: paperclip\nmirror_platform: local-md\n")
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


class FetchMirrorIssuesTest(unittest.TestCase):
    """`fetch_mirror_issues` 撈兩份清單，**兩份都會截斷**。"""

    ISSUE = {"number": 2, "state": "OPEN", "body": "Foundry-Source: paperclip/MYL-58\n\n內文"}

    def fake_gh(self, issues, items):
        def gh(root, *args):
            if args[0] == "issue":
                return issues, ""
            if args[0] == "project" and args[1] == "list":
                return {"projects": [{"number": 1, "title": "Foundry"}]}, ""
            return {"items": items}, ""
        return gh

    def run_fetch(self, issues, items):
        with mock.patch.object(foundry_lint, "gh_json",
                               side_effect=self.fake_gh(issues, items)):
            return foundry_lint.fetch_mirror_issues(Path("/x"), "Foundry", "@me")

    def test_兩份清單都沒滿時不報截斷(self):
        (issues, truncated), why = self.run_fetch(
            [self.ISSUE], [{"content": {"number": 2}, "status": "Todo"}])
        self.assertEqual(why, "")
        self.assertFalse(truncated)
        self.assertEqual([(m.ref, m.status) for m in issues], [("MYL-58", "Todo")])

    def test_看板項目撈到上限也算截斷(self):
        # 反例：只看 issue 清單的話這裡會回 truncated=False，於是查不到的
        # Status 變成空字串、每張都報成「狀態不同步」——紅燈理由是錯的。
        items = [{"content": {"number": n}, "status": "Todo"}
                 for n in range(foundry_lint.MIRROR_LIST_LIMIT)]
        (_, truncated), why = self.run_fetch([self.ISSUE], items)
        self.assertEqual(why, "")
        self.assertTrue(truncated)

    def test_issue_清單撈到上限算截斷(self):
        issues = [dict(self.ISSUE, number=n)
                  for n in range(foundry_lint.MIRROR_LIST_LIMIT)]
        (_, truncated), why = self.run_fetch(issues, [])
        self.assertEqual(why, "")
        self.assertTrue(truncated)


class RepoCopyTestCase(unittest.TestCase):
    """把真實 repo 複製到臨時目錄，讓反例可以直接寫檔而不弄髒工作區。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        shutil.copytree(
            REPO_ROOT, self.root,
            ignore=shutil.ignore_patterns(".git", "site", "__pycache__"),
        )

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class TableShapeTest(RepoCopyTestCase):
    """表格被空行切斷（MYL-76 AC9）：反例是「續列」，不是「兩張表」。

    分開驗這兩者是本檢查的重點——只擋「空行後面還有 `|` 開頭的行」會把
    兩張相鄰的表也判成壞的，於是這項檢查第一天就會被當成雜訊關掉。
    """

    TABLE = "| 欄 | 說明 |\n| --- | --- |\n| a | 甲 |\n"

    def _run(self):
        return foundry_lint.check_table_shape(self.root)

    def test_真實_repo_通過(self):
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_續列被空行切斷時擋下(self):
        self.write("docs/standards/drift-sample.md", self.TABLE + "\n| b | 乙 |\n")
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(
            any("docs/standards/drift-sample.md:5" in f for f in res.failures),
            res.failures,
        )

    def test_相鄰的兩張表不誤殺(self):
        self.write("docs/standards/drift-sample.md", self.TABLE + "\n" + self.TABLE)
        self.assertTrue(self._run().passed)

    def test_圍欄裡的示例不算(self):
        self.write(
            "skills/drift-sample.md",
            "```markdown\n" + self.TABLE + "\n| b | 乙 |\n```\n",
        )
        self.assertTrue(self._run().passed)

    def test_沒有分隔列的段落不算表(self):
        """`|` 開頭但下一行不是分隔列——那是普通段落，不該被當成表頭。"""
        self.write("skills/drift-sample.md", "| 這只是一行文字\n\n| 另一行\n")
        self.assertTrue(self._run().passed)

    def test_縮排在清單裡的表也擋得住(self):
        self.write(
            "docs/standards/drift-sample.md",
            "- 說明：\n\n  | 欄 | 值 |\n  | --- | --- |\n  | a | 1 |\n\n  | b | 2 |\n",
        )
        self.assertFalse(self._run().passed)


class TableColumnCountTest(RepoCopyTestCase):
    """欄數與表頭對不上（MYL-98，出處 `8416f66`）。

    這一組跟上面的 `TableShapeTest` 同屬 `table-shape`，但驗的是另一種靜默：
    表格沒被切斷、渲染得出來，只是**多出來的那一格連同內容一起消失**。
    `8416f66` 那次某列 4 格、同表其餘 8 列 3 格，被吃掉的是整個「正確寫法」欄。
    """

    #: 表頭 3 欄，兩列正常資料——`8416f66` 那張表的最小形。
    TABLE = ("| # | 陷阱 | 正確寫法 |\n| --- | --- | --- |\n"
             "| S1 | 甲 | 乙 |\n| S2 | 丙 | 丁 |\n")
    #: 第 5 行：多出第 4 格，裝著本來要給讀者看的內容。
    OVERFLOW = TABLE + "| S3 | 戊 | 己 | 多出來的這一整格會不見 |\n"

    def _run(self):
        return foundry_lint.check_table_shape(self.root)

    def test_真實_repo_通過(self):
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_某列比表頭多一格時擋下(self):
        """`8416f66` 的形狀：某列 4 格，其餘與表頭都是 3 格。"""
        self.write("docs/standards/drift-sample.md", self.OVERFLOW)
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(
            any("docs/standards/drift-sample.md:5" in f and "整格丟掉" in f
                for f in res.failures),
            res.failures,
        )

    def test_舊版邏輯擋不住這個反例(self):
        """AC1：確認上一則不是空轉——只驗連續性的舊邏輯對同一份輸入是綠的。

        問的是舊版判準本身（`table_breaks`），而不是「把新程式碼註解掉再跑一次」：
        反例要擋得住，前提是它在**加這項檢查之前**確實會漏網。
        """
        self.assertEqual(foundry_lint.table_breaks(self.OVERFLOW), [])
        self.assertTrue(foundry_lint.table_column_mismatches(self.OVERFLOW))

    def test_某列比表頭少一格時也擋下(self):
        self.write("skills/drift-sample.md", self.TABLE + "| S3 | 戊 |\n")
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("skills/drift-sample.md:5" in f for f in res.failures),
                        res.failures)

    def test_分隔列格數與表頭不符時擋下(self):
        """分隔列對不上時 GFM 連表格都不渲染，錯得比少一格更徹底。"""
        self.write("skills/drift-sample.md",
                   "| a | b | c |\n| --- | --- |\n| 1 | 2 | 3 |\n")
        res = self._run()
        self.assertFalse(res.passed)
        mine = [f for f in res.failures if "skills/drift-sample.md" in f]
        self.assertTrue(any("分隔列" in f for f in mine), res.failures)
        # 分隔列一壞整張表就不是表，後面每一列不再逐列重報一次
        self.assertEqual(len(mine), 1, res.failures)

    def test_前後沒有管線符號的列不誤殺(self):
        """GFM 的前導／收尾 `|` 是可選的裝飾，寫不寫都是同樣的欄數。"""
        self.write("skills/drift-sample.md",
                   "| a | b |\n| --- | --- |\n| 1 | 2\n| 3 | 4 |\n")
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_逃脫過的管線符號不算分隔(self):
        self.write("skills/drift-sample.md", self.TABLE + "| S3 | `a \\| b` | 己 |\n")
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_反引號保護不了管線符號(self):
        """GFM 先切格再解析行內語法——`` `a|b` `` 實際會切成兩格，那是真的壞掉。"""
        self.write("skills/drift-sample.md", self.TABLE + "| S3 | `a | b` | 己 |\n")
        self.assertFalse(self._run().passed)

    def test_圍欄裡的示例不算(self):
        self.write("skills/drift-sample.md", "```markdown\n" + self.OVERFLOW + "```\n")
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_沒有分隔列的段落不算表(self):
        self.write("skills/drift-sample.md", "| 這只是一行文字\n| 另一行 | 有兩格 |\n")
        res = self._run()
        self.assertTrue(res.passed, res.failures)


class CountCellsTest(unittest.TestCase):
    """`count_cells()` 照 GFM 數格，不照作者的意圖數。"""

    def test_各種寫法(self):
        for line, want in (
            ("| a | b |", 2),
            ("|a|b|", 2),
            ("a | b", 2),             # 前導／收尾的 `|` 在 GFM 是可選的
            ("| a | b", 2),
            ("a | b |", 2),
            ("| a |  |", 2),          # 留白仍是一格
            ("  | a | b |  ", 2),     # 縮排與行尾空白不影響
            ("| a \\| b |", 1),       # 逃脫過的不切
            ("| `a | b` |", 2),       # 反引號保護不了
        ):
            with self.subTest(line=line):
                self.assertEqual(foundry_lint.count_cells(line), want)


class ParseOrgTest(unittest.TestCase):
    """`.foundry/org.yml` 的 parser：不支援的寫法要**拋錯**，不是靜靜忽略。"""

    def test_真實檔案讀得出九名(self):
        org = foundry_lint.parse_org(
            (REPO_ROOT / foundry_lint.ORG_REL).read_text(encoding="utf-8"))
        self.assertEqual(org["foundry_org"], "1")
        self.assertEqual(len(org["roles"]), 9)
        ceo = org["roles"][0]
        self.assertEqual(ceo["id"], "ceo")
        self.assertEqual(ceo["reports_to"], "user")
        self.assertEqual(ceo["skills"], ["skills/roles/ceo/SKILL.md"])
        self.assertIn("assign_tasks", ceo["permissions"])

    def test_註解與行尾註解不進資料(self):
        org = foundry_lint.parse_org(
            "# 抬頭\nfoundry_org: 1  # 版本\nai_platform: paperclip\n")
        self.assertEqual(org, {"foundry_org": "1", "ai_platform": "paperclip"})

    def test_空序列寫成中括號(self):
        org = foundry_lint.parse_org("roles:\n  - id: x\n    permissions: []\n")
        self.assertEqual(org["roles"][0]["permissions"], [])

    def test_不支援的寫法拋錯而不是忽略(self):
        with self.assertRaises(LintError):
            foundry_lint.parse_org("roles:\n  - id: x\n    skills: {a: 1}\n  - 裸序列項\n")

    def test_欄位不在任何角色底下拋錯(self):
        with self.assertRaises(LintError):
            foundry_lint.parse_org("foundry_org: 1\n  title: 迷路的欄位\n")


class OrgSyncTest(RepoCopyTestCase):
    """組織宣告 ↔ protocol 第 9／8 節（MYL-76 AC3）：每個比對方向各配一個反例。"""

    #: 值域外的權限，四種寫錯的方式各一個：中文值、看起來像權限名的英文值、
    #: 與既有成員只差一個字母的近似值、只差大小寫的值。
    #: 都是**自造**的值——不引用 `ORG_PERMISSIONS` 現在有哪些成員
    #: （見 `test_權限值域外被擋下` 的 docstring）。
    OUT_OF_DOMAIN_PERMISSIONS = ("不在值域裡的權限", "do_anything", "create_skill", "CREATE_SKILLS")

    def _run(self):
        return foundry_lint.check_org_sync(self.root)

    def _org(self):
        return (self.root / foundry_lint.ORG_REL).read_text(encoding="utf-8")

    def _set_ai(self, text, value, anchor):
        """把 `text` 的頂層 `ai_platform:` 設成 `value`；原本沒有就插在 `anchor` 行後面。

        其餘內容原封不動——反例只想動這一欄。`anchor` 是各檔一定存在的版本欄
        （`foundry:` / `foundry_org:`），插在它後面才不會掉進某個縮排區塊裡。
        """
        out, seen = [], False
        for line in text.splitlines(True):
            if line.startswith("ai_platform:"):
                out.append("ai_platform: %s\n" % value)
                seen = True
            else:
                out.append(line)
        if seen:
            return "".join(out)
        hits = [i for i, ln in enumerate(out) if ln.startswith(anchor)]
        self.assertTrue(hits, "找不到錨點 `%s`——這兩份檔的形狀變了" % anchor)
        out.insert(hits[0] + 1, "ai_platform: %s\n" % value)
        return "".join(out)

    def _config_with_ai(self, value):
        text = (self.root / foundry_lint.CONFIG_REL).read_text(encoding="utf-8")
        return self._set_ai(text, value, "foundry:")

    def _org_with_ai(self, value):
        return self._set_ai(self._org(), value, "foundry_org:")

    def test_真實_repo_通過(self):
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_檔案不存在時擋下(self):
        (self.root / foundry_lint.ORG_REL).unlink()
        res = self._run()
        self.assertFalse(res.passed)

    def test_版本不認得就停下不猜著解析(self):
        self.write(foundry_lint.ORG_REL, self._org().replace("foundry_org: 1", "foundry_org: 2"))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("foundry_org" in f for f in res.failures), res.failures)

    def test_權限值域外被擋下(self):
        """封閉值域的反例。少了這條，打錯的權限名會被當成一個新權限默默收下。

        **反例自己造兩端**：每個案例都**插一個**保證不在值域裡的值，不去改寫某個
        現有的權限名。本檔是可攜的那一半（`foundry-init` 會複製到目標專案），而
        目標專案的 `org.yml` 宣告什麼權限是它自己的事——依賴現值的話 `replace`
        會變成 no-op，這條就從反例退化成「跑了一次真實 repo」。

        本條是 MYL-97 A3：原本兩條測同一件事的測試收成這一條參數化（MYL-95 第 1
        輪審查次要建議 2）。被收掉的那條寫法正是
        `.replace("      - create_skills", "      - do_anything", 1)`——依賴目標專案
        現在宣告了 `create_skills`，退化成 no-op 也不會有人知道。它涵蓋的值
        （`do_anything`）留在 `OUT_OF_DOMAIN_PERMISSIONS`，並補上三種其他寫錯的方式。

        **訊息斷言只看「值域是 …」之前那半段**，別放寬回整句子字串比對。訊息尾巴
        會列舉值域全部成員，`create_skill` 這種近似值會被 `create_skills` 吃掉，
        那一例就恆真了。守著這條鑑別力的突變（MYL-106 第 1 輪審查瑕疵 1）：把
        `foundry_lint.py` 訊息裡的 `` 有 `{perm}` `` 改成 `` 有 `某個值` ``——
        訊息不再指名犯規的值，四個案例都必須轉紅。
        """
        original = self._org()
        marker = "    permissions:\n"
        self.assertIn(marker, original, "`org.yml` 的 `permissions:` 區塊形狀變了")
        for bogus in self.OUT_OF_DOMAIN_PERMISSIONS:
            with self.subTest(值域外的值=bogus):
                self.assertNotIn(bogus, foundry_lint.ORG_PERMISSIONS,
                                 "這個案例的值被收進值域了，它就不再是反例")
                mutated = original.replace(marker, marker + "      - %s\n" % bogus, 1)
                self.assertNotEqual(mutated, original,
                                    "反例沒改到東西——這輪等於只是跑了一次真實 repo")
                self.write(foundry_lint.ORG_REL, mutated)
                res = self._run()
                self.assertFalse(res.passed, "插了值域外的權限卻通過了")
                self.assertTrue(
                    any("`%s`" % bogus in f.split("值域是")[0] and "值域" in f
                        for f in res.failures),
                    res.failures)

    def test_configure_agents_在值域內(self):
        """MYL-79 加入的值域成員。

        上一條只證明「值域擋得住外來值」，擋不住有人把這個成員從值域**刪掉**——
        那會讓任何登記了它的 `org.yml` 突然變非法，而錯誤訊息會指向 `org.yml`
        （看起來像宣告寫錯），真正的原因卻在值域那一行。
        這裡只斷言常數本身，不斷言任何一份 `org.yml` 的內容：本 repo 的 CEO 確實
        登記了它（卡 `0bd69c99` Q5 核可），但那是本 repo 的資料，守在
        `test_rule_repo.py`；目標專案要不要用這個值是它自己的事。
        """
        self.assertIn("configure_agents", foundry_lint.ORG_PERMISSIONS)

    def test_漏宣告組織圖上的角色被擋下(self):
        text = self._org()
        head, _, _ = text.partition("  - id: qa-engineer")
        self.write(foundry_lint.ORG_REL, head)
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("QA Engineer" in f and "沒有宣告" in f for f in res.failures),
                        res.failures)

    def test_匯報線與組織圖不符被擋下(self):
        text = self._org().replace(
            "    title: Developer\n    reports_to: tech-lead",
            "    title: Developer\n    reports_to: ceo")
        self.write(foundry_lint.ORG_REL, text)
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("`developer` 宣告匯報給" in f and "Tech Lead" in f
                            for f in res.failures), res.failures)

    def test_模型層與第8節不符被擋下(self):
        text = self._org().replace(
            "    title: Developer\n    reports_to: tech-lead\n    model_tier: medium",
            "    title: Developer\n    reports_to: tech-lead\n    model_tier: low")
        self.write(foundry_lint.ORG_REL, text)
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("第 8 節" in f and "developer" in f for f in res.failures),
                        res.failures)

    def test_模型層值域外被擋下(self):
        self.write(foundry_lint.ORG_REL,
                   self._org().replace("model_tier: high", "model_tier: highest", 1))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("model_tier" in f for f in res.failures), res.failures)

    def test_掛的_skill_路徑失效被擋下(self):
        (self.root / "skills/roles/pm/SKILL.md").unlink()
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("skills/roles/pm/SKILL.md" in f for f in res.failures),
                        res.failures)

    def test_兩份設定檔的_ai_platform_不一致被擋下(self):
        """反例自己把兩份檔的值都寫定——**不得依賴規則本體現在宣告的是哪一家**。

        原版寫死 `paperclip → codex`（agent-foundry 自己的值）。目標專案合法宣告
        `codex` 時 `.replace()` 是 no-op、`org-sync` 於是通過，這條就假紅；
        config.yml 整欄不寫（Q2 答「不宣告」，也是合法）時比對根本不觸發，一樣假紅。
        兩種都是本檔身為**可攜那一半**不該有的依賴（MYL-91 第 1 輪審查瑕疵 1，實測過）。
        """
        self.write(foundry_lint.CONFIG_REL, self._config_with_ai("paperclip"))
        self.write(foundry_lint.ORG_REL, self._org_with_ai("codex"))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("ai_platform" in f for f in res.failures), res.failures)

    def test_兩份設定檔的_ai_platform_一致就通過(self):
        """上一條的對照組：確認它紅是因為「不一致」，不是因為反例把檔案寫壞了。"""
        self.write(foundry_lint.CONFIG_REL, self._config_with_ai("codex"))
        self.write(foundry_lint.ORG_REL, self._org_with_ai("codex"))
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    def test_組織圖讀不出來時報紅而不是靜靜通過(self):
        """比對基準的形狀變了要擋下——靜靜通過等於這項檢查從此不存在。"""
        protocol = (self.root / foundry_lint.PROTOCOL_REL).read_text(encoding="utf-8")
        self.write(foundry_lint.PROTOCOL_REL,
                   protocol.replace("### 現行結構", "### 組織現況"))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("組織圖" in f for f in res.failures), res.failures)

    def test_不比對平台實況(self):
        """AC7 的回歸守衛：宣告了平台上還不存在的 PM，本項仍然通過。

        PM 的 agent 要到 MYL-79（T7）才建；期間本檔宣告一個不存在的成員是
        預期行為。這個測試存在的目的是擋下「順手補一個比對平台的檢查」。
        """
        self.assertIn("id: pm", self._org())
        self.assertTrue(self._run().passed)

    # ── 缺 `title` 不得多報一句不存在的「重複」（MYL-85 AC7）──────────────
    def test_缺_title_不會多報一句假的重複(self):
        """原本用 `len(titles) != len(by_id)` 判重複，缺 `title` 也會讓左邊變短。

        失效方向不是假綠（檔案這時本來就非法），是**錯誤訊息把人指向錯的方向**：
        讀到「有重複的 `title`」的人會去找那個不存在的重複。
        """
        text = self._org()
        marker = "    title: Developer\n"
        self.assertIn(marker, text, "`org.yml` 的角色欄位形狀變了")
        self.write(foundry_lint.ORG_REL, text.replace(marker, "", 1))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("缺必填欄位 `title`" in f for f in res.failures), res.failures)
        self.assertFalse([f for f in res.failures if "重複" in f],
                         "缺 `title` 卻報了一句不存在的重複")

    def test_真的重複時仍然報得出來(self):
        """上一條的對照組：確認修法沒有把重複判定一起關掉。

        反例自己造兩端——把某個角色的 `title` 改成**另一個角色的** `title`，
        兩邊都從檔案現值取，不寫死任何一個 repo 的角色名。
        """
        roles = foundry_lint.parse_org(self._org())["roles"]
        first, second = roles[0]["title"], roles[1]["title"]
        self.assertNotEqual(first, second)
        self.write(foundry_lint.ORG_REL,
                   self._org().replace(f"    title: {second}\n",
                                       f"    title: {first}\n", 1))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("重複" in f and first in f for f in res.failures), res.failures)


class ConfigSchemaTest(RepoCopyTestCase):
    """`config-schema`（MYL-85）：設定欄位名、schema 版本、值域、文件裡的舊欄位名。

    每一條反例都**自己造兩端**——要用到的欄位名、必填集合與現行版本號一律從
    `config-schema.md` 現值算出來，不寫死 agent-foundry 自己那份的值。本檔是可攜
    的那一半，目標專案的 `.foundry/config.yml` 長什麼樣是它自己的事（MYL-91）。
    """

    #: 一段「看得出是 Foundry 設定檔」的 yaml 圍欄：帶必填欄位，且拿舊名當欄位。
    def _bad_fence(self, retired, required_key):
        return ("說明文字。\n\n```yaml\n"
                f"foundry: {self._declared()}\n"
                f"{retired}: github\n"
                f"{required_key}:\n  spec_approval: user\n"
                "```\n")

    def _run(self):
        return foundry_lint.check_config_schema(self.root)

    def _schema(self):
        return (self.root / foundry_lint.CONFIG_SCHEMA_REL).read_text(encoding="utf-8")

    def _config(self):
        return (self.root / foundry_lint.CONFIG_REL).read_text(encoding="utf-8")

    def _fields(self):
        return foundry_lint.parse_schema_fields(self._schema())

    def _required(self):
        return sorted(n for n, (req, _) in self._fields().items() if req)

    def _declared(self):
        declared, _ = foundry_lint.parse_schema_versions(self._schema())
        self.assertIsNotNone(declared, "config-schema 讀不出現行版本，反例無從構造")
        return declared

    def _retired(self):
        """挑一個已正名掉的舊欄位名——清單空了的話本組反例整批無從構造。"""
        self.assertTrue(foundry_lint.RETIRED_CONFIG_FIELDS,
                        "`RETIRED_CONFIG_FIELDS` 空了：舊欄位名那一半沒有反例守得住")
        return sorted(foundry_lint.RETIRED_CONFIG_FIELDS)[0]

    def test_真實_repo_通過(self):
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    # ── 欄位名（AC1 第 1 件事）────────────────────────────────────────
    def test_必填欄位名打錯時兩個方向都報(self):
        """只驗「缺必填」的話，讀的人不會知道那個鍵其實就在檔案裡、只是拼錯了。

        逐一把每個必填欄位改成錯名——**不挑一個代表**：挑一個的話，日後某個欄位
        從表格裡掉出必填集合也不會有人發現。
        """
        for name in self._required():
            with self.subTest(field=name):
                typo = name + "_打錯字"
                text = re.sub(rf"^{name}:", typo + ":", self._config(), flags=re.M)
                self.assertNotEqual(text, self._config(), f"`{name}:` 不在頂格")
                self.write(foundry_lint.CONFIG_REL, text)
                res = self._run()
                self.assertFalse(res.passed)
                self.assertTrue(any(f"缺必填欄位 `{name}`" in f for f in res.failures),
                                res.failures)
                self.assertTrue(any(f"`{typo}`" in f and "沒有它" in f
                                    for f in res.failures), res.failures)

    def test_設定檔裡的舊欄位名被擋下(self):
        retired = self._retired()
        self.write(foundry_lint.CONFIG_REL,
                   self._config() + f"\n{retired}: github\n")
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any(f"舊欄位名 `{retired}`" in f for f in res.failures),
                        res.failures)

    def test_範例檔也一起驗(self):
        """`config.example.yml` 是 `foundry-init` 的起點：它寫錯，錯誤會被複製到
        之後導入的每一個專案，而那些專案不會知道自己抄到的是舊名。

        只驗 `.foundry/config.yml` 的話這一格整個沒人管——實測過（把範例檔從比對
        清單拿掉，其餘 235 條測試全綠）。
        """
        rel = foundry_lint.CONFIG_EXAMPLE_REL
        path = self.root / rel
        self.assertTrue(path.exists(), f"{rel} 不存在——比對清單漂了")
        path.write_text(path.read_text(encoding="utf-8")
                        + f"\n{self._retired()}: github\n", encoding="utf-8")
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any(rel in f for f in res.failures), res.failures)

    def test_值域外的值被擋下(self):
        """枚舉來自 config-schema 的表格，不是程式裡另抄的一份。"""
        enums = foundry_lint.parse_schema_enums(self._fields())
        self.assertTrue(enums, "config-schema 一個值域都讀不出來——表的形狀變了")
        name = sorted(enums)[0]
        text = re.sub(rf"^{name}:.*$", f"{name}: 不在值域裡的平台",
                      self._config(), flags=re.M)
        self.assertNotEqual(text, self._config(), f"`{name}:` 不在設定檔頂格")
        self.write(foundry_lint.CONFIG_REL, text)
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("不在值域裡的平台" in f and "值域" in f for f in res.failures),
                        res.failures)

    # ── schema 版本（AC1 第 2 件事）──────────────────────────────────
    def test_設定檔版本與_schema_不一致時擋下(self):
        bogus = str(int(self._declared()) + 1)
        text = re.sub(r"^foundry:.*$", f"foundry: {bogus}", self._config(), flags=re.M)
        self.write(foundry_lint.CONFIG_REL, text)
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("`foundry`" in f and bogus in f for f in res.failures),
                        res.failures)

    def test_schema_自己兩處版本不一致時擋下(self):
        """散文側「目前固定 `N`」與「版本沿革」表最後一列是同一件事寫兩個地方。

        只讀其中一處的話，遞增版本號時漏改另一處，本檢查會拿過期的數字去核設定檔
        而且核得振振有詞——那正是它該擋的那種靜默。
        """
        declared = self._declared()
        bogus = str(int(declared) + 1)
        self.write(foundry_lint.CONFIG_SCHEMA_REL,
                   self._schema().replace(f"目前固定 `{declared}`",
                                          f"目前固定 `{bogus}`", 1))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("自己就不一致" in f for f in res.failures), res.failures)

    # ── 形狀守衛：不只擋「整表讀不出來」，也要擋「只讀錯一格」（MYL-111 §3）──
    def _enum_field(self):
        """型別標「枚舉」而且真的讀得出值域的欄位——本組反例的兩端都從它算。"""
        enums = foundry_lint.parse_schema_enums(self._fields())
        marks = foundry_lint.parse_schema_marks(self._schema())
        names = [n for n in sorted(enums)
                 if marks.get(n, ("", ""))[0] == foundry_lint.CONFIG_SCHEMA_ENUM_TYPE]
        self.assertTrue(names, "schema 一個「枚舉」型別的欄位都讀不出來——反例無從構造")
        return names[0]

    def test_值域的分隔符被改寫時擋下(self):
        """`｜` 換成別的寫法 ⇒ `parse_schema_enums()` 讀空，值域整組靜默消失。

        實測過（審查 §3-1）：改完之後 `devtools_platform: 香蕉` 與 `org.yml` 的
        `ai_platform: banana` **兩個一起放行**，本項仍 `passed=True`。型別欄已經
        寫著「枚舉」，拿它當對照物就叫得出來。
        """
        name = self._enum_field()
        enums = foundry_lint.parse_schema_enums(self._fields())
        fullwidth = "｜".join(f"`{v}`" for v in enums[name])
        halfwidth = " / ".join(f"`{v}`" for v in enums[name])
        schema = self._schema()
        self.assertIn(fullwidth, schema, f"`{name}` 的值域不是預期的寫法——反例沒造出來")
        self.write(foundry_lint.CONFIG_SCHEMA_REL,
                   schema.replace(fullwidth, halfwidth, 1))
        # 反例要證明的是「改了寫法就沒人擋」，所以連值域外的值一起塞進去：
        # 舊實作在這個組合下是全綠的。
        self.write(foundry_lint.CONFIG_REL,
                   re.sub(rf"^{name}:.*$", f"{name}: 香蕉", self._config(), flags=re.M))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any(f"`{name}`" in f and "讀不出值域" in f for f in res.failures),
                        res.failures)

    def test_值域借用解不到時也擋下(self):
        """「值域同 `x`」是第二種來源，寫錯一樣是靜默漏掉。

        只釘直接宣告那一種的話，把借用寫成「值域同 `打錯的名字`」照樣全綠。
        """
        marks = foundry_lint.parse_schema_marks(self._schema())
        enums = foundry_lint.parse_schema_enums(self._fields())
        alias = [n for n, (_, desc) in self._fields().items()
                 if n in enums
                 and marks.get(n, ("", ""))[0] == foundry_lint.CONFIG_SCHEMA_ENUM_TYPE
                 and foundry_lint.CONFIG_SCHEMA_ENUM_ALIAS_RE.search(desc)
                 and not foundry_lint.CONFIG_SCHEMA_ENUM_RE.match(desc)]
        self.assertTrue(alias, "schema 沒有借用型的值域——反例無從構造")
        name = alias[0]
        borrowed = foundry_lint.CONFIG_SCHEMA_ENUM_ALIAS_RE.search(
            self._fields()[name][1]).group(1)
        self.write(foundry_lint.CONFIG_SCHEMA_REL,
                   self._schema().replace(f"值域同 `{borrowed}`",
                                          f"值域同 `{borrowed}_打錯字`", 1))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any(f"`{name}`" in f and "讀不出值域" in f for f in res.failures),
                        res.failures)

    def _lonely_enum_field(self):
        """型別標「枚舉」、而且**沒有別的欄位借用它的值域**的那一個。

        借用型的鄰居會替被借的那一欄叫一聲（`mirror_platform` 寫「值域同
        `devtools_platform`」，自己的型別格是乾淨的），於是被借的那一欄型別格被加
        註記時**看起來**仍有人擋——那是順帶接住的，不是它自己的守衛。反例挑沒有
        鄰居的那一欄，才驗得到型別欄那道白名單本身（審查補正的 M3b 誤判）。
        """
        marks = foundry_lint.parse_schema_marks(self._schema())
        enums = foundry_lint.parse_schema_enums(self._fields())
        borrowed = set()
        for _, (_, desc) in self._fields().items():
            m = foundry_lint.CONFIG_SCHEMA_ENUM_ALIAS_RE.search(desc)
            if m:
                borrowed.add(m.group(1))
        names = [n for n in sorted(enums)
                 if marks.get(n, ("", ""))[0] == foundry_lint.CONFIG_SCHEMA_ENUM_TYPE
                 and n not in borrowed]
        self.assertTrue(names, "schema 沒有值域無人借用的枚舉欄位——反例無從構造")
        return names[0]

    def _edit_row(self, text, name, fn, why):
        """把欄位表裡 `name` 那一列交給 `fn` 改寫，回傳整份文字。

        每一步都斷言「改完 ≠ 原字串」：`replace` 打錯一個字就退化成 no-op，而
        no-op 的表現跟「修好了」一模一樣。
        """
        row = f"| `{name}` |"
        self.assertIn(row, text, f"`{name}` 不在欄位表第一格——反例沒造出來")
        head, sep, tail = text.partition(row)
        line, nl, rest = tail.partition("\n")
        new = fn(line)
        self.assertNotEqual(new, line, f"{why}——反例沒造出來")
        return head + sep + new + nl + rest

    def _annotate_type(self, text, name):
        typ = foundry_lint.CONFIG_SCHEMA_ENUM_TYPE
        return self._edit_row(text, name,
                              lambda line: line.replace(f" {typ} |", f" {typ}（見下） |", 1),
                              "型別格不是預期的寫法")

    def test_型別欄加註記時擋下(self):
        """型別欄的守衛是**白名單**，不是「等於『枚舉』才檢查」的相等比對。

        相等比對認不得 `枚舉（見下）`，失敗方向是靜靜跳過：那一欄的值域守衛整條
        消失，而本項照樣全綠（審查補正實測 M3a）。
        """
        name = self._lonely_enum_field()
        self.write(foundry_lint.CONFIG_SCHEMA_REL,
                   self._annotate_type(self._schema(), name))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any(f"`{name}`" in f and "型別欄寫成" in f for f in res.failures),
                        res.failures)

    def test_型別欄加註記後值域再被改寫也擋下(self):
        """M3a 的下一步：守衛消失之後，把那一欄的值域寫壞不會有任何聲音。

        這一條要證明的是**型別欄那道白名單自己**接住了它——所以同時斷言「讀不出
        值域」那道守衛在本情境下根本沒觸發（型別格已經不是「枚舉」了）。
        """
        name = self._lonely_enum_field()
        text = self._annotate_type(self._schema(), name)
        text = self._edit_row(text, name, lambda line: line.replace("｜", " / "),
                              "值域不是全形分隔符")
        self.write(foundry_lint.CONFIG_SCHEMA_REL, text)
        # 值域讀不出來之後，設定檔那一欄填什麼都沒人管——連值域外的值一起塞進去。
        for rel in (foundry_lint.CONFIG_REL, foundry_lint.ORG_REL):
            cur = (self.root / rel).read_text(encoding="utf-8")
            if re.search(rf"^{name}:", cur, flags=re.M):
                self.write(rel, re.sub(rf"^{name}:.*$", f"{name}: 香蕉", cur, flags=re.M))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any(f"`{name}`" in f and "型別欄寫成" in f for f in res.failures),
                        res.failures)
        self.assertFalse(any(f"`{name}`" in f and "讀不出值域" in f for f in res.failures),
                         f"值域守衛不該是這一組的網子：{res.failures}")

    def test_必填欄加註記時擋下(self):
        """必填欄是拿**整格字面**比對的，`✅（見下）` 會讓該欄位靜靜掉出必填集合。

        實測過（審查 §3-2）：改完之後把 `.foundry/config.yml` 的那一欄整行刪掉，
        本項仍 `passed=True`；而必填集合同時是 `foundry_config_fences()` 判準第 3
        層的證據集，它縮小 ⇒ 舊欄位名掃描的覆蓋跟著無聲變窄。
        """
        name = self._required()[0]
        row = f"| `{name}` |"
        schema = self._schema()
        self.assertIn(row, schema, f"`{name}` 不在欄位表第一格——反例沒造出來")
        head, sep, tail = schema.partition(row)
        line, nl, rest = tail.partition("\n")
        marked = line.replace(f" {foundry_lint.CONFIG_SCHEMA_REQUIRED_MARK} |",
                              f" {foundry_lint.CONFIG_SCHEMA_REQUIRED_MARK}（見下） |", 1)
        self.assertNotEqual(marked, line, "必填格不是預期的寫法——反例沒造出來")
        self.write(foundry_lint.CONFIG_SCHEMA_REL, head + sep + marked + nl + rest)
        # 同時把設定檔那一欄拿掉：舊實作在這個組合下是全綠的。
        self.write(foundry_lint.CONFIG_REL,
                   re.sub(rf"^{name}:.*$", "", self._config(), flags=re.M))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any(f"`{name}`" in f and "必填欄寫成" in f for f in res.failures),
                        res.failures)

    # ── 行完整性：整列有沒有被讀進來（審查 §3-3 的 M4）───────────────────
    def _bold_name_cell(self, text, name):
        """把欄位表裡 `name` 的**欄位名格**加粗——純排版編輯，Markdown 照樣渲染。

        改完斷言「那一列真的從解析結果消失、其餘欄位一列不少」：`replace` 退化成
        no-op、或打到別的地方時，反例會安靜地不成立。
        """
        row = f"| `{name}` |"
        self.assertIn(row, text, f"`{name}` 不在欄位表第一格——反例沒造出來")
        new = text.replace(row, f"| **`{name}`** |", 1)
        after = foundry_lint.parse_schema_fields(new)
        self.assertNotIn(name, after, f"`{name}` 那一列沒有消失——反例沒造出來")
        self.assertEqual(set(foundry_lint.parse_schema_fields(text)) - {name}, set(after),
                         "加粗打到別的列了——反例沒造出來")
        return new

    @staticmethod
    def _drop_top_key(text, name):
        """刪掉頂層鍵 `name` 連同它底下的縮排區塊（沒有就原樣回傳）。"""
        out, dropping = [], False
        for line in text.splitlines(keepends=True):
            if re.match(rf"{re.escape(name)}:(\s|$)", line):
                dropping = True
                continue
            if dropping:
                if line.strip() and not line[:1].isspace():
                    dropping = False
                else:
                    continue
            out.append(line)
        return "".join(out)

    def _org_enum_optional_field(self):
        """選填＋有值域＋`org.yml` 也寫了的那一欄——M4 的構造要件。

        要選填，`config.yml` 才能合法地整段省略它；要 `org.yml` 也寫了，才有一道
        本來擋得住的守衛可以被消失掉。
        """
        fields = self._fields()
        enums = foundry_lint.parse_schema_enums(fields)
        org = foundry_lint.parse_org(
            (self.root / foundry_lint.ORG_REL).read_text(encoding="utf-8"))
        names = [n for n in sorted(enums) if not fields[n][0] and n in org]
        self.assertTrue(names, "沒有「選填＋有值域＋org.yml 也寫了」的欄位——M4 無從構造")
        return names[0]

    def test_欄位名格加粗會讓整列連同三道守衛一起消失(self):
        """兩個**各自都合法**的編輯合起來讓 AC8 整項失效，而本項照樣全綠（審查 M4）。

        `parse_schema_fields()`／`parse_schema_marks()` 都是 regex 不 match 就跳過該
        列（沒有 else），而欄位名格的 regex 兩端錨定 ⇒ 加粗那一列就不見，它的必填／
        型別／值域三道守衛跟著不見。本條先證「值域守衛本來擋得住這個值」，再證
        「加粗之後換成行完整性那道網子接住」——**不是鄰居在叫**：`config.yml` 已經
        依 schema 明文（整段缺席＝未宣告）合法地省掉那一欄，「有頂層欄位但表沒有它」
        那條路走不到。
        """
        name = self._org_enum_optional_field()
        cfg = self._config()
        dropped = self._drop_top_key(cfg, name)
        self.assertNotEqual(dropped, cfg, f"config.yml 沒有 `{name}`——反例沒造出來")
        self.write(foundry_lint.CONFIG_REL, dropped)
        org = (self.root / foundry_lint.ORG_REL).read_text(encoding="utf-8")
        bogus = re.sub(rf"^{name}:.*$", f"{name}: 香蕉", org, flags=re.M)
        self.assertNotEqual(bogus, org, f"org.yml 沒有 `{name}`——反例沒造出來")
        self.write(foundry_lint.ORG_REL, bogus)
        # 對照組：schema 沒動時，值域守衛擋得住這個值——證明下面那一半不是空轉。
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any(f"`{name}`" in f and "值域是" in f for f in res.failures),
                        res.failures)
        # M4：只多加一個粗體，上面那道守衛整條消失，綠字只從「3 組值域」變「2 組」。
        self.write(foundry_lint.CONFIG_SCHEMA_REL,
                   self._bold_name_cell(self._schema(), name))
        res = self._run()
        self.assertFalse(res.passed, "欄位名格加粗 ⇒ 該列連同值域守衛一起消失而全綠（M4）")
        self.assertTrue(any("只解得出" in f for f in res.failures), res.failures)

    def test_欄位名格逐格加粗都擋下(self):
        """逐格 sweep：行完整性是**每一列**都有對照物，不是補在某一欄上的單點。

        補這道守衛之前，同一張 sweep 是 8 紅 1 綠——8 紅全是鄰居（「config.yml 有
        頂層欄位而表沒有它」）順帶接住的，唯一沒有鄰居的那一欄靜靜通過（審查 §3-3）。
        所以這裡**不動設定檔**：紅燈只能來自行完整性自己。
        """
        schema = self._schema()
        names = sorted(foundry_lint.parse_schema_fields(schema))
        self.assertTrue(names, "欄位表是空的——sweep 無從構造")
        for name in names:
            with self.subTest(field=name):
                self.write(foundry_lint.CONFIG_SCHEMA_REL,
                           self._bold_name_cell(schema, name))
                res = self._run()
                self.assertFalse(res.passed)
                self.assertTrue(any("只解得出" in f for f in res.failures), res.failures)

    def test_欄位表少一格時整列消失也擋下(self):
        """同族的另一種：`len(cells) < 4` 也是靜靜跳過，一樣要有對照物。"""
        schema = self._schema()
        name = sorted(foundry_lint.parse_schema_fields(schema))[0]
        text = self._edit_row(schema, name,
                              lambda line: line.rstrip().rsplit("|", 2)[0] + " |",
                              "欄位表那一列不是預期的格數")
        self.assertNotIn(name, foundry_lint.parse_schema_fields(text),
                         f"`{name}` 那一列沒有消失——反例沒造出來")
        self.write(foundry_lint.CONFIG_SCHEMA_REL, text)
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("只解得出" in f for f in res.failures), res.failures)

    def test_舊欄位名映射的現名一定在表裡(self):
        """`RETIRED_CONFIG_FIELDS` 手維護，配一條廉價後盾（審查 §4-5）。"""
        retired = self._retired()
        current = foundry_lint.RETIRED_CONFIG_FIELDS[retired]
        row = f"| `{current}` |"
        self.assertIn(row, self._schema(), f"`{current}` 不在欄位表——後盾無從構造")
        self.write(foundry_lint.CONFIG_SCHEMA_REL,
                   self._schema().replace(row, f"| `{current}_改過名` |", 1))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("RETIRED_CONFIG_FIELDS" in f and f"`{current}`" in f
                            for f in res.failures), res.failures)

    def test_欄位表讀不出來時報紅而不是靜靜通過(self):
        self.write(foundry_lint.CONFIG_SCHEMA_REL,
                   self._schema().replace(
                       "## " + foundry_lint.CONFIG_SCHEMA_TOP_HEADING,
                       "## 設定檔長什麼樣", 1))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("欄位表" in f for f in res.failures), res.failures)

    # ── 選填性：`ai_platform` 不得被驗成必填（本單邊界第 2 條）───────────
    def test_選填欄位缺席不算缺欄位(self):
        """`ai_platform` 是選填（MYL-82 裁定），本項不得把它驗成必填。

        只刪**純量**的選填欄位：物件型的（`platform_options` 那種）刪掉標題行會把
        底下的巢狀鍵留在原地變成頂層鍵，那是把檔案寫壞，不是「欄位缺席」。
        """
        cfg = foundry_lint.parse_config(self._config())
        scalar = [n for n, (req, _) in self._fields().items()
                  if not req and isinstance(cfg.get(n), str)]
        self.assertTrue(scalar, "設定檔一個純量選填欄位都沒有——反例無從構造")
        text = self._config()
        for name in scalar:
            text = re.sub(rf"^{name}:.*$", "", text, flags=re.M)
        self.write(foundry_lint.CONFIG_REL, text)
        res = self._run()
        self.assertTrue(res.passed, res.failures)

    # ── AC8：`org.yml` 側的 `ai_platform` 值域 ───────────────────────
    def test_org_yml_的_ai_platform_值域外被擋下(self):
        """反例要造的是 `org-sync` 漏掉的那個形狀：`config.yml` **沒寫**這一欄。

        兩檔都有寫時 `org-sync` 的比對會先報「兩個值」，那不是本條要證明的事。
        把 `config.yml` 那一欄拿掉，兩檔比對整個不觸發——原本 `banana` 就是從
        這個缺口溜過去的。
        """
        self.write(foundry_lint.CONFIG_REL,
                   re.sub(r"^ai_platform:.*$", "", self._config(), flags=re.M))
        org = (self.root / foundry_lint.ORG_REL).read_text(encoding="utf-8")
        current = foundry_lint.parse_org(org)["ai_platform"]
        self.write(foundry_lint.ORG_REL,
                   org.replace(f"ai_platform: {current}", "ai_platform: banana", 1))
        self.assertTrue(foundry_lint.check_org_sync(self.root).passed,
                        "`org-sync` 這時就紅了——反例沒造出「只有本項擋得住」的那個缺口")
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any(foundry_lint.ORG_REL in f and "banana" in f
                            for f in res.failures), res.failures)

    # ── 文件裡的舊欄位名：判準要分辨得出設定欄位與散文（AC3）────────────
    def test_文件的_yaml_範例用舊欄位名被擋下(self):
        retired = self._retired()
        self.write("skills/drift-sample.md", self._bad_fence(retired, "gates"))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("skills/drift-sample.md:5" in f and retired in f
                            for f in res.failures), res.failures)

    def test_散文提到舊欄位名不誤報(self):
        """MYL-82 實測寬鬆判準會掃出 25 檔而多數只是行文——那種紅字會被習慣性忽略。"""
        retired = self._retired()
        self.write(
            "skills/drift-sample.md",
            f"本欄原名 `{retired}`，MYL-82 正名。\n\n"
            f"| 欄位 | 舊名 |\n| --- | --- |\n| 工具面 | `{retired}` |\n\n"
            f"    {retired}: github\n\n```\n{retired}: github\n```\n",
        )
        self.assertTrue(self._run().passed, self._run().failures)

    def test_不是_Foundry_設定的_yaml_圍欄不誤報(self):
        """`adapters/gitlab.md` 那段 GitLab CI 就是這種：是 yaml，但不是設定檔。"""
        retired = self._retired()
        self.write("skills/drift-sample.md",
                   f"```yaml\npages:\n  script:\n    - build\n{retired}: github\n```\n")
        self.assertTrue(self._run().passed, self._run().failures)

    def test_巢狀鍵不算頂層設定欄位(self):
        retired = self._retired()
        self.write("skills/drift-sample.md",
                   f"```yaml\nfoundry: {self._declared()}\ngates:\n"
                   f"  {retired}: github\n```\n")
        self.assertTrue(self._run().passed, self._run().failures)

    # ── AC4：歷史交付物不回溯改，也就不掃 ────────────────────────────
    def test_歷史交付物不在掃描範圍內(self):
        """`docs/features/` 是各模組**當時**的交付物，改它等於竄改簽核過的文件。"""
        retired = self._retired()
        rel = "docs/features/cross-platform/drift-sample.md"
        self.write(rel, self._bad_fence(retired, "gates"))
        self.assertTrue(self._run().passed, self._run().failures)
        self.assertNotIn(rel, foundry_lint.config_field_scan_targets(self.root))

    def test_排除的只有_docs_features(self):
        """上一條的對照組：同一段內容放在 `docs/` 別處照樣紅。

        少了這條，把排除規則寫成「整個 `docs/` 都不掃」也會通過。
        """
        retired = self._retired()
        self.write("docs/standards/drift-sample.md", self._bad_fence(retired, "gates"))
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any("docs/standards/drift-sample.md" in f for f in res.failures),
                        res.failures)


class TableShapeEntryFileTest(RepoCopyTestCase):
    """`table-shape` 的掃描範圍要涵蓋根目錄雙入口（MYL-85 AC9）。

    那是全 repo 表格最密的兩份檔案，又受「共用正文逐字相同」約束——一處被空行
    切斷會**同時**壞兩份，而在此之前它們完全不在覆蓋內。
    """

    TABLE = "| 欄 | 說明 |\n| --- | --- |\n| a | 甲 |\n"

    def _run(self):
        return foundry_lint.check_table_shape(self.root)

    def test_入口檔的表格被空行切斷時擋下(self):
        for rel in foundry_lint.TABLE_SCAN_FILES:
            with self.subTest(entry=rel):
                self.setUp()    # 每份各從乾淨副本開始
                path = self.root / rel
                self.assertTrue(path.exists(), f"{rel} 不存在——掃描清單漂了")
                self.write(rel, path.read_text(encoding="utf-8")
                           + "\n" + self.TABLE + "\n| b | 乙 |\n")
                res = self._run()
                self.assertFalse(res.passed, f"{rel} 沒被掃到")
                self.assertTrue(any(f.startswith(rel + ":") for f in res.failures),
                                res.failures)

    def test_入口檔的欄數對不上表頭時擋下(self):
        rel = foundry_lint.TABLE_SCAN_FILES[0]
        path = self.root / rel
        self.write(rel, path.read_text(encoding="utf-8")
                   + "\n" + self.TABLE + "| b | 乙 | 多出來的一格 |\n")
        res = self._run()
        self.assertFalse(res.passed)
        self.assertTrue(any(rel in f and "整格丟掉" in f for f in res.failures),
                        res.failures)

    def test_引用區塊內的表格不納入(self):
        """AC9 明寫不納入（全 repo 只有一處、屬歷史交付物）。

        這條是「刻意的缺口」的守衛，不是在慶祝漏檢：日後真要補前綴剝離，
        改的是這條測試的期望，而不是在別處悄悄加一層而沒有人知道範圍變了。
        """
        rel = foundry_lint.TABLE_SCAN_FILES[0]
        quoted = "".join("> " + ln + "\n" for ln in self.TABLE.splitlines())
        self.write(rel, (self.root / rel).read_text(encoding="utf-8")
                   + "\n" + quoted + ">\n> | b | 乙 |\n")
        self.assertTrue(self._run().passed, self._run().failures)


if __name__ == "__main__":
    unittest.main()
