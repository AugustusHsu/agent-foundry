#!/usr/bin/env python3
"""盤點本機的瀏覽器操控能力，判定 L0～L3（MYL-37）。

為什麼要有這支腳本：`foundry-browser` 的第一步是「這個 harness 到底能不能開瀏覽器」。
這件事**大部分可以機械判定**（瀏覽器二進位在不在、MCP server 有沒有被宣告、
有沒有被權限規則放行），不該由 agent 憑印象回答——MYL-37 調查期就出過兩次誤判：

1. 「裝了 MCP server 就等於能用」——**錯**。實測 `.mcp.json` 宣告了工具、工具也載入了，
   但 `permission-mode default` 時**每一次呼叫都被擋**。要能用得同時滿足三件事：
   **宣告**（`.mcp.json`）＋**放行**（settings `permissions.allow`）＋**信任**（見下）。
   只有一半時明確回報 `declared_not_allowed`，而不是含糊地說「有裝」。
2. 「`dangerouslySkipPermissions` 開著就不用管權限」——**錯**，同上，實測無效。
3. 「放行規則寫進版控的 `.claude/settings.json` 就會生效」——**未必**。工作區未被信任時
   （`~/.claude.json` 的 `projects[<路徑>].hasTrustDialogAccepted` 非 true），
   該檔的 `permissions.allow` **整份被忽略**，只有機器本地的 `.claude/settings.local.json` 算數。
   這是實測撞到的：同一份設定，靠 `settings.json` 全被擋，改放 `settings.local.json` 就全通。
   本腳本因此把「規則寫了但因未信任而無效」獨立成 `allowed_but_untrusted`——
   那正是最會騙人的狀態：設定檔看起來完全正確。

判定只用不需要網路、不需要真的開瀏覽器的訊號：二進位是否在 `PATH`、設定檔內容。
**跑得動不代表跑得對**：本腳本不驗證瀏覽器真的能渲染，那要靠 `--vision-fixture`
產生的圖檔由 agent 實際讀一次（見 `foundry-browser` §2.1）。

用法::

    python3 tools/browser-probe/probe_browser.py                    # markdown 表
    python3 tools/browser-probe/probe_browser.py --format json
    python3 tools/browser-probe/probe_browser.py --min-level 2      # 低於 L2 則 exit 1
    python3 tools/browser-probe/probe_browser.py --vision-fixture /tmp/v.png

⚠️ 本檔的 `L0`～`L3` 是**瀏覽器能力等級**，與 `docs/standards/known-drift.md` 的
`L1`～`L6`（平台限制）**不同命名空間**，兩者不可互相引用。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

# ── 瀏覽器二進位登記表（依序取第一個找得到的） ──────────────────────────────
#
# 只收 Chromium 家族與 Firefox：這兩族都支援「無頭 ＋ 截圖」的命令列用法，
# 而 L1 的定義就是這個。新增一個瀏覽器：在此加一列即可。
BROWSERS = (
    {"id": "chrome", "name": "Google Chrome", "cli": "google-chrome"},
    {"id": "chrome-stable", "name": "Google Chrome (stable)", "cli": "google-chrome-stable"},
    {"id": "chromium", "name": "Chromium", "cli": "chromium"},
    {"id": "chromium-browser", "name": "Chromium", "cli": "chromium-browser"},
    {"id": "edge", "name": "Microsoft Edge", "cli": "microsoft-edge"},
    {"id": "firefox", "name": "Firefox", "cli": "firefox"},
)

# ── 瀏覽器 MCP server 登記表 ────────────────────────────────────────────────
#
# `package` 用來從 `.mcp.json` 的 command/args 裡認出這是哪一支 server。
# `deep` 標記該 server 是否提供 L3 的深度診斷（Lighthouse／效能 trace）。
# `intercept` 標記能否**在測試進行中**按 URL 攔截單一端點——MYL-37 的主場景需要它。
MCP_PACKAGES = (
    {
        "package": "chrome-devtools-mcp",
        "name": "chrome-devtools-mcp",
        "deep": True,
        "intercept": False,
        "note": "Lighthouse／效能 trace 獨有；按 URL 攔截只有啟動旗標 --blockedUrlPattern（靜態，測試中改不了）",
    },
    {
        "package": "@playwright/mcp",
        "name": "@playwright/mcp",
        "deep": False,
        "intercept": True,
        "note": "page.route() 可在測試中動態攔截／解除；跨瀏覽器與裝置模擬獨有",
    },
    {
        "package": "@modelcontextprotocol/server-puppeteer",
        "name": "puppeteer MCP",
        "deep": False,
        "intercept": False,
        "note": "舊版通用 puppeteer server，只有基本互動",
    },
)

# MCP server 狀態
ALLOWED = "allowed"
ALLOWED_BUT_UNTRUSTED = "allowed_but_untrusted"
DECLARED_NOT_ALLOWED = "declared_not_allowed"
NOT_DECLARED = "not_declared"

MCP_STATUS_LABEL = {
    ALLOWED: "✅ 已宣告且已放行",
    ALLOWED_BUT_UNTRUSTED: "❌ 規則只在 settings.json，但工作區未信任（整份被忽略）",
    DECLARED_NOT_ALLOWED: "❌ 已宣告但未放行（呼叫會被擋）",
    NOT_DECLARED: "— 未宣告",
}

LEVEL_LABEL = {
    0: "L0 只有 HTTP（curl／urllib），拿不到 JS 渲染後的畫面",
    1: "L1 可渲染＋截圖，但不能互動（點擊／填表）",
    2: "L2 可互動：導航、點擊、填表、讀 console／network",
    3: "L3 可深度診斷：Lighthouse、效能 trace",
}

#: 版控走的放行規則——**要工作區被信任才生效**。
PROJECT_SETTINGS = ".claude/settings.json"
#: 機器本地的放行規則——不受信任閘門限制，但被全域 gitignore 排除、不跟著版控走。
LOCAL_SETTINGS = ".claude/settings.local.json"
#: 信任狀態的權威來源（使用者層設定，不在 repo 內）。
CLAUDE_CONFIG = "~/.claude.json"


def _default_which(cmd: str):
    return shutil.which(cmd)


def _default_read(path: Path):
    """讀檔；不存在或壞掉都回 None——設定檔缺席是常態，不是錯誤。"""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _default_version(cli_path: str) -> str:
    """取版本字串；取不到就回空字串——版本只是佐證，不影響可用判定。"""
    try:
        out = subprocess.run([cli_path, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    text = (out.stdout or "") + (out.stderr or "")
    return text.strip().splitlines()[0] if text.strip() else ""


def probe_browsers(which=_default_which, version=_default_version) -> list:
    """回傳所有找得到的瀏覽器二進位。找不到就回空 list（＝L1 不成立）。"""
    found = []
    for browser in BROWSERS:
        path = which(browser["cli"])
        if not path:
            continue
        found.append(
            {
                "id": browser["id"],
                "name": browser["name"],
                "cli": browser["cli"],
                "path": path,
                "version": version(path),
            }
        )
    return found


def _iter_server_words(server: dict):
    """把一筆 mcpServers 設定攤平成字串序列，用來比對套件名。"""
    yield str(server.get("command", ""))
    for arg in server.get("args") or []:
        yield str(arg)
    for value in (server.get("env") or {}).values():
        yield str(value)


def parse_mcp_declarations(mcp_text) -> dict:
    """從 `.mcp.json` 內容解析出「套件 → 宣告名稱」。

    比對用 `in` 而不是完全相等，因為實際寫的是 `chrome-devtools-mcp@1.8.0` 這種帶版號的形式。
    """
    if not mcp_text:
        return {}
    try:
        data = json.loads(mcp_text)
    except (ValueError, TypeError):
        # 壞掉的 .mcp.json 等同沒有宣告：harness 也載入不了，據實反映。
        return {}
    declared = {}
    for name, server in (data.get("mcpServers") or {}).items():
        if not isinstance(server, dict):
            continue
        words = " ".join(_iter_server_words(server))
        for pkg in MCP_PACKAGES:
            if pkg["package"] in words:
                declared[pkg["package"]] = name
    return declared


def parse_allow_rules(settings_texts) -> list:
    """把數份 settings 的 `permissions.allow` 併成一張清單。"""
    rules = []
    for text in settings_texts:
        if not text:
            continue
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            continue
        for rule in (data.get("permissions") or {}).get("allow") or []:
            rules.append(str(rule))
    return rules


def is_allowed(server_name: str, allow_rules) -> bool:
    """允許規則是否涵蓋這個 MCP server。

    Claude Code 的 MCP 規則形狀是 `mcp__<server>` 或 `mcp__<server>__<tool>`；
    整台放行的 `mcp__<server>` 也涵蓋其下所有工具，所以用前綴比對。
    """
    prefix = f"mcp__{server_name}"
    return any(rule == prefix or rule.startswith(prefix + "__") for rule in allow_rules)


def is_workspace_trusted(root: Path, read=_default_read) -> bool:
    """工作區在 `~/.claude.json` 裡是否被標記為已信任。

    未信任時 `.claude/settings.json` 的 `permissions.allow` **整份被忽略**——
    這是設計如此（不讓 clone 來的 repo 自己給自己開權限），不是 bug。
    Paperclip materialize 出來的 workspace 從沒被互動式開啟過，預設就是未信任。
    """
    text = read(Path(os.path.expanduser(CLAUDE_CONFIG)))
    if not text:
        return False
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return False
    entry = (data.get("projects") or {}).get(str(root)) or {}
    return bool(entry.get("hasTrustDialogAccepted"))


def probe_mcp(root: Path, read=_default_read) -> list:
    """判定每一支已登記的瀏覽器 MCP server 目前是「宣告了沒／放行了沒／算不算數」。"""
    declared = parse_mcp_declarations(read(root / ".mcp.json"))
    project_rules = parse_allow_rules([read(root / PROJECT_SETTINGS)])
    local_rules = parse_allow_rules([read(root / LOCAL_SETTINGS)])
    trusted = is_workspace_trusted(root, read=read)
    # 生效的規則＝本地那份，加上（信任時才算數的）版控那份。
    effective = local_rules + (project_rules if trusted else [])

    results = []
    for pkg in MCP_PACKAGES:
        server_name = declared.get(pkg["package"])
        if not server_name:
            status = NOT_DECLARED
        elif is_allowed(server_name, effective):
            status = ALLOWED
        elif is_allowed(server_name, project_rules):
            # 規則寫對了，只是因為工作區未信任而被整份忽略——最會騙人的狀態。
            status = ALLOWED_BUT_UNTRUSTED
        else:
            status = DECLARED_NOT_ALLOWED
        results.append(
            {
                "package": pkg["package"],
                "name": pkg["name"],
                "server_name": server_name,
                "status": status,
                "deep": pkg["deep"],
                "intercept": pkg["intercept"],
                "note": pkg["note"],
            }
        )
    return results


def compute_level(browsers, mcp_results, has_npx: bool) -> int:
    """由訊號推出能力等級。每一級都是前一級的超集，缺一級就停在下面。"""
    if not browsers:
        return 0
    usable = [m for m in mcp_results if m["status"] == ALLOWED]
    if not usable or not has_npx:
        return 1
    return 3 if any(m["deep"] for m in usable) else 2


def probe(root: Path, which=_default_which, read=_default_read, version=_default_version, env=None) -> dict:
    env = os.environ if env is None else env
    browsers = probe_browsers(which=which, version=version)
    mcp_results = probe_mcp(root, read=read)
    has_npx = bool(which("npx"))
    usable = [m for m in mcp_results if m["status"] == ALLOWED]
    return {
        "root": str(root),
        "level": compute_level(browsers, mcp_results, has_npx),
        "trusted": is_workspace_trusted(root, read=read),
        "browsers": browsers,
        "mcp": mcp_results,
        "runtime": {
            "curl": which("curl"),
            "node": which("node"),
            "npx": which("npx"),
            "display": env.get("DISPLAY") or "",
            "xvfb": which("Xvfb"),
        },
        "can_intercept": any(m["intercept"] for m in usable),
    }


# ── 視覺 fixture ───────────────────────────────────────────────────────────
#
# 「adapter 看不看得懂圖」無法從機器狀態推斷——它是模型能力不是機器能力。
# 所以這裡只負責產出一張**內容已知**的圖，由 agent 實際讀一次再自我比對。
# 純標準庫寫 PNG（zlib＋struct），不引入 Pillow 這種額外相依。

VISION_FIXTURE_EXPECTED = (
    "四個象限：左上紅、右上藍、左下黃、右下綠；"
    "另有一條由左上到右下的黑色對角線。"
)


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def render_vision_fixture(size: int = 240) -> bytes:
    """產生四象限＋黑色對角線的 PNG bytes（內容固定，可重複比對）。"""
    half = size // 2
    quadrants = ((255, 0, 0), (0, 0, 255), (255, 255, 0), (0, 160, 0))  # 左上 右上 左下 右下
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # PNG 每列的 filter type
        for x in range(size):
            if abs(x - y) <= max(1, size // 120):
                raw.extend((0, 0, 0))
                continue
            raw.extend(quadrants[(0 if y < half else 2) + (0 if x < half else 1)])
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _png_chunk(b"IEND", b"")
    )


# ── 輸出 ───────────────────────────────────────────────────────────────────


def render_text(result: dict) -> str:
    """輸出 markdown——終端可讀，且可直接貼進工單留言當盤點證據。"""
    lines = ["| MCP server | 狀態 | 宣告名稱 | 深度診斷 | 測試中攔截 |", "| --- | --- | --- | --- | --- |"]
    for m in result["mcp"]:
        lines.append(
            "| `{pkg}` | {status} | {server} | {deep} | {intercept} |".format(
                pkg=m["package"],
                status=MCP_STATUS_LABEL[m["status"]],
                server=f"`{m['server_name']}`" if m["server_name"] else "—",
                deep="✅" if m["deep"] else "—",
                intercept="✅" if m["intercept"] else "—",
            )
        )

    lines.append("")
    lines.append("| 瀏覽器 | 路徑 | 版本 |")
    lines.append("| --- | --- | --- |")
    if result["browsers"]:
        for b in result["browsers"]:
            lines.append(f"| {b['name']} | `{b['path']}` | {b['version'] or '—'} |")
    else:
        lines.append("| — 找不到任何瀏覽器二進位 | — | — |")

    runtime = result["runtime"]
    lines.append("")
    lines.append(
        "執行環境：node `{node}`／npx `{npx}`／curl `{curl}`／DISPLAY `{display}`／Xvfb `{xvfb}`".format(
            node=runtime["node"] or "無",
            npx=runtime["npx"] or "無",
            curl=runtime["curl"] or "無",
            display=runtime["display"] or "無",
            xvfb=runtime["xvfb"] or "無",
        )
    )
    lines.append(f"工作區信任狀態：{'✅ 已信任' if result['trusted'] else '❌ 未信任'}")
    lines.append("")
    lines.append(f"**能力等級：{LEVEL_LABEL[result['level']]}**")

    for m in result["mcp"]:
        if m["status"] == DECLARED_NOT_ALLOWED:
            lines.append(
                f"⚠️ `{m['package']}` 已在 `.mcp.json` 宣告為 `{m['server_name']}`，"
                f"但 settings 的 `permissions.allow` 沒有 `mcp__{m['server_name']}`——"
                "工具會載入卻每次呼叫都被擋。宣告與放行缺一不可。"
            )
        elif m["status"] == ALLOWED_BUT_UNTRUSTED:
            lines.append(
                f"⚠️ `{m['package']}` 的放行規則寫在 `{PROJECT_SETTINGS}`，但本工作區未被信任，"
                f"**該檔的 `permissions.allow` 整份被忽略**。兩條出路："
                f"把規則複製一份到 `{LOCAL_SETTINGS}`（立即生效、不跟版控），"
                f"或把 `{CLAUDE_CONFIG}` 的 `projects[\"{result['root']}\"].hasTrustDialogAccepted` 設為 true。"
            )
    if result["level"] >= 2 and not result["can_intercept"]:
        lines.append(
            "⚠️ 目前可用的 server 都無法在測試進行中按 URL 攔截單一端點"
            "（只有全站 Offline 或啟動時就固定的黑名單）。"
            "需要故障注入的驗證要改掛 `@playwright/mcp`，見 `foundry-browser` §4。"
        )
    lines.append("")
    lines.append(
        "視覺能力無法由本腳本判定（那是模型能力不是機器能力）："
        "跑 `--vision-fixture <路徑>` 產圖後實際讀一次再比對。"
    )
    return "\n".join(lines)


def render_json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="盤點本機瀏覽器操控能力並判定 L0～L3（foundry-browser 步驟 1）",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        metavar="DIR",
        help="要檢查 .mcp.json 與 .claude/settings*.json 的目錄，預設為現行目錄",
    )
    parser.add_argument(
        "--min-level",
        type=int,
        default=None,
        metavar="N",
        help="能力等級低於 N 時 exit 1（把『這台機器夠不夠』變成可機械檢查）",
    )
    parser.add_argument(
        "--vision-fixture",
        type=Path,
        default=None,
        metavar="PATH",
        help="產生一張內容已知的測試圖，供 agent 實際讀取以驗證視覺能力",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.vision_fixture:
        args.vision_fixture.parent.mkdir(parents=True, exist_ok=True)
        args.vision_fixture.write_bytes(render_vision_fixture())
        print(f"已產生視覺測試圖：{args.vision_fixture}")
        print(f"預期內容：{VISION_FIXTURE_EXPECTED}")
        print("讀這張圖並自我比對；描述不符或讀不到圖，就是沒有視覺能力。")
        return 0

    result = probe(args.root)
    print(render_json(result) if args.format == "json" else render_text(result))
    if args.min_level is not None and result["level"] < args.min_level:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
