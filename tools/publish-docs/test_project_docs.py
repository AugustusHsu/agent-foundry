#!/usr/bin/env python3
"""`project_docs` 與 `compare_projection` 的單元測試（MYL-52）。

每個測試對應一個**具體會壞掉的東西**，不是為了覆蓋率：
投影改寫連結，改寫錯了 wiki 上就是一片死連結，而本機沒有渲染器可以事後發現
（known-drift `X4`）。所以能在這一層機械證明的，就不要留到實站才知道。
"""

import tempfile
import unittest
from pathlib import Path

import compare_projection
import project_docs


class GithubSlugTest(unittest.TestCase):
    """GitHub 的 slugger 保留 CJK，mkdocs 的丟掉——這個差異是整套錨點改寫的起點。"""

    def test_cjk_survives(self):
        self.assertEqual(project_docs.github_slug("3. HITL 發卡"), "3-hitl-發卡")

    def test_differs_from_mkdocs(self):
        heading = "3. HITL 發卡"
        self.assertEqual(project_docs.mkdocs_slug(heading), "3-hitl")
        self.assertNotEqual(
            project_docs.mkdocs_slug(heading), project_docs.github_slug(heading)
        )

    def test_pure_cjk_heading_is_empty_in_mkdocs_but_not_github(self):
        """純中文標題在 mkdocs 是空 slug；共用一份去重計數會錯位，所以要分開算。"""
        self.assertEqual(project_docs.mkdocs_slug("流程"), "")
        self.assertEqual(project_docs.github_slug("流程"), "流程")

    def test_inline_markup_stripped(self):
        self.assertEqual(project_docs.github_slug("`make check` 是什麼"),
                         "make-check-是什麼")

    def test_duplicate_headings_get_suffix(self):
        # H1 也會產生錨點，所以 `t` 一併在集合裡。
        text = "# T\n\n## 一\n\n## 一\n"
        self.assertEqual(project_docs.github_anchors(text), {"t", "一", "一-1"})


class RepoPathTest(unittest.TestCase):
    def test_up_two_levels_reaches_repo_root(self):
        self.assertEqual(project_docs.repo_path_of("../../skills/x/SKILL.md"),
                         "skills/x/SKILL.md")

    def test_sibling_dir_stays_under_docs(self):
        self.assertEqual(project_docs.repo_path_of("../pilot/pilot-log.md"),
                         "docs/pilot/pilot-log.md")


class RewriteLinksTest(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "index.md": "# 首頁\n\n## 導覽\n",
            "03-workflow.md": "# 3\n\n## 3. HITL 發卡\n\n## 一般段落\n",
        }

    def rewrite(self, text, name="index.md", policy="absolute"):
        out, warns = project_docs.rewrite_links(
            text, name, self.sources, policy, "https://example.test/blob/main")
        return out, warns

    def test_chapter_link_loses_md_suffix(self):
        out, _ = self.rewrite("見 [流程](03-workflow.md)。")
        self.assertIn("[流程](03-workflow)", out)

    def test_index_becomes_home(self):
        out, _ = self.rewrite("回 [首頁](index.md)。", name="03-workflow.md")
        self.assertIn("[首頁](Home)", out)

    def test_anchor_is_translated_to_github_slug(self):
        out, _ = self.rewrite("見 [發卡](03-workflow.md#3-hitl)。")
        self.assertIn("[發卡](03-workflow#3-hitl-發卡)", out)

    def test_unknown_anchor_warns_and_keeps_target(self):
        out, warns = self.rewrite("見 [x](03-workflow.md#nope)。")
        self.assertIn("#nope", out)
        self.assertTrue(any("沒有對得上的標題" in w for w in warns))

    def test_repo_path_absolute_policy(self):
        out, _ = self.rewrite("見 [規範](../../skills/foundry-protocol/SKILL.md)。")
        self.assertIn("(https://example.test/blob/main/skills/foundry-protocol/SKILL.md)",
                      out)

    def test_repo_path_plain_policy_keeps_label_only(self):
        out, _ = self.rewrite("見 [規範](../../skills/foundry-protocol/SKILL.md)。",
                              policy="plain")
        self.assertIn("見 規範。", out)
        self.assertNotIn("](", out)

    def test_external_url_untouched(self):
        text = "見 [repo](https://github.com/AugustusHsu/agent-foundry#readme)。"
        out, _ = self.rewrite(text)
        self.assertEqual(out, text)

    def test_links_inside_code_fence_untouched(self):
        """圍欄裡的 `[x](y)` 是語法示例，改了就是竄改內容。"""
        text = "```\n[流程](03-workflow.md)\n```\n"
        out, _ = self.rewrite(text)
        self.assertIn("[流程](03-workflow.md)", out)


class DigestTest(unittest.TestCase):
    def test_same_pages_same_digest(self):
        a = {"Home.md": "x", "01.md": "y"}
        self.assertEqual(project_docs.digest_of(a), project_docs.digest_of(dict(a)))

    def test_swapping_filenames_changes_digest(self):
        """只雜湊內容的話，兩頁互換檔名不會被察覺——所以頁名要一起餵進去。"""
        a = {"Home.md": "x", "01.md": "y"}
        b = {"Home.md": "y", "01.md": "x"}
        self.assertNotEqual(project_docs.digest_of(a), project_docs.digest_of(b))

    def test_dir_digest_matches_in_memory(self):
        pages = {"Home.md": "# a\n", "01.md": "# b\n"}
        with tempfile.TemporaryDirectory() as d:
            for name, body in pages.items():
                (Path(d) / name).write_text(body, encoding="utf-8")
            self.assertEqual(project_docs.digest_of(pages),
                             project_docs.digest_of_dir(Path(d)))


