"""probe_browser 的單元測試（MYL-37）。

測試重點是**判級規則**與**那兩個實際踩過的坑**：
宣告了但沒放行、以及放行規則寫對了卻因工作區未信任而整份被忽略。
瀏覽器二進位與設定檔內容全部以參數注入，不碰真實檔案系統與 PATH。
"""

import json
import struct
import unittest
from pathlib import Path

import probe_browser as pb

ROOT = Path("/repo")


def fake_which(available):
    """把一組可用指令做成 which 替身。"""
    return lambda cmd: f"/usr/bin/{cmd}" if cmd in available else None


def fake_read(files):
    """把「檔名 → 內容」做成 read 替身，未登記的檔名一律當作不存在。"""
    return lambda path: files.get(Path(path).name)


def trust_config(trusted=True, root=ROOT):
    """`~/.claude.json` 的最小形狀。"""
    return json.dumps({"projects": {str(root): {"hasTrustDialogAccepted": trusted}}})


MCP_BOTH = json.dumps(
    {
        "mcpServers": {
            "chrome-devtools": {"command": "npx", "args": ["-y", "chrome-devtools-mcp@1.8.0", "--isolated"]},
            "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@0.0.80", "--browser", "chrome"]},
        }
    }
)
MCP_CDP_ONLY = json.dumps(
    {"mcpServers": {"chrome-devtools": {"command": "npx", "args": ["chrome-devtools-mcp@1.8.0"]}}}
)
ALLOW_BOTH = json.dumps({"permissions": {"allow": ["mcp__chrome-devtools", "mcp__playwright"]}})


class ParseDeclarationsTest(unittest.TestCase):
    def test_recognises_versioned_package_names(self):
        declared = pb.parse_mcp_declarations(MCP_BOTH)
        self.assertEqual(declared["chrome-devtools-mcp"], "chrome-devtools")
        self.assertEqual(declared["@playwright/mcp"], "playwright")

    def test_server_name_need_not_match_package_name(self):
        text = json.dumps({"mcpServers": {"我的瀏覽器": {"command": "npx", "args": ["chrome-devtools-mcp"]}}})
        self.assertEqual(pb.parse_mcp_declarations(text), {"chrome-devtools-mcp": "我的瀏覽器"})

    def test_broken_or_missing_json_counts_as_no_declaration(self):
        # 壞掉的 .mcp.json harness 也載入不了，據實回報「沒有」而不是假設有。
        self.assertEqual(pb.parse_mcp_declarations("{ not json"), {})
        self.assertEqual(pb.parse_mcp_declarations(None), {})
        self.assertEqual(pb.parse_mcp_declarations(json.dumps({})), {})

    def test_unregistered_package_is_ignored(self):
        text = json.dumps({"mcpServers": {"serena": {"command": "uvx", "args": ["serena"]}}})
        self.assertEqual(pb.parse_mcp_declarations(text), {})


class AllowRuleTest(unittest.TestCase):
    def test_merges_allow_lists_across_settings_files(self):
        a = json.dumps({"permissions": {"allow": ["Bash(curl:*)"]}})
        b = json.dumps({"permissions": {"allow": ["mcp__playwright"]}})
        self.assertEqual(pb.parse_allow_rules([a, None, b]), ["Bash(curl:*)", "mcp__playwright"])

    def test_server_level_rule_covers_its_tools(self):
        self.assertTrue(pb.is_allowed("playwright", ["mcp__playwright"]))

    def test_tool_level_rule_counts_as_allowed(self):
        self.assertTrue(pb.is_allowed("playwright", ["mcp__playwright__browser_navigate"]))

    def test_similar_prefix_does_not_leak(self):
        # `mcp__chrome-devtools-extra` 不得被當成 `chrome-devtools` 的放行。
        self.assertFalse(pb.is_allowed("chrome-devtools", ["mcp__chrome-devtools-extra"]))
        self.assertFalse(pb.is_allowed("chrome-devtools", []))


