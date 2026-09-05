#!/usr/bin/env python3
"""發佈閘門與防手改偵測的自動化測試（MYL-52，併入 MYL-50 的範圍）。

MYL-50 原本要測的是 `scripts/publish-handbook.sh` 裡那段 shell 閘門邏輯，
因本單要把它改寫成 `publish_docs` 而暫緩。閘門邏輯抽到
`scripts/lib/publish-gate.sh` 之後，它可以單獨執行、不 clone 不 push，
於是**測得動了**——這裡就是那份覆蓋。

三組：
- `PublishGateTest`：MYL-24 證據閘門 ＋ MYL-44 戳記旁路。每個測試各對應一條
  「這樣就該擋下／這樣就該放行」的規則，**每條規則都配一個擋得住的反例**。
- `WikiTamperTest`：MYL-52 防手改偵測。用本機 bare repo 假扮 wiki，證明
  「人為改一頁 wiki 後再跑同步，腳本必須拒絕並報錯」。這是 AC 3 離線可證的那一半；
  真 wiki 上的實測另計（見工單）。
- `DocsConfigTest`：`.foundry/config.yml` 的 `docs` 段是唯一權威。防的是
  「設定檔宣告一套、腳本寫死另一套」——兩邊都看起來正確，跑出來的是腳本那套。

環境需求：只要 `git` 與 `python3`。刻意不碰網路——碰網路的測試在 pre-commit 裡
就是隨機失敗的來源。
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts" / "lib" / "publish-gate.sh"

# 造臨時 repo 前先把繼承來的 `GIT_*` 清掉：git 呼叫 hook 時會設 `GIT_DIR`／
# `GIT_INDEX_FILE`，而它們勝過 `git -C <路徑>`，臨時 repo 會被拉回外層 repo，
# 於是「單獨跑全過、在 pre-commit 裡跑全敗」。`test_foundry_lint.py` 有完整說明，
# 那邊是本單一併修掉的既有缺陷。
for _leaked in [k for k in os.environ if k.startswith("GIT_")]:
    del os.environ[_leaked]

CLEAN_GIT_ENV = dict(os.environ)


def git(root, *args, check=True):
    return subprocess.run(("git", "-C", str(root)) + args,
                          capture_output=True, text=True, check=check,
                          env=CLEAN_GIT_ENV)


class RepoFixture:
    """一個**能通過閘門**的最小 repo：手冊、工具、腳本、mkdocs.yml、main 分支。

    直接複製真 repo 的 `docs/handbook/` 而不是造假章節——投影與戳記的行為都跟
    實際內容有關，用假資料測出來的綠燈證明不了實際會發生什麼。
    """

    def __init__(self, tmp: Path):
        self.root = tmp / "repo"
        self.root.mkdir(parents=True)
        for rel in ("docs/handbook", "tools/foundry-lint", "tools/publish-docs",
                    "scripts", "templates"):
            src = REPO_ROOT / rel
            if src.is_dir():
                shutil.copytree(src, self.root / rel,
                                ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(REPO_ROOT / "mkdocs.yml", self.root / "mkdocs.yml")
        (self.root / "docs" / "publish-reviews").mkdir(parents=True, exist_ok=True)

        git(self.root, "init", "--quiet", "--initial-branch=main")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.test")
        self.commit("初始內容")

    def commit(self, message):
        git(self.root, "add", "-A")
        git(self.root, "commit", "--quiet", "--no-verify", "-m", message)
        return git(self.root, "rev-parse", "HEAD").stdout.strip()

    @property
    def handbook_sha(self):
        return git(self.root, "log", "-1", "--format=%H", "--",
                   "docs/handbook").stdout.strip()

    def write_review(self, name="MYL-TEST.md", verdict="APPROVED", commit=None):
        (self.root / "docs" / "publish-reviews" / name).write_text(
            "---\n"
            "issue: MYL-TEST\n"
            f"verdict: {verdict}\n"
            f"handbook_commit: {commit if commit is not None else self.handbook_sha}\n"
            "reviewer: Tech Lead\n"
            "reviewed_at: 2026-09-04\n"
            "---\n\n# 測試用審查記錄\n",
            encoding="utf-8")
        return self.commit(f"審查記錄 {name}")

    def bump_stamp(self, chapter="03-workflow.md", sha="1234567", date="2026-09-04"):
        """把某一章的戳記行換成新 sha——製造一顆「戳記-only」的手冊 commit。"""
        path = self.root / "docs" / "handbook" / chapter
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.startswith("> 最後對照 protocol"):
                lines[i] = f"> 最後對照 protocol `{sha}`（{date}）"
                break
        else:
            raise AssertionError(f"{chapter} 沒有戳記行，fixture 前提不成立")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_config(self, **docs_fields):
        """寫一份只有 `docs` 段的 `.foundry/config.yml`。

        fixture 預設**不寫**這個檔——那正是「設定缺席時落回 schema 預設」那條
        路徑的測試環境。要測設定驅動的行為時才呼叫。
        """
        lines = ["foundry: 1", "platform: github", "docs:"]
        lines += [f"  {k}: {v}" for k, v in docs_fields.items()]
        cfg = self.root / ".foundry" / "config.yml"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.commit("設定 docs 段")

    def run_gate(self):
        return subprocess.run(["bash", str(GATE), str(self.root)],
                              capture_output=True, text=True, env=CLEAN_GIT_ENV)


class PublishGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = RepoFixture(Path(self.tmp.name))

    def test_no_review_record_is_blocked(self):
        r = self.repo.run_gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("沒有對應的 APPROVED 發佈審查記錄", r.stderr)

    def test_matching_approved_record_passes(self):
        self.repo.write_review()
        r = self.repo.run_gate()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("審查記錄：docs/publish-reviews/MYL-TEST.md", r.stdout)

    def test_non_approved_verdict_is_blocked(self):
        self.repo.write_review(verdict="REJECTED")
        self.assertEqual(self.repo.run_gate().returncode, 1)

    def test_record_for_other_commit_is_blocked(self):
        """閘門綁 commit sha 不綁工單號：改了手冊之後舊記錄自動失效。"""
        self.repo.write_review()
        (self.repo.root / "docs" / "handbook" / "index.md").write_text(
            "# 首頁\n\n改過的內容\n", encoding="utf-8")
        self.repo.commit("改手冊")
        r = self.repo.run_gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("沒有對應的 APPROVED", r.stderr)

    def test_too_short_sha_is_not_accepted(self):
        """短於 7 碼的 handbook_commit 不算數，否則空值或 1 碼前綴會誤中。"""
        self.repo.write_review(commit=self.repo.handbook_sha[:4])
        self.assertEqual(self.repo.run_gate().returncode, 1)

    def test_short_sha_prefix_of_seven_is_accepted(self):
        self.repo.write_review(commit=self.repo.handbook_sha[:7])
        self.assertEqual(self.repo.run_gate().returncode, 0)

    def test_uncommitted_handbook_change_is_blocked(self):
        """有未 commit 的手冊變更時，審查證據對應不到實際內容。"""
        self.repo.write_review()
        (self.repo.root / "docs" / "handbook" / "index.md").write_text(
            "# 首頁\n\n還沒 commit\n", encoding="utf-8")
        r = self.repo.run_gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("未 commit 的變更", r.stderr)

    def test_handbook_change_not_merged_into_main_is_blocked(self):
        """P2 前提 1：只存在於工作分支的內容不得推上公開面。"""
        self.repo.write_review()
        git(self.repo.root, "checkout", "--quiet", "-b", "feat/x")
        (self.repo.root / "docs" / "handbook" / "index.md").write_text(
            "# 首頁\n\n分支上的內容\n", encoding="utf-8")
        self.repo.commit("分支上改手冊")
        self.repo.write_review(name="MYL-TEST2.md")
        r = self.repo.run_gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("尚未合併進 main", r.stderr)

    def test_stamp_only_change_takes_the_bypass(self):
        """MYL-44 旁路：戳記-only 的手冊 diff 免寫新審查記錄，照樣放行。

        沒有這條，戳記 commit 會換掉手冊 sha、找不到記錄，公開面被自己的閘門
        鎖在舊版——那正是同步戳記要避免的事。
        """
        self.repo.write_review()
        self.repo.bump_stamp()
        self.repo.commit("📝 推同步戳記")
        r = self.repo.run_gate()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("戳記旁路（MYL-44）", r.stdout)

    def test_stamp_bypass_is_closed_when_substance_rides_along(self):
        """夾帶任何一行實質內容就落回原閘門——這條洞是封閉的，不是人治例外。"""
        self.repo.write_review()
        self.repo.bump_stamp()
        path = self.repo.root / "docs" / "handbook" / "03-workflow.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n順手夾帶的一句話。\n",
                        encoding="utf-8")
        self.repo.commit("📝 戳記＋夾帶內容")
        r = self.repo.run_gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("不只有同步戳記", r.stderr)

    def test_multiple_stamp_commits_all_listed(self):
        self.repo.write_review()
        self.repo.bump_stamp(sha="1111111")
        self.repo.commit("📝 戳記 1")
        self.repo.bump_stamp(chapter="04-decision-points.md", sha="2222222")
        self.repo.commit("📝 戳記 2")
        r = self.repo.run_gate()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("戳記 1", r.stdout)
        self.assertIn("戳記 2", r.stdout)

    def test_not_a_git_repo_is_blocked(self):
        plain = Path(self.tmp.name) / "plain"
        plain.mkdir()
        r = subprocess.run(["bash", str(GATE), str(plain)],
                           capture_output=True, text=True, env=CLEAN_GIT_ENV)
        self.assertEqual(r.returncode, 1)
        self.assertIn("不是 git repo", r.stderr)

    def test_fixture_repo_is_independent_of_inherited_git_dir(self):
        """回歸守衛：臨時 repo 不可以被繼承來的 `GIT_DIR` 拉回外層 repo。

        這正是本單踩到的既有缺陷——症狀是整組測試只在 pre-commit 底下紅。
        兩件事一起驗：程序環境真的清乾淨了，而且臨時 repo 指的是它自己。
        擋得住的反例：把清理那幾行拿掉，在 hook 底下這一項立刻紅。
        """
        self.assertEqual([k for k in os.environ if k.startswith("GIT_")], [])
        self.assertEqual(
            git(self.repo.root, "rev-parse", "--absolute-git-dir").stdout.strip(),
            str(self.repo.root / ".git"))


class WikiCase(unittest.TestCase):
    """共用的 wiki 測試環境：一個能過閘門的 repo ＋ 一個假扮 wiki 的本機 bare repo。

    本身不含測項（unittest 收集到 0 個），只給下面兩組繼承。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = RepoFixture(Path(self.tmp.name))
        self.repo.write_review()
        self.wiki_remote = Path(self.tmp.name) / "wiki.git"
        subprocess.run(["git", "init", "--quiet", "--bare",
                        "--initial-branch=master", str(self.wiki_remote)],
                       check=True, env=CLEAN_GIT_ENV)
        self.env = dict(CLEAN_GIT_ENV,
                        FOUNDRY_WIKI_URL=str(self.wiki_remote),
                        FOUNDRY_WIKI_HTML="https://example.test/wiki",
                        GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.test",
                        GIT_COMMITTER_NAME="Test",
                        GIT_COMMITTER_EMAIL="test@example.test")

    def publish(self, *args):
        return subprocess.run(
            ["bash", str(self.repo.root / "scripts" / "publish-wiki.sh"), *args],
            capture_output=True, text=True, env=self.env, cwd=str(self.repo.root))

    def clone_wiki(self, name="clone"):
        dest = Path(self.tmp.name) / name
        subprocess.run(["git", "clone", "--quiet", str(self.wiki_remote), str(dest)],
                       check=True, env=CLEAN_GIT_ENV)
        git(dest, "config", "user.name", "Somebody")
        git(dest, "config", "user.email", "somebody@example.test")
        return dest