class NavTest(unittest.TestCase):
    def test_sidebar_is_transcribed_from_mkdocs_not_hand_written(self):
        """側欄轉寫既有 mkdocs.yml，避免變成 known-drift 記的「第三份 nav」。"""
        with tempfile.TemporaryDirectory() as d:
            yml = Path(d) / "mkdocs.yml"
            yml.write_text(
                "nav:\n"
                "  - 首頁: index.md\n"
                "  - 使用手冊:\n"
                "      - 手冊首頁: handbook/index.md\n"
                "      - 1. 走查: handbook/01-first-run.md\n",
                encoding="utf-8")
            nav = project_docs.read_nav(yml)
        self.assertEqual(nav, [("手冊首頁", "index.md"), ("1. 走查", "01-first-run.md")])
        self.assertIn("- [1. 走查](01-first-run)", project_docs.build_sidebar(nav))


class CompareTest(unittest.TestCase):
    """比對表是閘門本身：任何一格紅就不 push。逐個失效模式各驗一次。"""

    STAMP = "> 最後對照 protocol `abcdef1234`（2026-09-04）"

    def build(self, src_pages, wiki_pages):
        d = Path(self.tmp.name)
        src, wiki = d / "src", d / "wiki"
        src.mkdir(exist_ok=True)
        wiki.mkdir(exist_ok=True)
        for p in list(src.glob("*.md")) + list(wiki.glob("*.md")):
            p.unlink()
        for name, body in src_pages.items():
            (src / name).write_text(body, encoding="utf-8")
        for name, body in wiki_pages.items():
            (wiki / name).write_text(body, encoding="utf-8")
        return compare_projection.compare(src, wiki)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.good_src = {"index.md": "# 首頁\n\n## 一節\n"}
        self.good_wiki = {"Home.md": "# 首頁\n\n## 一節\n",
                          "_Sidebar.md": "x", "_Footer.md": "y"}

    def test_all_green(self):
        reports, global_problems = self.build(self.good_src, self.good_wiki)
        self.assertEqual(global_problems, [])
        self.assertTrue(all(r.ok for r in reports))

    def test_missing_chapter_is_red(self):
        reports, _ = self.build({**self.good_src, "01-x.md": "# 一\n"}, self.good_wiki)
        bad = [r for r in reports if not r.ok]
        self.assertEqual(len(bad), 1)
        self.assertIn("整章沒搬過去", bad[0].problems[0])

    def test_truncated_content_is_red(self):
        src = {"index.md": "# 首頁\n\n## 一節\n\n## 二節\n"}
        reports, _ = self.build(src, self.good_wiki)
        self.assertIn("二級章節數不一致", reports[0].problems[0])

    def test_h1_mismatch_is_red(self):
        wiki = dict(self.good_wiki, **{"Home.md": "# 別的標題\n\n## 一節\n"})
        reports, _ = self.build(self.good_src, wiki)
        self.assertIn("H1 標題不一致", reports[0].problems[0])

    def test_dropped_stamp_is_red(self):
        src = {"03-workflow.md": f"# 三\n\n{self.STAMP}\n\n## 一節\n"}
        wiki = {"03-workflow.md": "# 三\n\n## 一節\n", "_Sidebar.md": "x", "_Footer.md": "y"}
        reports, _ = self.build(src, wiki)
        self.assertTrue(any("戳記行沒存活" in p for p in reports[0].problems))

    def test_surviving_stamp_is_green(self):
        body = f"# 三\n\n{self.STAMP}\n\n## 一節\n"
        reports, _ = self.build({"03-workflow.md": body},
                                {"03-workflow.md": body, "_Sidebar.md": "x",
                                 "_Footer.md": "y"})
        self.assertTrue(reports[0].ok)
        self.assertEqual(reports[0].stamp, "✅ 存活")

    def test_broken_link_target_is_red(self):
        wiki = dict(self.good_wiki,
                    **{"Home.md": "# 首頁\n\n## 一節\n\n見 [x](99-nope)。\n"})
        reports, _ = self.build(self.good_src, wiki)
        self.assertTrue(any("指向 wiki 沒有的頁面" in p for p in reports[0].problems))

    def test_broken_anchor_is_red(self):
        wiki = dict(self.good_wiki,
                    **{"Home.md": "# 首頁\n\n## 一節\n\n見 [x](Home#沒這個)。\n"})
        reports, _ = self.build(self.good_src, wiki)
        self.assertTrue(any("錨點在" in p for p in reports[0].problems))

    def test_hand_created_page_is_flagged(self):
        wiki = dict(self.good_wiki, **{"我自己加的.md": "# 手寫\n"})
        _, global_problems = self.build(self.good_src, wiki)
        self.assertTrue(any("多半是有人手動建的頁面" in p for p in global_problems))

    def test_real_handbook_projects_green(self):
        """跑真的手冊：投影完必須全綠，否則本單的 AC 2 當場不成立。"""
        root = Path(__file__).resolve().parents[2]
        src = root / "docs" / "handbook"
        if not src.is_dir():
            self.skipTest("不在 repo 內")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            pages, _ = project_docs.project(src, root / "mkdocs.yml", "deadbeef")
            for name, body in pages.items():
                (out / name).write_text(body, encoding="utf-8")
            reports, global_problems = compare_projection.compare(src, out)
        self.assertEqual(global_problems, [])
        self.assertEqual([r.source for r in reports if not r.ok], [])
        self.assertEqual(len(reports), len(list(src.glob("*.md"))))


if __name__ == "__main__":
    unittest.main()
