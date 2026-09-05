#!/usr/bin/env python3
"""`site_docs`（publish_docs 的 mkdocs 精裝面）的單元測試。MYL-55。

每一項機械檢查都配一個**擋得住的反例**——這是本 repo 對新增檢查的既有要求。
最重要的兩組是：

1. `docs.mirror_site.enabled: false` 之後 `mirror_site_decision` 必須回 False
   （AC2 的邏輯本體）。反例是把同一份設定改成 true 之後它必須回 True，
   否則「永遠回 False」也能通過測試。
2. `verify()` 少一章要紅。反例是完整投影必須全綠。
"""

import shutil
import tempfile
import unittest
from pathlib import Path

import site_docs

REPO_ROOT = Path(__file__).resolve().parents[2]

CONFIG_SAMPLE = """\
foundry: 1
platform: paperclip

platform_options:
  paperclip:
    project_id: "abc-123"     # 行末註解要被吃掉

docs:
  source: docs/handbook/
  primary: wiki
  link_policy: absolute
  mirror_site:
    enabled: true
    trigger: tag
    tag_pattern: 'handbook-v*'

gates:
  external_actions: user
"""

MKDOCS_SAMPLE = """\
site_name: Foundry Handbook
site_url: ""

docs_dir: docs

theme:
  name: material
  features:
    - navigation.top

nav:
  - 首頁: index.md
  - 使用手冊:
      - 手冊首頁: handbook/index.md
      - 1. 走查: handbook/01-first-run.md

plugins:
  - search:
      lang: zh
"""


class ParseConfigTest(unittest.TestCase):
    def test_讀出巢狀純量與行末註解(self):
        docs = site_docs.parse_nested_scalars(CONFIG_SAMPLE, "docs")
        self.assertEqual(docs["source"], "docs/handbook/")
        self.assertEqual(docs["link_policy"], "absolute")
        self.assertEqual(docs["mirror_site"]["tag_pattern"], "handbook-v*")

    def test_只讀指定的頂層段_下一個頂層鍵就停(self):
        docs = site_docs.parse_nested_scalars(CONFIG_SAMPLE, "docs")
        self.assertNotIn("external_actions", docs)
        self.assertNotIn("gates", docs)

    def test_頂層鍵不存在回空_dict(self):
        self.assertEqual(site_docs.parse_nested_scalars(CONFIG_SAMPLE, "nope"), {})

    def test_本_repo_真實設定讀得出精裝站那段(self):
        text = (REPO_ROOT / ".foundry" / "config.yml").read_text(encoding="utf-8")
        docs = site_docs.parse_nested_scalars(text, "docs")
        self.assertIn("mirror_site", docs)
        self.assertIn("tag_pattern", docs["mirror_site"])


class DecisionTest(unittest.TestCase):
    """AC2 的邏輯本體：開關關掉之後 tag 不觸發發佈。"""

    def cfg(self, **overrides):
        docs = site_docs.parse_nested_scalars(CONFIG_SAMPLE, "docs")
        docs["mirror_site"].update(overrides)
        return docs

    def test_開關開著且_tag_相符_發佈(self):
        publish, version, _ = site_docs.mirror_site_decision(self.cfg(), "handbook-v1")
        self.assertTrue(publish)
        self.assertEqual(version, "v1")

    def test_開關關掉_不發佈(self):
        publish, _, reason = site_docs.mirror_site_decision(
            self.cfg(enabled="false"), "handbook-v1")
        self.assertFalse(publish)
        self.assertIn("enabled", reason)

    def test_開關關掉時就算_tag_完全相符也不發佈(self):
        for tag in ("handbook-v1", "handbook-v2", "handbook-v99"):
            publish, _, _ = site_docs.mirror_site_decision(self.cfg(enabled="false"), tag)
            self.assertFalse(publish, tag)

    def test_trigger_不是_tag_不發佈(self):
        publish, _, reason = site_docs.mirror_site_decision(
            self.cfg(trigger="merge"), "handbook-v1")
        self.assertFalse(publish)
        self.assertIn("trigger", reason)

    def test_tag_不符合_pattern_不發佈(self):
        publish, _, reason = site_docs.mirror_site_decision(self.cfg(), "v1")
        self.assertFalse(publish)
        self.assertIn("tag_pattern", reason)

    def test_整段_mirror_site_缺席_不發佈(self):
        publish, _, reason = site_docs.mirror_site_decision(
            {"source": "docs/handbook/"}, "handbook-v1")
        self.assertFalse(publish)
        self.assertIn("mirror_site", reason)

    def test_沒有_docs_段_不發佈(self):
        publish, _, _ = site_docs.mirror_site_decision({}, "handbook-v1")
        self.assertFalse(publish)

    def test_trigger_是_tag_卻缺_tag_pattern_屬設定錯誤而非不發佈(self):
        cfg = self.cfg()
        del cfg["mirror_site"]["tag_pattern"]
        with self.assertRaises(site_docs.ConfigError):
            site_docs.mirror_site_decision(cfg, "handbook-v1")


