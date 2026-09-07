"""apply_profile 的 fixture 測試；不連真實 Paperclip。"""

import contextlib
import copy
import io
import tempfile
import unittest
from pathlib import Path

import apply_profile as ap
import probe_providers as pp


ORG = {
    "roles": [
        {"id": "developer", "model_tier": "medium"},
        {"id": "code-reviewer", "model_tier": "high"},
        {"id": "qa-engineer", "model_tier": "medium"},
    ]
}
CONFIG = {
    "model_routing": {
        "active": "normal",
        "profiles": {
            "normal": {
                "default_provider": "claude",
                "roles": {"developer": "codex"},
            },
            "emergency": {
                "default_provider": "codex",
                "roles": {},
                "emergency": True,
                "waives_m4": True,
                "waiver_reason": "測試完成後切回 normal",
            },
        },
    }
}


class FakeClient:
    def __init__(self, role="ceo", mismatch_at=None, unknown_adapter=None):
        self.company_id = "company"
        self.me = {"name": role}
        self.writes = []
        self.mismatch_at = mismatch_at
        self.agents = {
            role_id: {
                "id": f"id-{index}",
                "name": role_id,
                "adapterType": "claude_local",
                "adapterConfig": {
                    "model": "claude-opus-5",
                    "modelReasoningEffort": "high",
                },
            }
            for index, role_id in enumerate(("developer", "code-reviewer", "qa-engineer"), 1)
        }
        if unknown_adapter:
            self.agents[unknown_adapter]["adapterType"] = "unregistered_adapter"

    def get(self, path):
        if path == "/api/agents/me":
            return copy.deepcopy(self.me)
        if path == "/api/companies/company/agents":
            return [copy.deepcopy(agent) for agent in self.agents.values()]
        agent_id = path.rsplit("/", 1)[-1]
        agent = next(agent for agent in self.agents.values() if agent["id"] == agent_id)
        return copy.deepcopy(agent)

    def patch(self, path, body):
        self.writes.append((path, copy.deepcopy(body)))
        agent_id = path.rsplit("/", 1)[-1]
        agent = next(agent for agent in self.agents.values() if agent["id"] == agent_id)
        agent["adapterType"] = body["adapterType"]
        agent["adapterConfig"].update(body["adapterConfig"])
        if len(self.writes) == self.mismatch_at:
            agent["adapterConfig"]["model"] = "wrong-model"


def ready_probe():
    return [
        {**provider, "status": pp.READY, "version": "fake", "cred_path": "fake"}
        for provider in pp.PROVIDERS
        if provider["id"] in {"claude", "codex"}
    ]


class ApplyProfileTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.config_path = self.root / "config.yml"
        self.org_path = self.root / "org.yml"
        self.config_path.write_text(ap.yaml.safe_dump(CONFIG, allow_unicode=True), encoding="utf-8")
        self.org_path.write_text(ap.yaml.safe_dump(ORG, allow_unicode=True), encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def args(self, *action, profile=None, issue=None):
        return ap.parse_args([
            *action,
            *( ["--profile", profile] if profile else [] ),
            *( ["--issue", issue] if issue else [] ),
            "--config", str(self.config_path), "--org-config", str(self.org_path),
        ])

    def mock_load(self):
        return contextlib.ExitStack()

    def test_list_includes_active_and_waiver(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(ap.command_list(CONFIG), 0)
        self.assertIn("目前 active：normal", output.getvalue())
        self.assertIn("waives_m4: true", output.getvalue())
        self.assertIn("測試完成後切回 normal", output.getvalue())

    def test_dry_run_never_writes(self):
        client = FakeClient()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = ap.command_dry_run(client, "normal", CONFIG["model_routing"]["profiles"], ORG)
        self.assertEqual(result, 0)
        self.assertEqual(client.writes, [])
        self.assertIn("PATCH agent developer", output.getvalue())

    def test_patch_body_is_limited_and_has_no_instructions_key(self):
        target = ap.targets_for_profile(CONFIG["model_routing"]["profiles"]["normal"], ORG)[0]
        body = ap.patch_body(target)
        self.assertEqual(set(body), {"adapterType", "adapterConfig"})
        self.assertEqual(set(body["adapterConfig"]), {"model", "modelReasoningEffort"})
        self.assertFalse(any(key.startswith("instructions") for key in body["adapterConfig"]))

    def test_second_verification_failure_stops_before_third_patch(self):
        client = FakeClient(mismatch_at=2)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaisesRegex(ValueError, "回查不符"):
            ap.command_apply(
                client, "normal", self.config_path, CONFIG["model_routing"]["profiles"], ORG,
                "MYL-129", probe_all=ready_probe,
            )
        self.assertEqual(len(client.writes), 2)
        self.assertNotIn("id-3", [path.rsplit("/", 1)[-1] for path, _ in client.writes])
        self.assertIn("--profile normal --apply --issue MYL-129", output.getvalue())
        self.assertIn("### 回查：code-reviewer", output.getvalue())
        self.assertIn("active: normal", self.config_path.read_text(encoding="utf-8"))

    def test_non_ceo_fails_before_first_patch(self):
        client = FakeClient(role="developer")
        with self.assertRaisesRegex(ValueError, "configure_agents，全公司只有 CEO 持有"):
            ap.command_apply(
                client, "normal", self.config_path, CONFIG["model_routing"]["profiles"], ORG,
                "MYL-129", probe_all=ready_probe,
            )
        self.assertEqual(client.writes, [])

    def test_unavailable_provider_refuses_apply(self):
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "依 M5 處置"):
            ap.command_apply(
                client, "normal", self.config_path, CONFIG["model_routing"]["profiles"], ORG,
                "MYL-129", probe_all=lambda: [{"id": "claude", "status": pp.READY}],
            )
        self.assertEqual(client.writes, [])

    def test_unregistered_current_adapter_stops_before_writes(self):
        client = FakeClient(unknown_adapter="qa-engineer")
        with self.assertRaisesRegex(ValueError, "需人工確認"):
            ap.command_apply(
                client, "normal", self.config_path, CONFIG["model_routing"]["profiles"], ORG,
                "MYL-129", probe_all=ready_probe,
            )
        self.assertEqual(client.writes, [])

    def test_check_reports_each_mismatched_cell(self):
        client = FakeClient()
        client.agents["developer"]["adapterType"] = "claude_local"
        client.agents["developer"]["adapterConfig"]["model"] = "wrong"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = ap.command_check(client, CONFIG, ORG)
        self.assertEqual(result, 1)
        self.assertIn("developer", output.getvalue())
        self.assertIn("adapterType", output.getvalue())
        self.assertIn("adapterConfig.model", output.getvalue())

    def test_check_lists_active_profile_waiver_even_when_consistent(self):
        client = FakeClient()
        for target in ap.targets_for_profile(CONFIG["model_routing"]["profiles"]["emergency"], ORG):
            agent = client.agents[target["role"]]
            agent["adapterType"] = target["adapterType"]
            agent["adapterConfig"] = {
                "model": target["model"],
                "modelReasoningEffort": target["modelReasoningEffort"],
            }
        emergency_config = copy.deepcopy(CONFIG)
        emergency_config["model_routing"]["active"] = "emergency"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(ap.command_check(client, emergency_config, ORG), 0)
        self.assertIn("M4 waiver：`true`", output.getvalue())
        self.assertIn("測試完成後切回 normal", output.getvalue())

    def test_check_lists_active_profile_waiver_when_mismatched(self):
        client = FakeClient()
        emergency_config = copy.deepcopy(CONFIG)
        emergency_config["model_routing"]["active"] = "emergency"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(ap.command_check(client, emergency_config, ORG), 1)
        self.assertIn("M4 waiver：`true`", output.getvalue())
        self.assertIn("平台實況與 active profile 不一致", output.getvalue())

    def test_check_refuses_permission_masked_adapter_config_without_false_drift(self):
        client = FakeClient()
        client.agents["code-reviewer"]["adapterConfig"] = {}
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaisesRegex(ValueError, "權限遮蔽"):
            ap.command_check(client, CONFIG, ORG)
        self.assertNotIn("平台實況與 active profile 不一致", output.getvalue())

    def test_public_apply_interface_requires_issue_and_emits_full_markdown_report(self):
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "--issue"):
            ap.run(self.args("--apply", profile="emergency"), client=client, probe_all=ready_probe)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = ap.run(
                self.args("--apply", profile="emergency", issue="MYL-129"),
                client=client,
                probe_all=ready_probe,
            )
        self.assertEqual(result, 0)
        report = output.getvalue()
        self.assertIn("# 模型 profile 套用執行報告", report)
        self.assertIn("## 供應商盤點（原始輸出）", report)
        self.assertIn("active：`normal` → `emergency`", report)
        self.assertIn("## 逐角色現值 → 目標值", report)
        self.assertIn("### 回查：developer", report)
        self.assertIn("M6 第 1 級", report)
        self.assertIn("--profile normal --apply --issue MYL-129", report)


if __name__ == "__main__":
    unittest.main()
