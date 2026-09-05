#!/usr/bin/env python3
"""publish_docs 的 **mkdocs 精裝面**：`docs/handbook/` → 版本化的 GitHub Pages 站。

MYL-55。本模組是 `publish_docs`（`skills/foundry-platform/SKILL.md` §3.9）在
`mirror_site` 目標面的內容轉換那一半；建站、`mike` 版本化與 push 歸
`scripts/publish-site.sh` 與 `.github/workflows/publish-handbook-site.yml`。

與 wiki 面（`project_docs.py`）的差別只有一個，但它決定了本模組有多短：
**精裝面的渲染器與來源手冊是同一個**（Python-Markdown／mkdocs），所以
`project_docs` 的四條轉換規則裡，前三條（頁名、去 `.md`、錨點換算）在這裡
**全部不需要**——照抄就是對的。剩下的只有第四條：

> 指向 repo 內部路徑（`skills/`、`templates/`、`docs/pilot/`）的相對連結，
> 在只含手冊九章的站台上一定失效，依 `docs.link_policy` 改寫或拆為純文字。

⚠️ **不要好心把 `project_docs.rewrite_links` 拿來共用**：那支會把章間連結的 `.md`
去掉、把錨點換成 GitHub slug，兩件事在 mkdocs 面都是**把對的改成錯的**。
共用的是更下層的東西（`repo_path_of`、`MD_LINK_RE`、圍欄判斷），那些才是真正共通的。

另一件本模組刻意做的事：**站台的 `mkdocs.yml` 由私有 `mkdocs.yml` 轉寫**，
不另寫一份。known-drift「兩份 nav 的結構性漂移」記的就是舊 `publish-handbook.sh`
內嵌那份 heredoc；本模組把它收掉。轉寫的範圍不只 nav——theme、
`markdown_extensions` 一律沿用私有那份，否則本機預覽與公開站會用不同的
渲染設定，而那正是錨點會無聲對不上的來源。
"""

import argparse
import fnmatch
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "foundry-lint"))

from foundry_lint import FENCE_RE, extract_all_headings, read_text  # noqa: E402
from project_docs import (  # noqa: E402
    EXTERNAL_RE,
    INDEX_SOURCE,
    MD_LINK_RE,
    read_nav,
    repo_path_of,
)

DEFAULT_SITE_URL = "https://augustushsu.github.io/agent-foundry/"
DEFAULT_REPO_BLOB_URL = "https://github.com/AugustusHsu/agent-foundry/blob/main"

#: 注入到站台首頁的來源提示。內容固定，投影才有確定性（§3.9 行為 3）。
SITE_NOTE = (
    '!!! note "本站是機械投影"\n'
    "    本站由內部規則層 repo `agent-foundry` 的 `docs/handbook/` 產生，"
    "推 `handbook-v<a>.<b>.<c>.<d>` tag 時由 CI 建置並以 `mike` 版本化發佈。"
    "唯一可寫的真相是那個目錄，**在本站看到的任何內容都不要回頭改站台**。"
    "文中指向 `skills/`、`templates/`、`docs/pilot/` 的連結會帶你回 repo。\n"
)


# ── `.foundry/config.yml` 的 docs 段 ───────────────────────────────────────
# 刻意不用 PyYAML：foundry-lint 與本目錄的工具一律只吃標準函式庫，這樣機械閘門
# 在任何環境都跑得起來（CI 的 lint job 不裝任何東西就是靠這條）。要讀的東西也
# 只有巢狀純量映射這一種形狀，寫個受限的解析器比拖一個相依進來便宜。


