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

#: ⚠️ 平台端的事實，**刻意不從 `apply_profile` 取**。
#:
#: 這張表就是 AC 15 說的「消費端」。假替身若拿 `ap.effort_key_for()` 當期望值，工具寫
#: 哪個鍵、測試就期望哪個鍵，斷言恆成立——2026-09-07 實測那 12 項有 10 項就是這樣綠的。
#: 兩側各有各的來源，把 `PROVIDERS` 的 `effort_key` 換成假名時這一側不動，測試才會紅
#: （AC 16 的反向突變靠這個成立）。
#:
#: 值的出處是原始碼，不是文件：`claude-local/src/server/execute.ts:332` 讀 `effort`、
#: `:455` 推 `--effort`；`codex-local/src/server/execute.ts` 讀 `modelReasoningEffort`。
CONSUMED_EFFORT_KEY = {
    "claude_local": "effort",
    "codex_local": "modelReasoningEffort",
}

#: 換 adapterType 時平台會保留的鍵（`agents.ts:1900` 的白名單）。**不含 effort 類鍵**
#: ——換型＝整份取代，舊 adapter 的 effort 鍵就此消失，也不會被建立預設值回填。
PRESERVED_ON_TYPE_CHANGE = ("instructionsBundleId",)

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
            # 全 claude：今天平台上真正在跑的形狀（九名全 `claude_local`），也是
            # 「同型改 effort」那條路徑唯一走得到的 profile。
            "claude-only": {"default_provider": "claude", "roles": {}},
        },
    }
}


