"""apply_profile 的 fixture 測試；不連真實 Paperclip。"""

import contextlib
import copy
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apply_profile as ap
import probe_providers as pp


#: 真的那一份模板。測試刻意不自己造一份簡化模板——那樣就驗不到「repo 裡這一份
#: 產出的描述合不合格」，而那正是本單的交付物。
TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "switch-execution-issue.md"

FIXED_NOW = "2026-09-08 01:23 +0800"

#: 順序有意義：`targets_for_profile` 依這個順序逐角色套用，前三名對應 fixture 的
#: `id-1`～`id-3`，「第二名回查失敗就停在那裡」那條測試靠它定位。
ORG = {
    "roles": [
        {"id": "developer", "model_tier": "medium", "title": "Developer"},
        {"id": "code-reviewer", "model_tier": "high", "title": "Code Reviewer"},
        {"id": "qa-engineer", "model_tier": "medium", "title": "QA Engineer"},
        {"id": "ceo", "model_tier": "high", "title": "CEO"},
        {"id": "product-manager", "model_tier": "medium", "title": "Product Manager"},
        {"id": "product-analyst", "model_tier": "medium", "title": "Product Analyst"},
        {"id": "tech-lead", "model_tier": "high", "title": "Tech Lead"},
        {"id": "frontend-verifier", "model_tier": "medium", "title": "Frontend Verifier"},
    ]
}
ROLE_IDS = tuple(role["id"] for role in ORG["roles"])
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
    def __init__(self, role="ceo", mismatch_at=None, unknown_adapter=None, me=None,
                 truncate_comment=False, comment_id="comment-new", created_parent=None):
        self.company_id = "company"
        self.me = me or {"name": role, "id": "agent-me", "title": role}
        self.writes = []
        self.posts = []
        self.mismatch_at = mismatch_at
        self.truncate_comment = truncate_comment
        self.comment_id = comment_id
        #: 建出來的單回讀時要不要故意換掉 parentId（驗回讀查證擋得住）。
        self.created_parent = created_parent
        #: ⚠️ 平台實測：`GET …/comments` 是**新到舊**，index 0 才是最新。
        #: fixture 照這個順序放，才驗得到程式沒有拿 `[-1]` 當「最後一則」。
        self.comments = {"MYL-129": [{"id": "comment-old", "body": "上一輪的留言"}]}
        self.issues = {
            "MYL-125": {"id": "parent-uuid", "identifier": "MYL-125", "projectId": "proj-1"},
        }
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
            for index, role_id in enumerate(ROLE_IDS, 1)
        }
        if unknown_adapter:
            self.agents[unknown_adapter]["adapterType"] = "unregistered_adapter"

    def get(self, path):
        if path == "/api/agents/me":
            return copy.deepcopy(self.me)
        if path == "/api/companies/company/agents":
            return [copy.deepcopy(agent) for agent in self.agents.values()]
        if path.startswith("/api/issues/"):
            rest = path[len("/api/issues/"):]
            if "/comments/" in rest:
                ref, comment_id = rest.split("/comments/", 1)
                for comment in self.comments.get(ref, []):
                    if comment["id"] == comment_id:
                        return copy.deepcopy(comment)
                raise ap.ApiError(f"GET {path} → HTTP 404")
            if rest.endswith("/comments"):
                return copy.deepcopy(self.comments.get(rest[: -len("/comments")], []))
            if rest not in self.issues:
                raise ap.ApiError(f"GET {path} → HTTP 404")
            return copy.deepcopy(self.issues[rest])
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

    def post(self, path, body, headers=None):
        self.posts.append((path, copy.deepcopy(body), dict(headers or {})))
        if path.endswith("/comments"):
            ref = path[len("/api/issues/"): -len("/comments")]
            stored = body["body"][:20] if self.truncate_comment else body["body"]
            comment = {"id": self.comment_id, "body": stored}
            self.comments.setdefault(ref, []).insert(0, comment)
            return {"id": self.comment_id} if self.comment_id else {}
        if path == "/api/companies/company/issues":
            created = {
                **copy.deepcopy(body),
                "identifier": "MYL-999",
                "id": "created-uuid",
            }
            if self.created_parent is not None:
                created["parentId"] = self.created_parent
            self.issues["MYL-999"] = created
            return {"identifier": "MYL-999", "id": "created-uuid"}
        raise ap.ApiError(f"POST {path} → 未預期的路徑")


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

    def args(self, *action, profile=None, issue=None, parent=None, create_issue=False):
        return ap.parse_args([
            *action,
            *(["--create-issue"] if create_issue else []),
            *(["--profile", profile] if profile else []),
            *(["--issue", issue] if issue else []),
            *(["--parent", parent] if parent else []),
            "--config", str(self.config_path), "--org-config", str(self.org_path),
            "--template", str(TEMPLATE),
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
                client, "normal", self.config_path, CONFIG["model_routing"]["profiles"],
                ORG, "MYL-129", probe_all=ready_probe,
            )
        self.assertEqual(len(client.writes), 2)
        self.assertNotIn("id-3", [path.rsplit("/", 1)[-1] for path, _ in client.writes])
        self.assertIn("--profile normal --apply --issue MYL-129", output.getvalue())
        self.assertIn("### 回查：code-reviewer", output.getvalue())
        self.assertIn("active: normal", self.config_path.read_text(encoding="utf-8"))
        # 半途失敗不留半份稽核紀錄：報告只在全部套完之後才貼。
        self.assertEqual(client.posts, [])

    def test_non_ceo_fails_before_first_patch(self):
        client = FakeClient(role="developer")
        with self.assertRaisesRegex(ValueError, "configure_agents，全公司只有 CEO 持有"):
            ap.command_apply(
                client, "normal", self.config_path, CONFIG["model_routing"]["profiles"],
                ORG, "MYL-129", probe_all=ready_probe,
            )
        self.assertEqual(client.writes, [])

    def test_unavailable_provider_refuses_apply(self):
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "依 M5 處置"):
            ap.command_apply(
                client, "normal", self.config_path, CONFIG["model_routing"]["profiles"],
                ORG, "MYL-129",
                probe_all=lambda: [{"id": "claude", "status": pp.READY}],
            )
        self.assertEqual(client.writes, [])

    def test_unregistered_current_adapter_stops_before_writes(self):
        client = FakeClient(unknown_adapter="qa-engineer")
        with self.assertRaisesRegex(ValueError, "需人工確認"):
            ap.command_apply(
                client, "normal", self.config_path, CONFIG["model_routing"]["profiles"],
                ORG, "MYL-129", probe_all=ready_probe,
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


class SwitchExecutionIssueTest(unittest.TestCase):
    """C4（MYL-131）：`--create-issue` 路徑與切換執行單模板。"""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.config_path = self.root / "config.yml"
        self.org_path = self.root / "org.yml"
        self.config_path.write_text(ap.yaml.safe_dump(CONFIG, allow_unicode=True), encoding="utf-8")
        self.org_path.write_text(
            ap.yaml.safe_dump(ORG, allow_unicode=True), encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def args(self, *action, profile="emergency", parent="MYL-125", issue=None,
             create_issue=True):
        return ap.parse_args([
            *action,
            *(["--create-issue"] if create_issue else []),
            *(["--profile", profile] if profile else []),
            *(["--issue", issue] if issue else []),
            *(["--parent", parent] if parent else []),
            "--config", str(self.config_path), "--org-config", str(self.org_path),
            "--template", str(TEMPLATE),
        ])

    def payload(self, client=None, profile="emergency"):
        """走一趟真的 `--apply --create-issue`，回組出來的 payload。"""
        client = client or FakeClient()
        with contextlib.redirect_stdout(io.StringIO()):
            ap.run(self.args("--apply", profile=profile), client=client,
                   probe_all=ready_probe, now=FIXED_NOW)
        created = [(path, body) for path, body, _ in client.posts
                   if path == "/api/companies/company/issues"]
        self.assertEqual(len(created), 1, "應該只送出一次建單請求")
        return client, created[0][1]

    # ── AC 7：`--create-issue --dry-run` ────────────────────────────────────
    def test_create_issue_dry_run_prints_title_and_description_with_zero_writes(self):
        client = FakeClient()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = ap.run(self.args("--dry-run"), client=client, probe_all=ready_probe,
                            now=FIXED_NOW)
        self.assertEqual(result, 0)
        # 零寫入：PATCH 與 POST 兩族都要是空的。只斷言 PATCH 會漏掉建單那一筆。
        self.assertEqual(client.writes, [])
        self.assertEqual(client.posts, [])
        printed = output.getvalue()
        self.assertIn("標題：模型 profile 切換：normal → emergency（2026-09-08）", printed)
        for section in ("**Inputs**", "**Outputs**", "**驗收標準**", "**未決事項**"):
            self.assertIn(section, printed)
        self.assertIn("⚠️ `--dry-run` 預演：一筆 PATCH 都還沒送出", printed)
        self.assertIn("Foundry-Source: paperclip/<新單編號>", printed)

    def test_dry_run_warns_when_key_is_not_an_allowed_issue_author(self):
        client = FakeClient(role="developer")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(
                ap.run(self.args("--dry-run"), client=client, probe_all=ready_probe,
                       now=FIXED_NOW),
                0,
            )
        self.assertIn("開單者白名單見 `I1`", output.getvalue())
        self.assertEqual(client.posts, [])

    # ── AC 4：`--parent` 必填，且不自行宣告頂層單 ────────────────────────────
    def test_create_issue_without_parent_fails_pointing_at_i3(self):
        client = FakeClient()
        for action in ("--apply", "--dry-run"):
            with self.subTest(action=action):
                with self.assertRaises(ValueError) as caught:
                    ap.run(self.args(action, parent=None), client=client,
                           probe_all=ready_probe, now=FIXED_NOW)
                message = str(caught.exception)
                self.assertIn("I3", message)
                self.assertIn("--parent", message)
                self.assertEqual(client.writes, [])
                self.assertEqual(client.posts, [])

    def test_no_top_level_declaration_anywhere_in_template_or_rendered_issue(self):
        """`I3` 的例外是可自我特赦的，所以工具與模板都不得替自己寫那一行。"""
        self.assertNotIn("頂層單", TEMPLATE.read_text(encoding="utf-8"))
        _, payload = self.payload()
        self.assertNotIn("頂層單", payload["description"])
        self.assertNotIn("頂層單", payload["title"])

    # ── AC 5：開單者白名單 ─────────────────────────────────────────────────
    def test_issue_author_whitelist_is_exactly_ceo_and_product_manager(self):
        allowed, refused = [], []
        for role in ORG["roles"]:
            for name in (role["id"], role["title"]):
                try:
                    ap.assert_issue_author({"name": name}, ORG)
                except ValueError:
                    refused.append(name)
                else:
                    allowed.append(name)
        self.assertEqual(
            sorted(set(allowed)),
            sorted({"ceo", "CEO", "product-manager", "Product Manager"}),
        )
        # 反例不空轉：被拒的那一族真的有人，而且包含平台 `role` 同為 `pm` 的另兩名。
        self.assertIn("Product Analyst", refused)
        self.assertIn("Developer", refused)

    def test_non_whitelisted_author_refused_before_any_platform_write(self):
        """平台的 `role` 是粗粒度 enum，過得了 `is_ceo` 不等於過得了 `I1`。"""
        client = FakeClient(me={"name": "Product Analyst", "role": "ceo", "id": "agent-pa"})
        with self.assertRaisesRegex(ValueError, "開單者白名單見 `I1`"):
            ap.run(self.args("--apply"), client=client, probe_all=ready_probe, now=FIXED_NOW)
        self.assertEqual(client.writes, [])
        self.assertEqual(client.posts, [])

    def test_refused_author_exits_non_zero_with_message_on_stderr(self):
        client = FakeClient(me={"name": "Product Analyst", "role": "ceo", "id": "agent-pa"})
        errors = io.StringIO()
        with mock.patch.object(ap, "PaperclipClient", return_value=client), \
                contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            code = ap.main([
                "--apply", "--create-issue", "--profile", "emergency", "--parent", "MYL-125",
                "--config", str(self.config_path), "--org-config", str(self.org_path),
                "--template", str(TEMPLATE),
            ])
        self.assertEqual(code, 1)
        self.assertIn("開單者白名單見 `I1`", errors.getvalue())

    # ── AC 6：`I2` 四欄齊備，且上位單不在 blockedByIssueIds ──────────────────
    def test_created_payload_has_all_four_i2_fields_and_parent_is_not_a_blocker(self):
        _, payload = self.payload()
        self.assertEqual(payload["assigneeAgentId"], "agent-me")
        self.assertEqual(payload["parentId"], "parent-uuid")
        upstream = ap_upstream_line(payload["description"])
        self.assertIsNotNone(upstream, "描述缺少 `**上游**：<單號>` 那一行")
        self.assertIn("MYL-125", upstream)
        self.assertRegex(payload["description"], r"(?m)^\*\*驗收標準\*\*$")
        # 反向那一格：填了會做出一張醒不來的單。
        self.assertNotIn(payload["parentId"], payload.get("blockedByIssueIds") or [])

    def test_parent_in_blocked_by_is_rejected(self):
        """反例不空轉：守衛真的擋得住，不是因為程式從不填那一欄才恆綠。"""
        with self.assertRaisesRegex(ValueError, "醒不來的單"):
            ap.assert_parent_not_blocker(
                {"parentId": "parent-uuid", "blockedByIssueIds": ["parent-uuid"]})

    # ── AC 3：四段骨架 ＋ 每條 AC 寫得出怎麼驗 ───────────────────────────────
    def test_description_has_four_section_skeleton_in_order(self):
        _, payload = self.payload()
        description = payload["description"]
        positions = []
        for section in ("Inputs", "Outputs", "驗收標準", "未決事項"):
            matched = re.search(rf"(?m)^\*\*{section}\*\*$", description)
            self.assertIsNotNone(matched, f"缺少 `**{section}**` 那一行")
            positions.append(matched.start())
        self.assertEqual(positions, sorted(positions), "四段順序固定，不得調換")

    def test_every_acceptance_criterion_names_something_checkable(self):
        _, payload = self.payload()
        criteria = acceptance_criteria(payload["description"])
        self.assertEqual(len(criteria), 5)
        for line in criteria:
            with self.subTest(line=line[:40]):
                # 「怎麼驗」的機械代理：每條都要指到一個具體的指令、檔案或欄位。
                self.assertRegex(line, r"`[^`]+`")

    def test_waived_profile_does_not_turn_waiver_into_an_open_question(self):
        _, payload = self.payload(profile="emergency")
        self.assertRegex(payload["description"], r"(?m)^無。（`emergency` 掛有 `M4` waiver")
        _, plain = self.payload(client=FakeClient(), profile="normal")
        self.assertRegex(plain["description"], r"(?m)^無$")

    # ── AC 8：報告內容四件事 ───────────────────────────────────────────────
    def test_report_inside_description_carries_all_four_required_parts(self):
        _, payload = self.payload()
        description = payload["description"]
        self.assertIn("## 逐角色現值 → 目標值", description)
        for role in ROLE_IDS:
            self.assertIn(f"### 回查：{role}", description)
        self.assertIn(
            "回退指令：python3 tools/model-routing/apply_profile.py "
            "--profile normal --apply --create-issue --parent MYL-125",
            description,
        )
        self.assertIn("M4 waiver：`true`", description)
        self.assertIn("測試完成後切回 normal", description)

    def test_created_issue_is_read_back_and_mismatch_is_caught(self):
        client = FakeClient(created_parent="somebody-elses-uuid")
        with contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(ValueError, "回讀 parentId 不符"):
            ap.run(self.args("--apply"), client=client, probe_all=ready_probe, now=FIXED_NOW)

    def test_created_issue_status_is_done_so_nobody_is_woken_for_finished_work(self):
        _, payload = self.payload()
        self.assertEqual(payload["status"], "done")
        self.assertEqual(payload["projectId"], "proj-1")

    # ── AC 1：報告貼回既有工單並回讀查證 ────────────────────────────────────
    def test_apply_with_issue_posts_report_comment_and_reads_it_back(self):
        client = FakeClient()
        output = io.StringIO()
        with mock.patch.dict("os.environ", {"PAPERCLIP_RUN_ID": "run-abc"}), \
                contextlib.redirect_stdout(output):
            ap.run(self.args("--apply", issue="MYL-129", create_issue=False, parent=None),
                   client=client, probe_all=ready_probe, now=FIXED_NOW)
        comments = [(path, body, headers) for path, body, headers in client.posts
                    if path.endswith("/comments")]
        self.assertEqual(len(comments), 1)
        path, body, headers = comments[0]
        self.assertEqual(path, "/api/issues/MYL-129/comments")
        self.assertEqual(headers.get("X-Paperclip-Run-Id"), "run-abc")
        self.assertIn("### 回查：developer", body["body"])
        self.assertIn("回讀未截斷", output.getvalue())

    def test_truncated_comment_read_back_is_reported_not_swallowed(self):
        client = FakeClient(truncate_comment=True)
        with contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(ValueError, "可能被截斷"):
            ap.run(self.args("--apply", issue="MYL-129", create_issue=False, parent=None),
                   client=client, probe_all=ready_probe, now=FIXED_NOW)

    def test_read_back_does_not_trust_the_last_array_element(self):
        """`GET …/comments` 是新到舊：拿 `[-1]` 讀到的是**最舊**那一則。

        POST 不回 id 時走位置退路，這裡把 id 拿掉，逼程式走那一條。fixture 裡先有一則
        舊留言，所以 `[-1]` 會讀到「上一輪的留言」而比對失敗——測試綠代表取的是 `[0]`。
        """
        client = FakeClient(comment_id=None)
        with contextlib.redirect_stdout(io.StringIO()):
            ap.run(self.args("--apply", issue="MYL-129", create_issue=False, parent=None),
                   client=client, probe_all=ready_probe, now=FIXED_NOW)
        self.assertEqual(client.comments["MYL-129"][-1]["body"], "上一輪的留言")

    # ── 模板本身的形狀 ─────────────────────────────────────────────────────
    def test_missing_placeholder_value_is_an_error_not_a_half_filled_issue(self):
        with self.assertRaisesRegex(ValueError, "沒有對應值"):
            ap.render_template("標題 {{profile}} 與 {{nope}}", {"profile": "x"})

    def test_template_without_body_marker_is_rejected(self):
        broken = self.root / "broken.md"
        broken.write_text("---\ntitle: x\n---\n沒有分界標記\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "FOUNDRY:ISSUE-BODY"):
            ap.load_switch_template(broken)

    def test_template_without_title_line_is_rejected(self):
        broken = self.root / "broken.md"
        broken.write_text(f"---\n---\n{ap.ISSUE_BODY_MARKER}\n本文\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "title:"):
            ap.load_switch_template(broken)

    def test_explanatory_preamble_never_reaches_the_issue_description(self):
        _, body = ap.load_switch_template(TEMPLATE)
        self.assertNotIn("這一份不是給人手填的", body)
        self.assertTrue(body.startswith("**Inputs**"))


def ap_upstream_line(description):
    """與 `foundry_lint.UPSTREAM_LINE_RE` 同形：行首粗體「上游」＋冒號＋同一行有單號。"""
    matched = re.search(
        r"(?m)^\s*\*\*上游\*\*[：:][^\n]*[A-Za-z][A-Za-z0-9]*-\d+[^\n]*$", description)
    return matched.group(0) if matched else None


def acceptance_criteria(description):
    """描述裡 `**驗收標準**` 段底下的編號條目。"""
    section = re.split(r"(?m)^\*\*驗收標準\*\*$", description)[1]
    section = re.split(r"(?m)^\*\*未決事項\*\*$", section)[0]
    return re.findall(r"(?m)^\d+\. .*$", section)


if __name__ == "__main__":
    unittest.main()