class WikiTamperTest(WikiCase):
    """防手改偵測：wiki 被手動編輯過就拒絕覆蓋，不是靜靜蓋掉。"""

    def test_empty_wiki_without_bootstrap_is_refused(self):
        """第一次投影要人明確表態，腳本不自己決定「這個 wiki 可以蓋」。"""
        r = self.publish()
        self.assertEqual(r.returncode, 1)
        self.assertIn("防手改偵測", r.stderr)

    def test_bootstrap_publishes_and_records_trailer(self):
        r = self.publish("--bootstrap")
        self.assertEqual(r.returncode, 0, r.stderr)
        wiki = self.clone_wiki()
        self.assertTrue((wiki / "Home.md").exists())
        self.assertTrue((wiki / "_Sidebar.md").exists())
        msg = git(wiki, "log", "-1", "--format=%B").stdout
        self.assertIn("Foundry-Projection:", msg)
        self.assertIn("Foundry-Projection-Digest:", msg)

    def test_second_run_passes_tamper_check(self):
        self.assertEqual(self.publish("--bootstrap").returncode, 0)
        r = self.publish()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("內容未被手改", r.stdout)

    def test_hand_edited_wiki_is_refused(self):
        """AC 3 的核心：人為改一頁 wiki 後再跑同步，必須拒絕並報錯。"""
        self.assertEqual(self.publish("--bootstrap").returncode, 0)
        wiki = self.clone_wiki("tamper")
        (wiki / "Home.md").write_text("# 我在 wiki 上手改的內容\n", encoding="utf-8")
        git(wiki, "add", "-A")
        git(wiki, "commit", "--quiet", "-m", "Updated Home (markdown)")
        git(wiki, "push", "--quiet", "origin", "HEAD")

        r = self.publish()
        self.assertEqual(r.returncode, 1)
        self.assertIn("防手改偵測", r.stderr)
        # 拒絕之後遠端內容必須原封不動——「拒絕覆蓋」是這條規則的重點。
        after = self.clone_wiki("verify")
        self.assertEqual((after / "Home.md").read_text(encoding="utf-8"),
                         "# 我在 wiki 上手改的內容\n")

    def test_forged_commit_message_still_caught_by_digest(self):
        """光抄 trailer 沒有用：內容摘要對不上一樣擋下。"""
        self.assertEqual(self.publish("--bootstrap").returncode, 0)
        wiki = self.clone_wiki("forge")
        old_msg = git(wiki, "log", "-1", "--format=%B").stdout
        (wiki / "Home.md").write_text("# 偽造 trailer 的手改\n", encoding="utf-8")
        git(wiki, "add", "-A")
        git(wiki, "commit", "--quiet", "-m", old_msg)
        git(wiki, "push", "--quiet", "origin", "HEAD")

        r = self.publish()
        self.assertEqual(r.returncode, 1)
        self.assertIn("有人直接在 wiki 上編輯過", r.stderr)

    def test_bootstrap_overrides_tamper_detection_deliberately(self):
        """放棄那筆編輯是**人的決定**，要顯式加旗標才發生。"""
        self.assertEqual(self.publish("--bootstrap").returncode, 0)
        wiki = self.clone_wiki("tamper2")
        (wiki / "Home.md").write_text("# 手改\n", encoding="utf-8")
        git(wiki, "add", "-A")
        git(wiki, "commit", "--quiet", "-m", "Updated Home (markdown)")
        git(wiki, "push", "--quiet", "origin", "HEAD")

        r = self.publish("--bootstrap")
        self.assertEqual(r.returncode, 0, r.stderr)
        # 走的是「HEAD 沒有 trailer」那一支：UI 上的編輯留下的是 GitHub 自己的
        # commit 訊息，trailer 當場消失，摘要那一支根本輪不到。
        self.assertIn("--bootstrap", r.stdout)
        after = self.clone_wiki("verify2")
        self.assertNotEqual((after / "Home.md").read_text(encoding="utf-8"), "# 手改\n")

    def test_gate_failure_stops_before_touching_wiki(self):
        """證據閘門擋下時，wiki 一個位元組都不該動。"""
        (self.repo.root / "docs" / "handbook" / "index.md").write_text(
            "# 首頁\n\n沒有審查記錄的新內容\n", encoding="utf-8")
        self.repo.commit("改手冊但不寫審查記錄")
        r = self.publish("--bootstrap")
        self.assertEqual(r.returncode, 1)
        self.assertIn("發佈審查證據閘門", r.stderr)
        self.assertEqual(git(self.wiki_remote, "log", "--oneline",
                             check=False).returncode, 128)

    def test_dry_run_never_touches_remote(self):
        r = self.publish("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[dry-run]", r.stdout)
        self.assertEqual(git(self.wiki_remote, "log", "--oneline",
                             check=False).returncode, 128)