class VersionTest(unittest.TestCase):
    def test_剝掉用途前綴保留_v(self):
        self.assertEqual(site_docs.version_of("handbook-v1", "handbook-v*"), "v1")
        self.assertEqual(site_docs.version_of("handbook-v2.1", "handbook-v*"), "v2.1")

    def test_pattern_沒有連字號時整段前綴剝掉(self):
        self.assertEqual(site_docs.version_of("v3", "v*"), "3")

    def test_前綴對不上時原樣回傳(self):
        self.assertEqual(site_docs.version_of("other-v1", "handbook-v*"), "other-v1")


class 四碼版本號Test(unittest.TestCase):
    """protocol `V4`：`handbook-v<a>.<b>.<c>.<d>` ＋ `handbook-v*.*.*.*` 的 glob。

    `V4` 的判準（哪一位該動、進位有沒有歸零）機械上驗不到，這裡釘住的是**唯一
    驗得到的那一格**：位數。連同兩個**擋不住**的形狀一起釘——那兩則不是待修的
    bug，是 `V4` 違反段寫明的已知缺口，用測試把「我們知道它漏這裡」變成會回歸的
    事實，免得日後有人看到 glob 就以為形狀已經全包了。
    """

    GLOB = "handbook-v*.*.*.*"

    def cfg(self):
        docs = site_docs.parse_nested_scalars(CONFIG_SAMPLE, "docs")
        docs["mirror_site"]["tag_pattern"] = self.GLOB
        return docs

    def test_本_repo_真實設定用的就是四碼_glob(self):
        """設定檔漂回 `handbook-v*` 的話，下面那些反例會全部失效而沒人發現。"""
        text = (REPO_ROOT / ".foundry" / "config.yml").read_text(encoding="utf-8")
        docs = site_docs.parse_nested_scalars(text, "docs")
        self.assertEqual(docs["mirror_site"]["tag_pattern"], self.GLOB)

    def test_位數不足的舊形狀一律不發佈(self):
        for tag in ("handbook-v1", "handbook-v1.1", "handbook-v1.1.1"):
            publish, _, reason = site_docs.mirror_site_decision(self.cfg(), tag)
            self.assertFalse(publish, tag)
            self.assertIn("tag_pattern", reason)

    def test_四碼放行且版本名保留四碼(self):
        publish, version, _ = site_docs.mirror_site_decision(
            self.cfg(), "handbook-v0.0.0.1")
        self.assertTrue(publish)
        self.assertEqual(version, "v0.0.0.1")

    def test_version_of_不必為四碼改實作(self):
        """`version_of()` 只剝前綴、不解析版本，換形狀不用回去改它。"""
        self.assertEqual(
            site_docs.version_of("handbook-v0.0.5.7", self.GLOB), "v0.0.5.7")

    def test_已知缺口_多一位與非數字都擋不住(self):
        """`fnmatch` 只數點不看內容——這兩格靠 `V4` 的自律那半。"""
        for tag in ("handbook-v0.0.0.1.2", "handbook-v0.0.0.x"):
            publish, _, _ = site_docs.mirror_site_decision(self.cfg(), tag)
            self.assertTrue(publish, f"{tag}：缺口的形狀變了就要回頭改 `V4` 違反段")


VERSIONS_JSON = """\
[
  {"version": "v1", "title": "v1", "aliases": ["latest"]},
  {"version": "v2", "title": "v2", "aliases": []}
]
"""


class PublishedVersionsTest(unittest.TestCase):
    """`V3` 的資料面：讀得出 gh-pages 上已經有哪幾版。"""

    def test_只取_version_欄位(self):
        self.assertEqual(site_docs.published_versions(VERSIONS_JSON), ["v1", "v2"])

    def test_別名不算已發佈版本(self):
        """反例守衛：把 aliases 一起收進來的話，`latest` 會讓第二版起全部被擋。"""
        self.assertNotIn("latest", site_docs.published_versions(VERSIONS_JSON))

    def test_空字串等於還沒發過任何版本(self):
        self.assertEqual(site_docs.published_versions(""), [])
        self.assertEqual(site_docs.published_versions("  \n"), [])

    def test_純字串陣列的舊格式也讀得出來(self):
        self.assertEqual(site_docs.published_versions('["v1"]'), ["v1"])

    def test_壞掉的_JSON_要_raise_而不是當成沒發過(self):
        """讀不懂就擋下。回空清單等於放行，代價是覆蓋掉一版已發佈的手冊。"""
        with self.assertRaises(site_docs.ConfigError):
            site_docs.published_versions("{ 這不是 JSON")

    def test_不是陣列時要_raise(self):
        with self.assertRaises(site_docs.ConfigError):
            site_docs.published_versions('{"version": "v1"}')


