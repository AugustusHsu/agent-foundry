#!/usr/bin/env python3
"""盤點本機可用的模型供應商 CLI（MYL-36 P10）。

為什麼要有這支腳本：`foundry-model-routing` 的第一步是「現在到底有哪幾家可用」。
這件事**可以機械判定**（CLI 在不在 PATH、憑證檔在不在），不該由 agent 憑印象回答——
MYL-36 分析階段就把「adapterType 欄位可寫」誤當成「該 CLI 可用」，兩者無關。

判定只用兩個訊號，都不需要網路、不需要跑 CLI 登入：

1. CLI 是否在 `PATH` 上。
2. 該 CLI 的憑證檔是否存在。

憑證路徑分「實測」與「推定」兩種來源（見 ``PROVIDERS`` 的 ``cred_source``）。
只有本機真的裝了並登入過的那幾家是實測；其餘是依各 CLI 慣例推定，
**沒有實測過的路徑不會被當成失敗證據**——CLI 不在時根本不查憑證，
CLI 在但沒有已知憑證路徑時回報 `unknown_auth`（無法自動判定），而不是猜一個「未登入」。

用法：

    python3 tools/model-routing/probe_providers.py              # markdown 表
    python3 tools/model-routing/probe_providers.py --format json
    python3 tools/model-routing/probe_providers.py --min-ready 2  # 少於 2 家可用則 exit 1
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ── 供應商登記表 ────────────────────────────────────────────────────────────
#
# `adapter_type` 是 Paperclip `PATCH /api/agents/{id}` 的 adapterType 值
# （MYL-36 自 openapi.json 讀出）。其他執行層平台沒有這個欄位，見 skill §4。
#
# 新增一家供應商：在此加一列即可，其餘程式碼不動。
PROVIDERS = (
    {
        "id": "claude",
        "name": "Claude Code",
        "cli": "claude",
        "cred_paths": ("~/.claude/.credentials.json",),
        "cred_source": "實測",
        "adapter_type": "claude_local",
    },
    {
        "id": "codex",
        "name": "Codex CLI",
        "cli": "codex",
        "cred_paths": ("~/.codex/auth.json",),
        "cred_source": "實測",
        "adapter_type": "codex_local",
    },
    {
        "id": "gemini",
        "name": "Gemini CLI",
        "cli": "gemini",
        "cred_paths": ("~/.gemini/oauth_creds.json",),
        "cred_source": "推定",
        "adapter_type": "gemini_local",
    },
    {
        "id": "cursor",
        "name": "Cursor Agent",
        "cli": "cursor-agent",
        "cred_paths": ("~/.cursor/cli-config.json",),
        "cred_source": "推定",
        "adapter_type": "cursor_cloud",
    },
    {
        "id": "opencode",
        "name": "OpenCode",
        "cli": "opencode",
        "cred_paths": ("~/.local/share/opencode/auth.json",),
        "cred_source": "推定",
        "adapter_type": "opencode_local",
    },
    {
        "id": "grok",
        "name": "Grok CLI",
        "cli": "grok",
        "cred_paths": (),
        "cred_source": "未知",
        "adapter_type": "grok_local",
    },
    {
        "id": "kimi",
        "name": "Kimi CLI",
        "cli": "kimi",
        "cred_paths": (),
        "cred_source": "未知",
        "adapter_type": "kimi_local",
    },
)

# 狀態值：可用 / 已安裝未登入 / 已安裝但登入狀態不明 / 未安裝
READY = "ready"
NO_AUTH = "no_auth"
UNKNOWN_AUTH = "unknown_auth"
ABSENT = "absent"

STATUS_LABEL = {
    READY: "✅ 可用",
    NO_AUTH: "⚠️ 已安裝、未登入",
    UNKNOWN_AUTH: "❓ 已安裝、登入狀態不明",
    ABSENT: "— 未安裝",
}


def _default_which(cmd: str):
    return shutil.which(cmd)


def _default_exists(path: str) -> bool:
    return Path(os.path.expanduser(path)).exists()


def _default_version(cli_path: str) -> str:
    """取版本字串；取不到就回空字串——版本只是佐證，不影響可用判定。"""
    try:
        out = subprocess.run(
            [cli_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (out.stdout or out.stderr or "").strip().splitlines()[0] if (out.stdout or out.stderr).strip() else ""


def probe_provider(provider: dict, which=_default_which, exists=_default_exists, version=_default_version) -> dict:
    """判定單一供應商的狀態。純函式（依賴以參數注入），供測試替換。"""
    result = {
        "id": provider["id"],
        "name": provider["name"],
        "cli": provider["cli"],
        "adapter_type": provider["adapter_type"],
        "cred_source": provider["cred_source"],
        "cli_path": None,
        "version": "",
        "cred_path": None,
    }

    cli_path = which(provider["cli"])
    if not cli_path:
        # CLI 不在就不查憑證：對沒裝的工具談「未登入」只會製造假訊號。
        result["status"] = ABSENT
        return result

    result["cli_path"] = cli_path
    result["version"] = version(cli_path)

    found = next((p for p in provider["cred_paths"] if exists(p)), None)
    if found:
        result["status"] = READY
        result["cred_path"] = found
    elif provider["cred_paths"]:
        result["status"] = NO_AUTH
    else:
        # 沒有已知憑證路徑可查，不代表沒登入——據實回報不明，別猜。
        result["status"] = UNKNOWN_AUTH
    return result


def probe_all(providers=PROVIDERS, **kwargs) -> list:
    return [probe_provider(p, **kwargs) for p in providers]


def ready_ids(results) -> list:
    return [r["id"] for r in results if r["status"] == READY]


def render_text(results) -> str:
    """輸出 markdown 表——終端可讀，且可直接貼進工單留言當盤點證據。"""
    lines = [
        "| 供應商 | 狀態 | CLI | 版本 | adapterType | 憑證路徑來源 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append(
            "| {name} | {status} | `{cli}` | {version} | `{adapter}` | {src} |".format(
                name=r["name"],
                status=STATUS_LABEL[r["status"]],
                cli=r["cli"],
                version=r["version"] or "—",
                adapter=r["adapter_type"],
                src=r["cred_source"],
            )
        )
    ids = ready_ids(results)
    lines.append("")
    lines.append(f"可用供應商：{len(ids)} 家" + (f"（{'、'.join(ids)}）" if ids else ""))
    if len(ids) < 2:
        lines.append(
            "註：可用供應商少於 2 家時，protocol `M4`（實作與審查異廠）不適用——"
            "不是違規，是條件未成立。"
        )
    return "\n".join(lines)


def render_json(results) -> str:
    return json.dumps(
        {"providers": results, "ready": ready_ids(results)},
        ensure_ascii=False,
        indent=2,
    )


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="盤點本機可用的模型供應商 CLI（foundry-model-routing 步驟 1）",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--min-ready",
        type=int,
        default=0,
        metavar="N",
        help="可用供應商少於 N 家時 exit 1（用於把 M4 的前提條件變成可機械檢查）",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    results = probe_all()
    print(render_json(results) if args.format == "json" else render_text(results))
    return 1 if len(ready_ids(results)) < args.min_ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
