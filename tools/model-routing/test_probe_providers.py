"""probe_providers 單元測試（MYL-36 P10）。

判定邏輯全部以注入的假 which／exists 驅動，不碰真實檔案系統與 PATH——
測試結果因此不會隨「這台機器剛好裝了什麼」而變動。
"""

import contextlib
import io
import json
import unittest

import probe_providers as pp


def fake_env(installed=(), creds=()):
    """回傳 (which, exists, version) 三個假依賴。"""
    installed, creds = set(installed), set(creds)
    return (
        lambda cmd: f"/usr/bin/{cmd}" if cmd in installed else None,
        lambda path: path in creds,
        lambda cli_path: "fake 1.0.0",
    )


def probe(provider, installed=(), creds=()):
    which, exists, version = fake_env(installed, creds)
    return pp.probe_provider(provider, which=which, exists=exists, version=version)


P_WITH_CRED = {
    "id": "demo",
    "name": "Demo",
    "cli": "demo",
    "cred_paths": ("~/.demo/auth.json",),
    "cred_source": "實測",
    "adapter_type": "demo_local",
}
P_NO_CRED_PATH = dict(P_WITH_CRED, id="nocred", cli="nocred", cred_paths=(), cred_source="未知")


class ProbeProviderTest(unittest.TestCase):
    def test_cli_absent_is_absent(self):
        self.assertEqual(probe(P_WITH_CRED)["status"], pp.ABSENT)

    def test_cli_absent_does_not_check_credentials(self):
        """CLI 沒裝就不該查憑證——對沒裝的工具回報「未登入」是假訊號。"""
        checked = []

        def exists(path):
            checked.append(path)
            return True

        pp.probe_provider(
            P_WITH_CRED,
            which=lambda cmd: None,
            exists=exists,
            version=lambda p: "",
        )
        self.assertEqual(checked, [])

    def test_cli_and_credential_present_is_ready(self):
        r = probe(P_WITH_CRED, installed=["demo"], creds=["~/.demo/auth.json"])
        self.assertEqual(r["status"], pp.READY)
        self.assertEqual(r["cred_path"], "~/.demo/auth.json")
        self.assertEqual(r["version"], "fake 1.0.0")

    def test_cli_present_without_credential_is_no_auth(self):
        r = probe(P_WITH_CRED, installed=["demo"])
        self.assertEqual(r["status"], pp.NO_AUTH)
        self.assertIsNone(r["cred_path"])

    def test_cli_present_without_known_credential_path_is_unknown(self):
        """沒有已知憑證路徑時回報「不明」，不得猜成未登入。"""
        r = probe(P_NO_CRED_PATH, installed=["nocred"])
        self.assertEqual(r["status"], pp.UNKNOWN_AUTH)

    def test_version_failure_does_not_change_status(self):
        r = pp.probe_provider(
            P_WITH_CRED,
            which=lambda cmd: "/usr/bin/demo",
            exists=lambda path: True,
            version=lambda p: "",
        )
        self.assertEqual(r["status"], pp.READY)
        self.assertEqual(r["version"], "")


class ReadyIdsTest(unittest.TestCase):
    def test_only_ready_counts_as_available(self):
        results = [
            {"id": "a", "status": pp.READY},
            {"id": "b", "status": pp.NO_AUTH},
            {"id": "c", "status": pp.UNKNOWN_AUTH},
            {"id": "d", "status": pp.ABSENT},
        ]
        self.assertEqual(pp.ready_ids(results), ["a"])


class RenderTest(unittest.TestCase):
    def _results(self, statuses):
        return [
            {
                "id": f"p{i}",
                "name": f"P{i}",
                "cli": f"p{i}",
                "adapter_type": f"p{i}_local",
                "cred_source": "實測",
                "cli_path": None,
                "version": "",
                "cred_path": None,
                "status": s,
            }
            for i, s in enumerate(statuses)
        ]

    def test_single_provider_notes_m4_not_applicable(self):
        text = pp.render_text(self._results([pp.READY, pp.ABSENT]))
        self.assertIn("`M4`", text)
        self.assertIn("可用供應商：1 家", text)

    def test_two_providers_drops_the_m4_note(self):
        """變異測試：M4 附註必須隨條件消失，否則它只是無意義的常駐文字。"""
        text = pp.render_text(self._results([pp.READY, pp.READY]))
        self.assertNotIn("`M4`", text)
        self.assertIn("可用供應商：2 家", text)

    def test_json_round_trips_and_matches_ready(self):
        results = self._results([pp.READY, pp.NO_AUTH])
        data = json.loads(pp.render_json(results))
        self.assertEqual(data["ready"], ["p0"])
        self.assertEqual(len(data["providers"]), 2)


class RegistryTest(unittest.TestCase):
    """登記表本身的健全性——加一家新供應商時這幾條會擋住漏填。"""

    def test_ids_and_clis_are_unique(self):
        ids = [p["id"] for p in pp.PROVIDERS]
        clis = [p["cli"] for p in pp.PROVIDERS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(clis), len(set(clis)))

    def test_required_fields_present(self):
        for p in pp.PROVIDERS:
            for field in ("id", "name", "cli", "cred_paths", "cred_source", "adapter_type"):
                self.assertIn(field, p, f"{p.get('id')} 缺欄位 {field}")
            self.assertIn(p["cred_source"], ("實測", "推定", "未知"), p["id"])

    def test_unknown_cred_source_has_no_paths_and_vice_versa(self):
        """`未知` 表示查不到路徑；有路徑卻標未知（或反之）代表登記表自相矛盾。"""
        for p in pp.PROVIDERS:
            self.assertEqual(
                p["cred_source"] == "未知",
                not p["cred_paths"],
                f"{p['id']} 的 cred_source 與 cred_paths 不一致",
            )

    def test_every_status_has_a_label(self):
        for status in (pp.READY, pp.NO_AUTH, pp.UNKNOWN_AUTH, pp.ABSENT):
            self.assertIn(status, pp.STATUS_LABEL)


class MinReadyTest(unittest.TestCase):
    def test_min_ready_gate(self):
        """--min-ready 把「至少 N 家可用」變成可機械檢查的前提。"""
        original = pp.probe_all
        try:
            pp.probe_all = lambda *a, **k: [
                {"id": "only", "status": pp.READY},
                {"id": "gone", "status": pp.ABSENT},
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pp.main(["--format", "json", "--min-ready", "1"]), 0)
                self.assertEqual(pp.main(["--format", "json", "--min-ready", "2"]), 1)
                self.assertEqual(pp.main(["--format", "json"]), 0)
        finally:
            pp.probe_all = original


if __name__ == "__main__":
    unittest.main()