class DocsConfigTest(WikiCase):
    """`.foundry/config.yml` 的 `docs` 段是唯一權威，腳本不另存一份預設值。

    這一組防的是本 repo 反覆記錄的那種漂移：設定檔宣告一套、腳本寫死另一套，
    兩邊都「看起來正確」，而實際跑出來的是腳本那套。
    """

    def projected_home(self):
        return (self.clone_wiki(f"read-{self.id().rsplit('.', 1)[-1]}")
                / "Home.md").read_text(encoding="utf-8")

    def test_config_plain_policy_is_honoured(self):
        self.repo.write_config(link_policy="plain")
        self.assertEqual(self.publish("--bootstrap").returncode, 0)
        self.assertNotIn("github.com/AugustusHsu/agent-foundry/blob/main",
                         self.projected_home())

    def test_missing_field_falls_back_to_schema_default(self):
        """設定缺席不是錯誤：schema 明訂 `link_policy` 預設 absolute。"""
        r = self.publish("--bootstrap")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("link-policy=absolute", r.stdout)
        self.assertIn("github.com/AugustusHsu/agent-foundry/blob/main",
                      self.projected_home())

    def test_command_line_overrides_config(self):
        self.repo.write_config(link_policy="absolute")
        r = self.publish("--bootstrap", "--link-policy", "plain")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("指令列覆寫", r.stdout)
        self.assertNotIn("github.com/AugustusHsu/agent-foundry/blob/main",
                         self.projected_home())

    def test_illegal_value_stops_before_touching_anything(self):
        """設定寫錯要當場停，不是默默落回預設——默默落回等於設定檔沒有作用。"""
        self.repo.write_config(link_policy="preserve")
        r = self.publish("--bootstrap")
        self.assertEqual(r.returncode, 2)
        self.assertIn("link_policy 只能是", r.stderr)
        self.assertIn("config.yml", r.stderr)
        self.assertEqual(git(self.wiki_remote, "log", "--oneline",
                             check=False).returncode, 128)

    def test_source_dir_comes_from_config(self):
        """`docs.source` 指到別的目錄時，投影的就是那個目錄。"""
        moved = self.repo.root / "docs" / "book"
        shutil.copytree(self.repo.root / "docs" / "handbook", moved)
        (moved / "index.md").write_text("# 搬過家的首頁\n\n## 一節\n", encoding="utf-8")
        self.repo.write_config(source="docs/book/")
        self.assertEqual(self.publish("--bootstrap").returncode, 0)
        self.assertIn("搬過家的首頁", self.projected_home())


if __name__ == "__main__":
    unittest.main()