class RepublishDecisionTest(unittest.TestCase):
    """`V3` 的判斷面：同版本重打擋下，`workflow_dispatch` 重建放行。"""

    def test_版本已發佈且是_tag_推送_擋下(self):
        ok, reason = site_docs.republish_decision("v1", ["v1"], rebuild=False)
        self.assertFalse(ok)
        self.assertIn("V3", reason)
        self.assertIn("bump", reason)  # 訊息要講得出「下一步做什麼」，不只說不行

    def test_新版本放行(self):
        """反例守衛：若判斷寫成「永遠擋下」，這一項會失敗。"""
        ok, _ = site_docs.republish_decision("v2", ["v1"], rebuild=False)
        self.assertTrue(ok)

    def test_第一次發佈時清單是空的_放行(self):
        ok, _ = site_docs.republish_decision("v1", [], rebuild=False)
        self.assertTrue(ok)

    def test_workflow_dispatch_重建同一版放行(self):
        """重建同一顆 commit 不是「重打」——判準是內容變沒變，不是跑了幾次。"""
        ok, reason = site_docs.republish_decision("v1", ["v1"], rebuild=True)
        self.assertTrue(ok)
        self.assertIn("workflow_dispatch", reason)

    def test_重建路徑不會讓判斷整個失效(self):
        """反例守衛：rebuild 若被寫成無條件放行，上面那項也會過；
        這一項確保沒有 rebuild 時同一組輸入仍然是擋下的。"""
        blocked, _ = site_docs.republish_decision("v1", ["v1"], rebuild=False)
        allowed, _ = site_docs.republish_decision("v1", ["v1"], rebuild=True)
        self.assertFalse(blocked)
        self.assertTrue(allowed)