class TrustTest(unittest.TestCase):
    def test_missing_config_is_untrusted(self):
        self.assertFalse(pb.is_workspace_trusted(ROOT, read=fake_read({})))

    def test_broken_config_is_untrusted(self):
        self.assertFalse(pb.is_workspace_trusted(ROOT, read=fake_read({".claude.json": "{ nope"})))

    def test_flag_false_is_untrusted(self):
        read = fake_read({".claude.json": trust_config(trusted=False)})
        self.assertFalse(pb.is_workspace_trusted(ROOT, read=read))

    def test_other_project_trusted_does_not_count(self):
        read = fake_read({".claude.json": trust_config(root=Path("/somewhere/else"))})
        self.assertFalse(pb.is_workspace_trusted(ROOT, read=read))

    def test_flag_true_is_trusted(self):
        self.assertTrue(pb.is_workspace_trusted(ROOT, read=fake_read({".claude.json": trust_config()})))


class ProbeMcpTest(unittest.TestCase):
    def _statuses(self, files):
        results = pb.probe_mcp(ROOT, read=fake_read(files))
        return {r["package"]: r["status"] for r in results}

    def test_project_settings_count_when_workspace_is_trusted(self):
        statuses = self._statuses(
            {".mcp.json": MCP_BOTH, "settings.json": ALLOW_BOTH, ".claude.json": trust_config()}
        )
        self.assertEqual(statuses["chrome-devtools-mcp"], pb.ALLOWED)
        self.assertEqual(statuses["@playwright/mcp"], pb.ALLOWED)

    def test_project_settings_are_ignored_when_untrusted(self):
        # 實測撞到的：設定檔看起來完全正確，但整份被忽略、呼叫全被擋。
        statuses = self._statuses({".mcp.json": MCP_BOTH, "settings.json": ALLOW_BOTH})
        self.assertEqual(statuses["chrome-devtools-mcp"], pb.ALLOWED_BUT_UNTRUSTED)
        self.assertEqual(statuses["@playwright/mcp"], pb.ALLOWED_BUT_UNTRUSTED)

    def test_local_settings_work_without_trust(self):
        statuses = self._statuses({".mcp.json": MCP_BOTH, "settings.local.json": ALLOW_BOTH})
        self.assertEqual(statuses["chrome-devtools-mcp"], pb.ALLOWED)
        self.assertEqual(statuses["@playwright/mcp"], pb.ALLOWED)

    def test_declared_but_not_allowed_is_its_own_state(self):
        statuses = self._statuses({".mcp.json": MCP_BOTH})
        self.assertEqual(statuses["chrome-devtools-mcp"], pb.DECLARED_NOT_ALLOWED)

    def test_not_declared(self):
        self.assertEqual(self._statuses({})["chrome-devtools-mcp"], pb.NOT_DECLARED)

    def test_partial_local_allow(self):
        files = {
            ".mcp.json": MCP_BOTH,
            "settings.local.json": json.dumps({"permissions": {"allow": ["mcp__playwright"]}}),
        }
        statuses = self._statuses(files)
        self.assertEqual(statuses["@playwright/mcp"], pb.ALLOWED)
        self.assertEqual(statuses["chrome-devtools-mcp"], pb.DECLARED_NOT_ALLOWED)