class FakeClient:
    """平台替身。它模擬的是**平台的行為**，不是工具的行為。

    兩件事必須照真的來，否則測試對本單的缺陷零鑑別力：

    1. **讀到的是實際存下來的東西**，不是工具寫進去的鍵原樣回存。工具寫錯鍵時，
       `consumed_effort()`（走 `CONSUMED_EFFORT_KEY`，與工具各有各的來源）讀到 `None`。
    2. **兩種 PATCH 語意**：換 adapterType ＝整份取代（只留白名單，`agents.ts:1896`／
       `:1900`）；同 adapterType ＝合併（`:1893`）。少了這一半，換型時舊鍵消失這件事
       就驗不到。
    """

    def __init__(self, role="ceo", mismatch_at=None, unknown_adapter=None, me=None,
                 truncate_comment=False, comment_id="comment-new", created_parent=None,
                 masked_config=None):
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
        #: 平台實況：九名全 `claude_local`，effort 落在該 adapter 真正消費的那個鍵上。
        self.agents = {
            role_id: {
                "id": f"id-{index}",
                "name": role_id,
                "adapterType": "claude_local",
                "adapterConfig": {
                    "model": "claude-opus-5",
                    CONSUMED_EFFORT_KEY["claude_local"]: "high",
                },
            }
            for index, role_id in enumerate(ROLE_IDS, 1)
        }
        if unknown_adapter:
            self.agents[unknown_adapter]["adapterType"] = "unregistered_adapter"
        #: 權限遮蔽：平台回 200，但 `adapterConfig` 被清成 `{}`（不是 403）。
        for role_id in masked_config or ():
            self.agents[role_id]["adapterConfig"] = {}

    def _agent_by_id(self, agent_id):
        return next(agent for agent in self.agents.values() if agent["id"] == agent_id)

    def consumed_effort(self, role):
        """平台端**真正被消費**的 effort 值；鍵名從測試自己的對照表取。"""
        agent = self.agents[role]
        key = CONSUMED_EFFORT_KEY.get(agent["adapterType"])
        return agent["adapterConfig"].get(key) if key else None

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
        return copy.deepcopy(self._agent_by_id(path.rsplit("/", 1)[-1]))

    def patch(self, path, body):
        self.writes.append((path, copy.deepcopy(body)))
        agent = self._agent_by_id(path.rsplit("/", 1)[-1])
        incoming = copy.deepcopy(body["adapterConfig"])
        if body["adapterType"] != agent["adapterType"]:
            # 換型：整份取代，只留白名單。舊 adapter 的 effort 鍵就此消失，平台的
            # `applyCreateDefaultsByAdapterType` 對 `claude_local` 沒有 effort 分支、
            # 不會回填——所以寫錯鍵的話，換型之後那一格是空的，不是舊值。
            kept = {key: value for key, value in agent["adapterConfig"].items()
                    if key in PRESERVED_ON_TYPE_CHANGE}
            agent["adapterConfig"] = {**kept, **incoming}
        else:
            # 同型：合併。寫錯鍵時舊值原地滯留，宣告值從未生效——今天唯一會走的路徑。
            agent["adapterConfig"].update(incoming)
        agent["adapterType"] = body["adapterType"]
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
        """AC 5：body 只有兩個允許欄位，effort 的鍵名**由 adapterType 決定**。

        舊版這條把 `modelReasoningEffort` 寫成期望契約，等於把缺陷釘死成規格。現在
        期望值從測試自己的消費端對照表取，而 fixture 的 `normal` 兩種 adapter 都有。
        """
        targets = {target["role"]: target
                   for target in ap.targets_for_profile(
                       CONFIG["model_routing"]["profiles"]["normal"], ORG)}
        # developer 走 codex、code-reviewer 走 claude：一條測試同時涵蓋兩個鍵名。
        self.assertEqual(targets["developer"]["adapterType"], "codex_local")
        self.assertEqual(targets["code-reviewer"]["adapterType"], "claude_local")
        for role, target in ((r, targets[r]) for r in ("developer", "code-reviewer")):
            with self.subTest(role=role):
                body = ap.patch_body(target)
                self.assertEqual(set(body), {"adapterType", "adapterConfig"})
                self.assertEqual(
                    set(body["adapterConfig"]),
                    {"model", CONSUMED_EFFORT_KEY[target["adapterType"]]},
                )
                self.assertFalse(
                    any(key.startswith("instructions") for key in body["adapterConfig"]))
        # `replaceAdapterConfig` 不得出現：既有 config 帶 instructions bundle 鍵時它會
        # 觸發 `assertCanManageInstructionsPath`，那就是 `L4` 的 403。
        self.assertNotIn("replaceAdapterConfig", ap.patch_body(targets["developer"]))

    def test_effort_key_has_exactly_one_source_and_no_literal_second_copy(self):
        """AC 13：取鍵只有一個函式，且全檔沒有第二處字面寫死的 effort 鍵名。"""
        source = Path(ap.__file__).read_text(encoding="utf-8")
        for key in CONSUMED_EFFORT_KEY.values():
            with self.subTest(key=key):
                # 找的是**字串常值**（前後帶引號），不是子字串——`effort` 這四個字必然
                # 出現在 `effort_key_for`／`effort_value` 這些識別字裡，拿子字串比對
                # 這條會恆紅，而恆紅的檢查跟恆綠的一樣沒有用。
                self.assertIsNone(
                    re.search(rf"""(["']){re.escape(key)}\1""", source),
                    f"apply_profile.py 不該出現字面 {key!r}（鍵名一律走 effort_key_for）",
                )
        self.assertEqual(ap.effort_key_for("claude_local"), CONSUMED_EFFORT_KEY["claude_local"])
        self.assertEqual(ap.effort_key_for("codex_local"), CONSUMED_EFFORT_KEY["codex_local"])

    def test_effort_key_refuses_to_guess_for_unverified_adapters(self):
        """AC 7／13：登記表外、或登記了卻沒實證 effort 鍵的 adapter，一律停下不猜。"""
        with self.assertRaisesRegex(ValueError, "不在 probe_providers 登記表"):
            ap.effort_key_for("nonexistent_local")
        # 反例不空轉：登記表裡真的有 effort_key 為 None 的列。
        unverified = [p["adapter_type"] for p in pp.PROVIDERS if not p.get("effort_key")]
        self.assertTrue(unverified, "登記表已無未實證的 adapter，這條反例失去對象")
        with self.assertRaisesRegex(ValueError, "沒有實證"):
            ap.effort_key_for(unverified[0])

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
                CONSUMED_EFFORT_KEY[target["adapterType"]]: target["effort_value"],
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

    # ── AC 2：`--check` 的三態 ─────────────────────────────────────────────
    def test_check_masked_config_is_a_third_state_not_a_wall_of_false_drift(self):
        """讀不到 ≠ 不一致：不渲染差異表，且 exit code 與「不一致」分得開。"""
        client = FakeClient(masked_config=["code-reviewer"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output), \
                self.assertRaises(ap.UnverifiableError) as caught:
            ap.command_check(client, CONFIG, ORG)
        self.assertNotIn("平台實況與 active profile 不一致", output.getvalue())
        message = str(caught.exception)
        # 成因與替代路徑都要寫出來，而且不得指向錯的權限鍵：實測跑在平台上的 build
        # 查的是 `agents:configure`（CEO 持有、讀得到），不是 `agents:create`。
        self.assertIn("agents:configure", message)
        self.assertNotIn("agents:create", message)
        self.assertIn("--dry-run", message)

    def test_three_states_have_three_distinguishable_exit_codes(self):
        """一致 0／不一致 1／無法驗證 3——混成同一個碼，呼叫端就分不出該做什麼。"""
        def exit_code(client):
            """走完整的 `main()`，才驗得到 exit code（不是函式回傳值）。"""
            with mock.patch.object(ap, "PaperclipClient", return_value=client), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                return ap.main(["--check", "--config", str(self.config_path),
                                "--org-config", str(self.org_path)])

        consistent = FakeClient()
        config = copy.deepcopy(CONFIG)
        config["model_routing"]["active"] = "claude-only"
        self.config_path.write_text(ap.yaml.safe_dump(config, allow_unicode=True),
                                    encoding="utf-8")
        for target in ap.targets_for_profile(
                config["model_routing"]["profiles"]["claude-only"], ORG):
            consistent.agents[target["role"]]["adapterConfig"] = {
                "model": target["model"],
                CONSUMED_EFFORT_KEY[target["adapterType"]]: target["effort_value"],
            }
        self.assertEqual(exit_code(consistent), ap.EXIT_OK)

        drifted = FakeClient()
        self.assertEqual(exit_code(drifted), ap.EXIT_DRIFT)

        masked = FakeClient(masked_config=["developer"])
        self.assertEqual(exit_code(masked), ap.EXIT_UNVERIFIABLE)
        self.assertNotEqual(ap.EXIT_DRIFT, ap.EXIT_UNVERIFIABLE)

    def test_check_reports_drift_when_the_effort_key_is_absent_entirely(self):
        """AC 16 ③：該有 effort 卻整個鍵不存在，要報不一致，不得與 `None` 靜默相等。"""
        client = FakeClient()
        config = copy.deepcopy(CONFIG)
        config["model_routing"]["active"] = "claude-only"
        targets = ap.targets_for_profile(config["model_routing"]["profiles"]["claude-only"], ORG)
        for target in targets:
            # 除了 effort 那一格，其餘全部對上——差異表裡只該剩它。
            client.agents[target["role"]]["adapterConfig"] = {"model": target["model"]}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(ap.command_check(client, config, ORG), ap.EXIT_DRIFT)
        printed = output.getvalue()
        effort_row = f"adapterConfig.{CONSUMED_EFFORT_KEY['claude_local']}"
        self.assertIn(effort_row, printed)
        self.assertNotIn("adapterConfig.model", printed)

    def test_check_covers_both_time_points_before_and_after_apply(self):
        """AC 2 尾段：只驗套用後那一格，「紅燈消失但值從沒被套上」會整條溜過去。"""
        client = FakeClient()
        config = copy.deepcopy(CONFIG)
        config["model_routing"]["active"] = "claude-only"
        self.config_path.write_text(ap.yaml.safe_dump(config, allow_unicode=True),
                                    encoding="utf-8")
        profiles = config["model_routing"]["profiles"]

        # 時點一：套用前。九名的 effort 都還是舊值 `high`，而 high 層宣告 `max`。
        before = io.StringIO()
        with contextlib.redirect_stdout(before):
            self.assertEqual(ap.command_check(client, config, ORG), ap.EXIT_DRIFT)
        self.assertIn(f"adapterConfig.{CONSUMED_EFFORT_KEY['claude_local']}", before.getvalue())

        with contextlib.redirect_stdout(io.StringIO()):
            ap.command_apply(client, "claude-only", self.config_path, profiles, ORG,
                             "MYL-129", probe_all=ready_probe)

        # 時點二：套用後。綠了，而且是「真的被套上」才綠——逐角色核對消費端的值。
        after = io.StringIO()
        with contextlib.redirect_stdout(after):
            self.assertEqual(ap.command_check(client, config, ORG), ap.EXIT_OK)
        for target in ap.targets_for_profile(profiles["claude-only"], ORG):
            self.assertEqual(client.consumed_effort(target["role"]), target["effort_value"])

    # ── AC 14：`--apply` 的回查能力預檢 ────────────────────────────────────
    def test_apply_precheck_stops_before_the_first_patch_when_readback_is_impossible(self):
        client = FakeClient(masked_config=["qa-engineer"])
        with contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(ap.UnverifiableError) as caught:
            ap.command_apply(client, "normal", self.config_path,
                             CONFIG["model_routing"]["profiles"], ORG, "MYL-129",
                             probe_all=ready_probe)
        # 沒有預檢的話，第 1 個角色會先被寫進去、回查才必然失敗——停在改到一半的狀態。
        self.assertEqual(client.writes, [])
        self.assertEqual(client.posts, [])
        self.assertIn("一筆 PATCH 都還沒送出", str(caught.exception))

    # ── AC 16：同型／往返兩條路徑的鍵名鑑別力 ──────────────────────────────
    def test_same_adapter_type_apply_actually_moves_the_consumed_effort(self):
        """AC 16 ①：今天唯一會走的路徑。合併語意下寫錯鍵＝舊值原地滯留。"""
        client = FakeClient()
        profiles = CONFIG["model_routing"]["profiles"]
        targets = ap.targets_for_profile(profiles["claude-only"], ORG)
        self.assertTrue(all(t["adapterType"] == "claude_local" for t in targets))
        before = {t["role"]: client.consumed_effort(t["role"]) for t in targets}
        with contextlib.redirect_stdout(io.StringIO()):
            ap.command_apply(client, "claude-only", self.config_path, profiles, ORG,
                             "MYL-129", probe_all=ready_probe)
        moved = [t["role"] for t in targets if before[t["role"]] != t["effort_value"]]
        self.assertTrue(moved, "fixture 起始值與目標值相同，這條測試會空轉")
        for target in targets:
            with self.subTest(role=target["role"]):
                self.assertEqual(client.consumed_effort(target["role"]), target["effort_value"])

    def test_round_trip_claude_codex_claude_leaves_no_stale_key_and_lands_on_target(self):
        """AC 16 ②：換型＝整份取代，舊 adapter 的 effort 鍵整個消失、平台不回填。"""
        client = FakeClient()
        profiles = CONFIG["model_routing"]["profiles"]
        for profile in ("emergency", "claude-only"):
            with contextlib.redirect_stdout(io.StringIO()):
                ap.command_apply(client, profile, self.config_path, profiles, ORG,
                                 "MYL-129", probe_all=ready_probe)
        for target in ap.targets_for_profile(profiles["claude-only"], ORG):
            with self.subTest(role=target["role"]):
                agent = client.agents[target["role"]]
                self.assertEqual(agent["adapterType"], "claude_local")
                self.assertEqual(client.consumed_effort(target["role"]), target["effort_value"])
                # 途經 codex 留下的那個鍵不該還在——它若還在，代表取代語意沒被模擬到，
                # 於是「寫錯鍵時往返之後那一格是空的」這件事就驗不出來。
                self.assertNotIn(CONSUMED_EFFORT_KEY["codex_local"], agent["adapterConfig"])

    def test_reverse_mutation_a_bogus_effort_key_is_caught_by_the_suite(self):
        """AC 16 的自證：登記表的 effort 鍵全域換成平台不消費的假名時，套件必須紅。

        ⚠️ 擋得住它的**不是工具**，而且原理上不可能是工具：組 body 與回查都走同一個
        `effort_key_for()`，兩側一起被突變，工具回查照樣相符、照樣 exit 0。唯一擋得住
        的是測試自己那張消費端對照表——這正是 AC 15 要求替身有「消費端」概念的理由。

        所以本條做兩件事：證明工具在突變下**沉默地成功**（把盲點寫在明處），並證明
        上面那族 `consumed_effort()` 斷言在突變下會失敗（套件因此紅）。
        """
        mutated = tuple(
            {**provider, "effort_key": "bogusEffortKey"} if provider.get("effort_key")
            else provider
            for provider in pp.PROVIDERS
        )
        client = FakeClient()
        profiles = CONFIG["model_routing"]["profiles"]
        with mock.patch.object(pp, "PROVIDERS", mutated), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                ap.command_apply(client, "claude-only", self.config_path, profiles, ORG,
                                 "MYL-129", probe_all=ready_probe),
                0,
                "工具本身偵測得到鍵名突變的話，這條測試的前提要重寫",
            )
        stale = [target["role"] for target in ap.targets_for_profile(profiles["claude-only"], ORG)
                 if client.consumed_effort(target["role"]) != target["effort_value"]]
        self.assertTrue(
            stale,
            "突變之後消費端的值仍與宣告相符 ⇒ 那一族斷言對鍵名沒有鑑別力，AC 16 不成立",
        )

    def test_writing_a_key_the_adapter_does_not_consume_is_caught_by_the_readback(self):
        """AC 4：只突變**寫入端**（回查端不動）時，回查就抓得住——保護力不是零。

        與上一條互補：兩側一起錯，工具無感（那是測試的職責）；只有一側錯，回查必須停下。
        """
        original_patch_body = ap.patch_body

        def body_with_a_key_nobody_reads(target):
            body = original_patch_body(target)
            key = ap.effort_key_for(target["adapterType"])
            body["adapterConfig"]["x-" + key] = body["adapterConfig"].pop(key)
            return body

        client = FakeClient()
        with mock.patch.object(ap, "patch_body", body_with_a_key_nobody_reads), \
                contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(ValueError, "回查不符"):
            ap.command_apply(client, "claude-only", self.config_path,
                             CONFIG["model_routing"]["profiles"], ORG, "MYL-129",
                             probe_all=ready_probe)
        # 停在第一個「宣告值與滯留舊值不同」的角色，不會把八個角色全套完。
        self.assertLess(len(client.writes), len(ROLE_IDS))

    # ── AC 17：`update_active_config` 的 no-op ────────────────────────────
    def test_applying_the_already_active_profile_is_idempotent_not_an_error(self):
        client = FakeClient()
        profiles = CONFIG["model_routing"]["profiles"]
        for attempt in (1, 2):
            with self.subTest(attempt=attempt), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    ap.command_apply(client, "claude-only", self.config_path, profiles, ORG,
                                     "MYL-129", probe_all=ready_probe),
                    0,
                )
        self.assertIn("active: claude-only", self.config_path.read_text(encoding="utf-8"))

    def test_update_active_config_still_refuses_a_config_without_the_active_line(self):
        """反例不空轉：改判「有沒有配到」之後，真的漏了 `active:` 那行仍然擋得住。"""
        broken = self.root / "no-active.yml"
        broken.write_text("model_routing:\n  profiles:\n    normal: {}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "找不到 model_routing.active"):
            ap.update_active_config(broken, "normal")

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