class CheckVersionCliTest(unittest.TestCase):
    """CI 的 `gate` job 直接吃這支的離開碼，所以離開碼本身要有測試守著。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.vj = self.tmp / "versions.json"
        self.vj.write_text(VERSIONS_JSON, encoding="utf-8")

    def run_cli(self, *extra):
        return site_docs.main(
            ["check-version", "--versions-json", str(self.vj), *extra])

    def test_撞到已發佈版本回_3(self):
        self.assertEqual(self.run_cli("--version", "v1"), 3)

    def test_新版本回_0(self):
        self.assertEqual(self.run_cli("--version", "v9"), 0)

    def test_重建路徑回_0(self):
        self.assertEqual(self.run_cli("--version", "v1", "--rebuild"), 0)

    def test_versions_json_路徑不存在時回_2_而不是放行(self):
        """路徑打錯若當成「沒有已發佈版本」，這道閘門就退化成恆真。"""
        self.assertEqual(
            site_docs.main(["check-version", "--version", "v1",
                            "--versions-json", str(self.tmp / "nope.json")]), 2)

    def test_gh_pages_還不存在時呼叫端寫_空陣列_放行(self):
        self.vj.write_text("[]\n", encoding="utf-8")
        self.assertEqual(self.run_cli("--version", "v1"), 0)


class RewriteLinksTest(unittest.TestCase):
    ABS = "https://github.com/AugustusHsu/agent-foundry/blob/main"

    def rw(self, text, policy="absolute"):
        return site_docs.rewrite_repo_links(text, policy, self.ABS)

    def test_章間連結與錨點原樣保留(self):
        """精裝面的渲染器與來源一樣，改了才是錯的。"""
        src = "看 [第 4 章](04-decision-points.md#3-hitl) 與 [本章](#1)。\n"
        self.assertEqual(self.rw(src), src)

    def test_repo_內部路徑改寫成絕對_URL(self):
        out = self.rw("見 [protocol](../../skills/foundry-protocol/SKILL.md)。\n")
        self.assertIn(f"{self.ABS}/skills/foundry-protocol/SKILL.md", out)

    def test_repo_內部路徑帶錨點時錨點跟著搬(self):
        out = self.rw("見 [模板](../../templates/publish-review.md#前提)。\n")
        self.assertIn(f"{self.ABS}/templates/publish-review.md#前提", out)

    def test_plain_政策拆為純文字(self):
        out = self.rw("見 [protocol](../../skills/foundry-protocol/SKILL.md)。\n", "plain")
        self.assertEqual(out, "見 protocol。\n")

    def test_外部連結不動(self):
        src = "見 [GitHub](https://github.com/x/y)。\n"
        self.assertEqual(self.rw(src), src)

    def test_圍欄內的連結語法不算連結(self):
        src = "```md\n[x](../../skills/a.md)\n```\n"
        self.assertEqual(self.rw(src), src)


class SiteMkdocsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def nav_of(self, text):
        path = self.tmp / "mkdocs.yml"
        path.write_text(text, encoding="utf-8")
        return site_docs.read_nav(path)

    def build(self):
        return site_docs.build_site_mkdocs_yaml(
            MKDOCS_SAMPLE, self.nav_of(MKDOCS_SAMPLE), "https://example.test/")

    def test_nav_攤平且只留手冊章節(self):
        out = self.build()
        self.assertIn("  - 手冊首頁: index.md", out)
        self.assertIn("  - 1. 走查: 01-first-run.md", out)
        self.assertNotIn("handbook/", out)
        # 私有站根目錄的 `首頁: index.md` 不屬手冊，轉寫時不應混進來。
        self.assertNotIn("- 首頁:", out)

    def test_site_url_被換掉(self):
        out = self.build()
        self.assertIn("site_url: https://example.test/", out)
        self.assertNotIn('site_url: ""', out)

    def test_版本選擇器與_edit_uri_補上(self):
        out = self.build()
        self.assertIn("provider: mike", out)
        self.assertIn('edit_uri: ""', out)

    def test_theme_與_plugins_原樣沿用(self):
        """不另寫一份渲染設定：本機預覽與公開站的錨點才會算出同一個 slug。"""
        out = self.build()
        self.assertIn("  name: material", out)
        self.assertIn("      lang: zh", out)

    def test_私有_nav_多一章時站台_nav_跟著多(self):
        """反例守衛：nav 若是寫死的，這一項會失敗。"""
        extended = MKDOCS_SAMPLE.replace(
            "      - 1. 走查: handbook/01-first-run.md",
            "      - 1. 走查: handbook/01-first-run.md\n"
            "      - 9. 新章: handbook/09-new.md",
        )
        out = site_docs.build_site_mkdocs_yaml(
            extended, self.nav_of(extended), "https://example.test/")
        self.assertIn("  - 9. 新章: 09-new.md", out)


class BuildAndVerifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = self.tmp / "handbook"
        self.src.mkdir()
        (self.src / "index.md").write_text(
            "# 手冊\n\n見 [走查](01-first-run.md) 與 "
            "[protocol](../../skills/foundry-protocol/SKILL.md)。\n", encoding="utf-8")
        (self.src / "01-first-run.md").write_text(
            "# 1. 走查\n\n## 1.1 開始\n\n內文。\n", encoding="utf-8")
        self.mkdocs = self.tmp / "mkdocs.yml"
        self.mkdocs.write_text(MKDOCS_SAMPLE, encoding="utf-8")
        self.out = self.tmp / "site"

    def do_build(self):
        return site_docs.build(
            self.src, self.mkdocs, self.out, "absolute", "https://example.test/",
            "https://github.com/AugustusHsu/agent-foundry/blob/main")

    def test_完整投影逐章比對全綠(self):
        self.do_build()
        nav = site_docs.read_nav(self.mkdocs)
        self.assertEqual(site_docs.verify(self.src, self.out, nav), [])

    def test_少一章就紅(self):
        self.do_build()
        (self.out / "docs" / "01-first-run.md").unlink()
        nav = site_docs.read_nav(self.mkdocs)
        problems = site_docs.verify(self.src, self.out, nav)
        self.assertTrue(any("01-first-run.md" in p for p in problems), problems)

    def test_內容被動過手腳導致標題消失就紅(self):
        self.do_build()
        page = self.out / "docs" / "01-first-run.md"
        page.write_text("# 1. 走查\n\n內文。\n", encoding="utf-8")
        nav = site_docs.read_nav(self.mkdocs)
        self.assertTrue(site_docs.verify(self.src, self.out, nav))

    def test_首頁被插入來源提示且冪等(self):
        self.do_build()
        first = (self.out / "docs" / "index.md").read_text(encoding="utf-8")
        self.assertIn("本站是機械投影", first)
        self.assertEqual(first.count("本站是機械投影"), 1)
        self.do_build()
        again = (self.out / "docs" / "index.md").read_text(encoding="utf-8")
        self.assertEqual(first, again, "同樣的來源必須產出同樣的位元組（§3.9 行為 3）")

    def test_讀不到_nav_時拒絕建置(self):
        self.mkdocs.write_text("site_name: x\n", encoding="utf-8")
        with self.assertRaises(site_docs.ConfigError):
            self.do_build()


if __name__ == "__main__":
    unittest.main()
