#!/usr/bin/env python3
"""`publish-docs` 測試：**以 agent-foundry 自身的 `.foundry/config.yml` 為 fixture**
的那一半（MYL-91）。

原本這兩條在 `test_site_docs.py` 的 `ParseConfigTest` 與 `四碼版本號Test` 裡。它們
斷言的是規則本體那份設定檔真的有 `docs.mirror_site` 那一段——而 `docs` 段依
`config-schema.md` 是**可選的**，目標專案沒開就沒有那一段，兩條必紅。

同一個工單的同一種病，另外兩處：`tools/foundry-lint/test_rule_repo.py`（分檔的理由
寫在那裡）與 `tools/publish-docs/test_publish_gate.py`（整份都是，它要
`docs/handbook/` 與 `scripts/lib/publish-gate.sh`）。

⚠️ **檔名刻意不叫 `test_rule_repo.py`**：`site_docs.py:35` 會把 `tools/foundry-lint`
插到 `sys.path[0]`，於是本目錄一旦 import 過 `site_docs`，同名的測試模組就會解析到
foundry-lint 那一份，`unittest discover` 報
`ImportError: 'test_rule_repo' module incorrectly imported from …`（實撞過）。
辨識「規則本體專屬」靠的是下面那行標記，不是檔名——所以跨目錄取不同名字沒有代價。
"""
# FOUNDRY:RULE-REPO-ONLY —— 本檔以 agent-foundry 自身為 fixture，foundry-init 不複製它

import unittest
from pathlib import Path

import site_docs

REPO_ROOT = Path(__file__).resolve().parents[2]


def real_docs_section():
    text = (REPO_ROOT / ".foundry" / "config.yml").read_text(encoding="utf-8")
    return site_docs.parse_nested_scalars(text, "docs")


class RealConfigDocsSectionTest(unittest.TestCase):
    """`CONFIG_SAMPLE` 那組反例只證明 parser 對，不證明真設定檔長那樣。"""

    #: 與 `test_site_docs.四碼版本號Test.GLOB` 同一個值；那邊釘的是 `V4` 的形狀
    #: 判斷，這邊釘的是「本 repo 真的用它」。
    GLOB = "handbook-v*.*.*.*"

    def test_本_repo_真實設定讀得出精裝站那段(self):
        docs = real_docs_section()
        self.assertIn("mirror_site", docs)
        self.assertIn("tag_pattern", docs["mirror_site"])

    def test_本_repo_真實設定用的就是四碼_glob(self):
        """設定檔漂回 `handbook-v*` 的話，`四碼版本號Test` 那些反例會全部失效
        而沒人發現。"""
        self.assertEqual(real_docs_section()["mirror_site"]["tag_pattern"], self.GLOB)


if __name__ == "__main__":
    unittest.main()