def parse_nested_scalars(text: str, top_key: str) -> dict:
    """讀出 `top_key:` 底下的巢狀純量映射，回傳巢狀 dict。

    支援的形狀就是 `.foundry/config.yml` 實際用到的那些：縮排巢狀、純量值、
    `#` 註解、單／雙引號。**不支援清單與多行字串**——本段 schema 裡沒有，
    真的出現時寧可讓它讀不到而不是猜（讀錯設定會靜默發錯東西）。
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(f"{top_key}:"):
            start = i
            break
    if start is None:
        return {}

    root: dict = {}
    # stack 是 (縮排深度, 該層的 dict)。頂層那段的內容縮排一定 > 0。
    stack = [(-1, root)]
    for line in lines[start + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            break  # 回到頂層＝這一段結束
        body = line.strip()
        if ":" not in body:
            continue
        key, _, raw = body.partition(":")
        key = key.strip()
        value = _strip_comment(raw.strip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = value
    return root


def _strip_comment(raw: str) -> str:
    """去掉行末註解與外層引號。引號內的 `#` 要留著。"""
    if raw[:1] in ("'", '"'):
        quote = raw[0]
        end = raw.find(quote, 1)
        if end > 0:
            return raw[1:end]
    cut = raw.find(" #")
    if cut >= 0:
        raw = raw[:cut]
    return raw.strip().strip("'\"")


def _truthy(value) -> bool:
    return str(value).strip().lower() in ("true", "yes", "on", "1")


class ConfigError(Exception):
    """設定本身不合法——與「設定說不要發佈」是兩回事，不可混為一談。"""


def mirror_site_decision(docs_cfg: dict, tag: str) -> tuple:
    """依 `docs` 段與 tag 名判斷「這次要不要發佈精裝站」。

    回傳 `(要發佈?, 版本字串, 理由)`。**這支是 AC2 的本體**：
    `docs.mirror_site.enabled: false` 之後再打 tag 必須走到 `False`。

    為什麼判斷不能只交給 workflow 的 `on: push: tags:`：那份過濾器是寫死在
    YAML 裡的靜態字串，改 `tag_pattern` 不會讓它跟著變。`on:` 是**粗篩**，
    設定檔才是權威——兩者不一致時以本函式為準，這樣「關掉開關」才真的關得掉。
    """
    site = docs_cfg.get("mirror_site")
    if not docs_cfg:
        return False, "", "`.foundry/config.yml` 沒有 `docs` 段＝本專案不做文檔投影"
    if not isinstance(site, dict):
        return False, "", "`docs.mirror_site` 整段缺席＝不建精裝站"
    if not _truthy(site.get("enabled", "")):
        return False, "", (
            f"`docs.mirror_site.enabled` 是 `{site.get('enabled', '（缺）')}`，不是 true"
            "——設定保留但精裝站已關閉"
        )

    trigger = str(site.get("trigger", "")).strip()
    if trigger != "tag":
        return False, "", (
            f"`docs.mirror_site.trigger` 是 `{trigger or '（缺）'}`，不是 `tag`"
            "——本次 tag 推送不觸發發佈"
        )

    pattern = str(site.get("tag_pattern", "")).strip()
    if not pattern:
        raise ConfigError(
            "`docs.mirror_site.trigger: tag` 但沒有 `tag_pattern`——缺必填欄位，"
            "設定不合法（見 skills/foundry-platform/config-schema.md）"
        )
    if not fnmatch.fnmatchcase(tag, pattern):
        return False, "", f"tag `{tag}` 不符合 `tag_pattern`（`{pattern}`）"

    return True, version_of(tag, pattern), f"tag `{tag}` 符合 `{pattern}`，開關為 true"


def version_of(tag: str, pattern: str) -> str:
    """由 tag 與 pattern 算出站台版本名：`handbook-v*` ＋ `handbook-v0.0.0.1` → `v0.0.0.1`。

    規則：取 pattern 第一個萬用字元之前的**字面前綴**，再截到它最後一個 `-`（含）
    為止，剝掉那一段。`handbook-v*` 的字面前綴是 `handbook-v`，截到最後一個 `-`
    是 `handbook-`，於是 `handbook-v0.0.0.1` → `v0.0.0.1`——版本選擇器上顯示的是
    `v0.0.0.1` 而不是光禿禿的 `0.0.0.1`。前綴裡沒有 `-` 就整段剝掉。
    改 `tag_pattern` 不必回來改這裡（四碼版本號的形狀見 protocol `V4`，
    本函式刻意是泛用的前綴剝除，不綁死位數）。
    前綴對不上（理論上 `fnmatch` 已經擋掉）時原樣回傳 tag。
    """
    cut = min((i for i in (pattern.find(c) for c in "*?[") if i >= 0), default=-1)
    literal = pattern[:cut] if cut >= 0 else pattern
    dash = literal.rfind("-")
    prefix = literal[: dash + 1] if dash >= 0 else literal
    return tag[len(prefix):] if prefix and tag.startswith(prefix) else tag


# ── 已發佈的版本不重打（MYL-63，對應 SuperOD `T5`）─────────────────────────
# `mike deploy` 對同名版本是**直接覆蓋** gh-pages 上那個目錄，不問也不警告。
# 已經發出去、可能已被引用的那一版就這樣靜靜換了內容——`V3` 擋的是這件事。


def published_versions(versions_json: str) -> list:
    """讀 `mike` 寫在 gh-pages 根目錄的 `versions.json`，回傳已發佈的版本清單。

    形狀是 `[{"version": "v0.0.0.1", "title": "v0.0.0.1", "aliases": ["latest"]}, …]`。
    **只取 `version`，不取 `aliases`**——別名（`latest`）每次發佈都會被重新指向，
    那是設計如此；把別名算成「已發佈版本」會讓第二版起全部被自己擋下。

    空字串＝gh-pages 上還沒有這個檔（第一次發佈），回空清單。
    **解析不出來就 raise**：讀不懂等於不知道有沒有撞版本，此時要擋下而不是放行——
    放行的代價是覆蓋掉一版已發佈的手冊，那是不可逆的。
    """
    if not versions_json.strip():
        return []
    try:
        data = json.loads(versions_json)
    except ValueError as exc:
        raise ConfigError(
            f"versions.json 解析失敗（{exc}）——判斷不了版本是否已發佈，拒絕部署"
        ) from exc
    if not isinstance(data, list):
        raise ConfigError("versions.json 不是 JSON 陣列，與 mike 的輸出形狀不符，拒絕部署")

    out = []
    for item in data:
        name = str(item.get("version", "")).strip() if isinstance(item, dict) \
            else str(item).strip()  # mike 也吃純字串陣列的舊格式
        if name:
            out.append(name)
    return out


def republish_decision(version: str, published: list, rebuild: bool) -> tuple:
    """同一個版本號要不要放行再部署一次。回傳 `(放行?, 理由)`。

    判準是**「這個版本號的內容有沒有變」**，不是「跑過幾次 `mike deploy`」。
    兩條觸發路徑因此處置相反：

    - **tag push**：git 拒絕把已存在的 tag 再推一次（除非 `-f` 或先刪再推），
      所以這個事件對一個已發佈的版本再次觸發，本身就意味著 tag 被移動或重打。
      版本已存在在這條路上是**違規的充分證據** → 擋下，要求 bump 下一版。
    - **`workflow_dispatch` 重建**（`rebuild=True`）：有人手動輸入既有 tag 重建站台
      （Pages 設定改過、CI 修好、建置環境換版）。tag 沒動＝同一顆 commit＝同樣的位元組；
      版本已存在在這條路上是**預期狀態** → 放行。擋死它等於封掉唯一的重建手段。

    ⚠️ 這個放行有一道**刻意留著的缺口**：本函式驗不了「tag 是否仍指向原本那顆
    commit」。先移動 tag 再用 dispatch 重建，覆蓋仍會發生。要擋得住得把來源 sha
    記在 gh-pages 上，而 `mike` 的 `versions.json` 不帶那個欄位。根治手段是 tag
    ruleset（需要使用者權限），不是這裡再多一層——見 protocol `V3` 的「違反」段。
    """
    if version not in published:
        return True, f"版本 `{version}` 尚未發佈過（gh-pages 現有：{'、'.join(published) or '無'}）"
    if rebuild:
        return True, (
            f"版本 `{version}` 已發佈，但這次是 workflow_dispatch 重建路徑"
            "——同一顆 commit 重建同樣的內容，不算重打"
        )
    return False, (
        f"版本 `{version}` 已經發佈在 gh-pages 上，而這次是 tag 推送。"
        "已發佈的手冊版本不重打（protocol `V3`）：tag 能對同一版再次觸發，"
        "代表它被移動或刪除重打了。要修就 bump 下一版：版本號是四碼 "
        "handbook-v<a>.<b>.<c>.<d>，依 protocol `V4` 的進位歸零規則決定這次動哪一位"
        "（動 a 則 b/c/d 歸零，動 b 則 c/d 歸零，動 c 則 d 歸零，動 d 只加 d）。"
        "不要覆蓋已經有人引用得到的那一版。"
    )


# ── 內容投影 ──────────────────────────────────────────────────────────────


def rewrite_repo_links(text: str, link_policy: str, repo_blob_url: str) -> str:
    """只改一件事：指向 repo 內部、手冊外的相對連結。

    章間連結與錨點**原樣保留**——目標面的渲染器就是來源假設的那一個。
    """
    def convert(m):
        label, target = m.group(1), m.group(2)
        if EXTERNAL_RE.match(target) or target.startswith("#"):
            return m.group(0)
        page_part, sep, anchor = target.partition("#")
        repo_path = repo_path_of(page_part)
        if repo_path.startswith("docs/handbook/"):
            return m.group(0)  # 手冊內部，平移之後相對路徑照樣成立
        if link_policy == "plain":
            return label
        return f"[{label}]({repo_blob_url.rstrip('/')}/{repo_path}{sep}{anchor})"

    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        out.append(line if in_fence else MD_LINK_RE.sub(convert, line))
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def inject_site_note(text: str) -> str:
    """在首頁大標之後插入來源提示。已經有就不重複插（冪等）。"""
    if "本站是機械投影" in text:
        return text
    lines = text.split("\n")
    lines.insert(1, "\n" + SITE_NOTE)
    return "\n".join(lines)


# ── 站台 mkdocs.yml：由私有那份轉寫 ────────────────────────────────────────


def split_top_level(text: str) -> list:
    """把 YAML 依**頂層鍵**切塊，回傳 `[(鍵或 None, 原始行串), …]`。

    只認「行首第一欄就是 `key:`」這一種邊界，其餘整段原封不動搬走。
    這樣 theme／markdown_extensions／plugins 不必被理解就能沿用，
    而需要換掉的那幾塊（`site_url`、`nav`、`extra`）可以精準置換。
    """
    blocks, key, buf = [], None, []
    for line in text.splitlines():
        stripped = line.rstrip("\n")
        if stripped and not stripped[0].isspace() and not stripped.startswith("#") \
                and ":" in stripped:
            blocks.append((key, buf))
            key, buf = stripped.split(":", 1)[0].strip(), [stripped]
        else:
            buf.append(stripped)
    blocks.append((key, buf))
    return [b for b in blocks if b[0] is not None or any(x.strip() for x in b[1])]


def _rstrip_blank(lines: list) -> list:
    end = len(lines)
    while end and not lines[end - 1].strip():
        end -= 1
    return lines[:end]


def build_site_mkdocs_yaml(private_text: str, nav: list, site_url: str) -> str:
    """私有 `mkdocs.yml` → 站台 `mkdocs.yml`。四處置換，其餘沿用。"""
    nav_lines = ["nav:"]
    for title, source_name in nav:
        nav_lines.append(f"  - {title}: {source_name}")

    extra_lines = [
        "extra:",
        "  version:",
        "    # mkdocs-material 的版本選擇器：資料來自 mike 寫在 gh-pages 根目錄的",
        "    # versions.json。少了這段，站台建得出來但沒有版本下拉選單。",
        "    provider: mike",
    ]

    replacements = {
        "site_url": [f"site_url: {site_url}"],
        "nav": nav_lines,
        "extra": extra_lines,
        # 站台是機械投影，指到 repo 的「編輯本頁」會鼓勵讀者改錯地方。
        "edit_uri": ['edit_uri: ""'],
        # 連結解不開就讓建置紅，不要靜靜產出一個有死連結的公開站。
        # 只開在站台這一份：本機預覽的 docs_dir 含 standards/、features/ 等
        # 不在 nav 裡的目錄，開 strict 會被那些警告卡住而不是被真的問題卡住。
        "strict": ["strict: true"],
    }

    out, seen = [], set()
    for key, lines in split_top_level(private_text):
        if key in replacements:
            # 保留原區塊尾端的空行，置換之後版面才跟私有那份一樣——
            # 產出的 YAML 要人看得懂，日後有人 diff 兩份才不會被排版噪音淹掉。
            trailing = len(lines) - len(_rstrip_blank(lines))
            out.extend(replacements[key] + [""] * trailing)
            seen.add(key)
        else:
            out.extend(lines)
    for key in ("site_url", "edit_uri", "strict", "nav", "extra"):
        if key not in seen:
            out.append("")
            out.extend(replacements[key])
    return "\n".join(out).rstrip("\n") + "\n"


def build(src_dir: Path, mkdocs_yml: Path, out_dir: Path, link_policy: str,
          site_url: str, repo_blob_url: str) -> dict:
    """產出完整的站台工作區（`<out>/mkdocs.yml` ＋ `<out>/docs/*.md`）。"""
    nav = read_nav(mkdocs_yml)
    if not nav:
        raise ConfigError(f"{mkdocs_yml} 讀不到手冊 nav——站台會沒有目錄，拒絕建置")

    docs_out = out_dir / "docs"
    if docs_out.exists():
        shutil.rmtree(docs_out)
    docs_out.mkdir(parents=True)

    pages = {}
    for path in sorted(src_dir.glob("*.md")):
        body = rewrite_repo_links(read_text(path), link_policy, repo_blob_url)
        if path.name == INDEX_SOURCE:
            body = inject_site_note(body)
        pages[path.name] = body
        (docs_out / path.name).write_text(body, encoding="utf-8")

    (out_dir / "mkdocs.yml").write_text(
        build_site_mkdocs_yaml(read_text(mkdocs_yml), nav, site_url), encoding="utf-8"
    )
    return pages


def verify(src_dir: Path, out_dir: Path, nav: list) -> list:
    """§3.9 行為 4「逐章比對」：章節數、大標文字、nav 涵蓋率。

    回傳失敗訊息清單（空＝全綠）。連結是否真的解得開交給 `mkdocs build --strict`
    ——那支是真的走過渲染器的，比在這裡再實作一次連結解析可靠。
    """
    problems = []
    src = {p.name: read_text(p) for p in sorted(src_dir.glob("*.md"))}
    dst_dir = out_dir / "docs"
    dst = {p.name: read_text(p) for p in sorted(dst_dir.glob("*.md"))}

    for missing in sorted(set(src) - set(dst)):
        problems.append(f"投影後少了 {missing}——缺一章就是紅燈")
    for extra in sorted(set(dst) - set(src)):
        problems.append(f"投影後多出 {extra}——來源沒有這一章")

    for name in sorted(set(src) & set(dst)):
        s_titles = extract_all_headings(src[name])
        d_titles = extract_all_headings(dst[name])
        if s_titles != d_titles:
            problems.append(f"{name}：標題文字與來源不一致（來源 {len(s_titles)} 個，投影 {len(d_titles)} 個）")

    for _, source_name in nav:
        if source_name not in dst:
            problems.append(f"nav 指向 {source_name}，但投影裡沒有這一頁")
    return problems


# ── CLI ───────────────────────────────────────────────────────────────────


def _load_docs_cfg(config: Path) -> dict:
    if not config.exists():
        raise ConfigError(f"{config} 不存在")
    return parse_nested_scalars(read_text(config), "docs")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="publish_docs 的 mkdocs 精裝面投影引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decide", help="依 .foundry/config.yml 判斷這個 tag 要不要發佈")
    d.add_argument("--config", default=".foundry/config.yml")
    d.add_argument("--tag", required=True)

    # 離開碼刻意與 decide 分開：0＝放行、3＝撞到已發佈版本、2＝設定／輸入不合法。
    # 3 這個值對齊來源專案 SuperOD 的 `release-archive`（同名目錄直接 exit 3）。
    c = sub.add_parser(
        "check-version",
        help="比對 gh-pages 的 versions.json：這個版本是不是已經發佈過（`V3`）")
    c.add_argument("--version", required=True)
    c.add_argument(
        "--versions-json", required=True,
        help="gh-pages 根目錄那份 versions.json 的本機路徑；該分支還不存在時，"
             "呼叫端要自己寫一個內容為 [] 的檔案")
    c.add_argument(
        "--rebuild", action="store_true",
        help="這次是 workflow_dispatch 重建路徑——同版本放行（見 republish_decision）")

    b = sub.add_parser("build", help="產出站台工作區")
    b.add_argument("--src", default="docs/handbook")
    b.add_argument("--mkdocs", default="mkdocs.yml")
    b.add_argument("--config", default=".foundry/config.yml")
    b.add_argument("--out", required=True)
    b.add_argument("--site-url", default=DEFAULT_SITE_URL)
    b.add_argument("--repo-blob-url", default=DEFAULT_REPO_BLOB_URL)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "check-version":
            versions_file = Path(args.versions_json)
            if not versions_file.exists():
                # 路徑打錯時若當成「沒有已發佈版本」，這道閘門就退化成恆真——
                # 一個永遠放行的閘門比沒有閘門更糟，因為它看起來還在。
                raise ConfigError(
                    f"{versions_file} 不存在。取不到 gh-pages 的 versions.json 就"
                    "判斷不了版本是否已發佈；gh-pages 還沒建出來時請明確寫入 `[]`"
                )
            ok, reason = republish_decision(
                args.version, published_versions(read_text(versions_file)), args.rebuild)
            print(f"{'✅' if ok else '❌'} {reason}", file=sys.stdout if ok else sys.stderr)
            return 0 if ok else 3

        docs_cfg = _load_docs_cfg(Path(args.config))
        if args.cmd == "decide":
            publish, version, reason = mirror_site_decision(docs_cfg, args.tag)
            # GitHub Actions 直接把 stdout 導進 $GITHUB_OUTPUT，所以形狀是 key=value。
            print(f"publish={'true' if publish else 'false'}")
            print(f"version={version}")
            print(f"reason={reason}")
            return 0

        nav = read_nav(Path(args.mkdocs))
        out = Path(args.out)
        build(Path(args.src), Path(args.mkdocs), out,
              str(docs_cfg.get("link_policy", "absolute")),
              args.site_url, args.repo_blob_url)
        problems = verify(Path(args.src), out, nav)
        for line in problems:
            print(f"❌ {line}", file=sys.stderr)
        if problems:
            print("逐章比對未過——不建置、不推送。", file=sys.stderr)
            return 1
        print(f"✅ 逐章比對全綠（{len(nav)} 章）→ {out}")
        return 0
    except ConfigError as exc:
        print(f"❌ 設定錯誤：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