class ComputeLevelTest(unittest.TestCase):
    def _mcp(self, **statuses):
        return [
            {"package": p["package"], "status": statuses.get(p["package"], pb.NOT_DECLARED), "deep": p["deep"]}
            for p in pb.MCP_PACKAGES
        ]

    def test_no_browser_is_l0(self):
        self.assertEqual(pb.compute_level([], self._mcp(), has_npx=True), 0)

    def test_browser_without_usable_mcp_is_l1(self):
        self.assertEqual(pb.compute_level([{"id": "chrome"}], self._mcp(), has_npx=True), 1)

    def test_declared_but_not_allowed_does_not_reach_l2(self):
        mcp = self._mcp(**{"@playwright/mcp": pb.DECLARED_NOT_ALLOWED})
        self.assertEqual(pb.compute_level([{"id": "chrome"}], mcp, has_npx=True), 1)

    def test_untrusted_does_not_reach_l2(self):
        # 規則寫對了但不生效，能力就是不存在——不能因為「設定看起來對」而升級。
        mcp = self._mcp(**{"chrome-devtools-mcp": pb.ALLOWED_BUT_UNTRUSTED})
        self.assertEqual(pb.compute_level([{"id": "chrome"}], mcp, has_npx=True), 1)

    def test_playwright_only_is_l2(self):
        mcp = self._mcp(**{"@playwright/mcp": pb.ALLOWED})
        self.assertEqual(pb.compute_level([{"id": "chrome"}], mcp, has_npx=True), 2)

    def test_chrome_devtools_reaches_l3(self):
        mcp = self._mcp(**{"chrome-devtools-mcp": pb.ALLOWED})
        self.assertEqual(pb.compute_level([{"id": "chrome"}], mcp, has_npx=True), 3)

    def test_missing_npx_caps_at_l1(self):
        # server 靠 npx 起，沒有 npx 時宣告與放行都不算數。
        mcp = self._mcp(**{"chrome-devtools-mcp": pb.ALLOWED})
        self.assertEqual(pb.compute_level([{"id": "chrome"}], mcp, has_npx=False), 1)


class ProbeTest(unittest.TestCase):
    def _probe(self, files, available={"google-chrome", "npx", "node", "curl"}, env=None):
        return pb.probe(
            ROOT,
            which=fake_which(available),
            read=fake_read(files),
            version=lambda path: "Google Chrome 150.0.7871.128",
            env={} if env is None else env,
        )

    def test_end_to_end_shape(self):
        files = {".mcp.json": MCP_BOTH, "settings.local.json": ALLOW_BOTH}
        result = self._probe(files, env={"DISPLAY": ":0"})
        self.assertEqual(result["level"], 3)
        self.assertTrue(result["can_intercept"])
        self.assertFalse(result["trusted"])
        self.assertEqual(result["browsers"][0]["version"], "Google Chrome 150.0.7871.128")
        self.assertEqual(result["runtime"]["display"], ":0")

    def test_chrome_devtools_alone_cannot_intercept(self):
        files = {".mcp.json": MCP_CDP_ONLY, "settings.json": ALLOW_BOTH, ".claude.json": trust_config()}
        result = self._probe(files)
        self.assertEqual(result["level"], 3)
        self.assertFalse(result["can_intercept"])
        self.assertTrue(result["trusted"])


class RenderTest(unittest.TestCase):
    def _render(self, files, available={"google-chrome", "npx"}):
        result = pb.probe(
            ROOT, which=fake_which(available), read=fake_read(files), version=lambda path: "", env={}
        )
        return pb.render_text(result)

    def test_declared_not_allowed_is_called_out_loudly(self):
        text = self._render({".mcp.json": MCP_BOTH})
        self.assertIn("宣告與放行缺一不可", text)
        self.assertIn("mcp__chrome-devtools", text)

    def test_untrusted_names_both_remedies(self):
        text = self._render({".mcp.json": MCP_BOTH, "settings.json": ALLOW_BOTH})
        self.assertIn("整份被忽略", text)
        self.assertIn("settings.local.json", text)
        self.assertIn("hasTrustDialogAccepted", text)

    def test_intercept_gap_is_called_out(self):
        files = {".mcp.json": MCP_CDP_ONLY, "settings.local.json": ALLOW_BOTH}
        self.assertIn("故障注入", self._render(files))

    def test_no_browser_reports_l0(self):
        text = self._render({}, available={"npx"})
        self.assertIn("L0", text)
        self.assertIn("找不到任何瀏覽器二進位", text)


class VisionFixtureTest(unittest.TestCase):
    def test_is_a_valid_png_of_requested_size(self):
        data = pb.render_vision_fixture(size=64)
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (64, 64))

    def test_is_deterministic(self):
        # 內容固定才能拿來比對——同樣的輸入必須產生同樣的位元組。
        self.assertEqual(pb.render_vision_fixture(32), pb.render_vision_fixture(32))


if __name__ == "__main__":
    unittest.main()
