#!/usr/bin/env python3
"""publish_docs 的投影引擎：`docs/handbook/` → GitHub wiki 頁面集。

MYL-52。這支模組實作抽象動詞 `publish_docs`（`skills/foundry-platform/SKILL.md` §3.9）
在 `github-wiki` 目標面的內容轉換那一半；push 與防手改偵測歸 `scripts/publish-wiki.sh`。

**判準（計畫 v5，v3 用同一條否決過 E-2）**：機械投影不是第二份真相。
人只改源頭，投影一律機械產生且不接受手改。所以本模組**只做確定性轉換**——
同樣的來源永遠產出同樣的位元組，沒有任何需要人在中間補一手的步驟。

轉換有四項，每一項都是「wiki 與 mkdocs 的載體差異」逼出來的，不是美化：

1. **頁名**：wiki 的首頁固定叫 `Home`，所以 `index.md` → `Home.md`；其餘章節同名平移。
2. **章間連結去掉 `.md`**：wiki 頁面的 URL 是 `.../wiki/<頁名>`，沒有副檔名。
   `[x](04-decision-points.md)` 在 wiki 會解析成 `.../wiki/04-decision-points.md`。
   去掉副檔名之後是**單純的相對 URL 解析**，不倚賴任何 wiki 專屬的連結改寫魔法
   ——這點很重要，因為本機驗不了 wiki 渲染（known-drift `X4`）。
3. **錨點換算**：手冊的錨點是寫給 mkdocs 的。Python-Markdown 預設 slugify
   `unicode=False` 會把非 ASCII 整個丟掉，於是 `## 3. HITL 發卡` 的 slug 是 `3-hitl`；
   GitHub 的 slugger 保留 CJK，同一個標題產生 `3-hitl-發卡`。**照抄過去必然全斷**，
   所以逐一比對標題、把 mkdocs slug 換成 GitHub slug。
4. **repo 內部路徑**：手冊裡指向 `skills/`、`templates/`、`docs/pilot/` 的相對連結
   在 wiki（另一個 git repo、頁面是平的）一定失效，依 `link_policy` 改寫或拆為純文字。

⚠️ 第 3 項有一個本機**證不了**的假設：我實作的 GitHub slugger 與 GitHub 真正用的
那支是否逐字一致。這裡的檢查只能保證「投影自我一致」（錨點指得到投影後文件裡真的
存在的標題），不能保證 GitHub 算出來的字串跟我算的一樣。那一步只能在 wiki 實站驗
——這正是 `X4` 記下的處境：手上沒有便宜的驗證手段，就不要用本機推論冒充實測。
"""

import argparse
import hashlib
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "foundry-lint"))

# 共用 foundry-lint 的 mkdocs slugify 與標題抽取，不另抄一份：
# 同一個演算法抄在兩處，就是這個 repo 反覆記錄的漂移來源。
from foundry_lint import (  # noqa: E402
    FENCE_RE,
    HEADING_RE,
    extract_all_headings,
    mkdocs_slug,
    read_text,
)

HOME_PAGE = "Home"
INDEX_SOURCE = "index.md"

# markdown 連結，連結文字與目標分開抓——目標要改寫，文字在 plain policy 下要留著。
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
EXTERNAL_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|//)")
NAV_ENTRY_RE = re.compile(r"^\s+-\s+(.+?):\s+handbook/([A-Za-z0-9_-]+\.md)\s*$")

# github-slugger 會剝掉的標點集合。來源：該套件的 regex，這裡只取 ASCII 標點與
# 常見的中日韓標點——手冊標題實際用到的就這些。刻意不做「全部非文字字元都剝」：
# 那會連 CJK 一起吃掉，變成 mkdocs 的行為，正好是要避免的那個錯。
GITHUB_STRIP_RE = re.compile(
    r"['\"!#$%&()*+,./:;<=>?@\[\]^`{|}~ -⁯⸀-⹿"
    r"？！，。、；：（）《》「」『』【】—…·]"
)


def github_slug(text: str) -> str:
    """複製 github-slugger 的行為：小寫、剝標點、空白轉 `-`、**保留 CJK**。

    與 `mkdocs_slug` 的差別只有一個但是致命的：那支把非 ASCII 丟掉，這支留著。
    手冊的中文標題在兩邊因此得到完全不同的錨點。
    """
    value = unicodedata.normalize("NFKC", _strip_inline_markup(text))
    value = value.lower()
    value = GITHUB_STRIP_RE.sub("", value)
    value = re.sub(r"[-\s]+", "-", value.strip())
    return value.strip("-")


def _strip_inline_markup(text: str) -> str:
    """去掉標題裡的行內語法（反引號、粗體、連結外框），只留會進 slug 的文字。"""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return text


def _dedupe(slug: str, seen: dict, joiner: str) -> str:
    """重複 slug 的後綴規則：mkdocs 用 `_1`、GitHub 用 `-1`，兩邊都從 1 起算。"""
    if slug not in seen:
        seen[slug] = 0
        return slug
    seen[slug] += 1
    return f"{slug}{joiner}{seen[slug]}"


def anchor_map(text: str) -> dict:
    """建立「mkdocs slug → GitHub slug」對照表。

    兩邊各自跑一次去重計數，因為重複標題在兩套 slugger 底下不見得撞在一起：
    `## 一` 與 `## 二` 的 mkdocs slug 都是空字串（非 ASCII 全丟），GitHub 那邊
    卻是兩個不同的 slug。共用一份計數會錯位。
    """
    mk_seen, gh_seen, mapping = {}, {}, {}
    for heading in extract_all_headings(text):
        mk = mkdocs_slug(heading)
        gh = github_slug(heading)
        mk = _dedupe(mk, mk_seen, "_") if mk else ""
        gh = _dedupe(gh, gh_seen, "-") if gh else ""
        if mk and gh:
            mapping.setdefault(mk, gh)
    return mapping


def github_anchors(text: str) -> set:
    """一份文件在 GitHub 上可跳轉的錨點集合（含去重後綴）。"""
    seen, anchors = {}, set()
    for heading in extract_all_headings(text):
        slug = github_slug(heading)
        if slug:
            anchors.add(_dedupe(slug, seen, "-"))
    return anchors


def wiki_page_name(source_name: str) -> str:
    """來源檔名 → wiki 頁面檔名。`index.md` 是首頁，wiki 規定叫 `Home`。"""
    return f"{HOME_PAGE}.md" if source_name == INDEX_SOURCE else source_name


def wiki_link_target(source_name: str) -> str:
    """來源檔名 → 章間連結該寫的目標（沒有副檔名，見模組說明第 2 點）。"""
    return HOME_PAGE if source_name == INDEX_SOURCE else source_name[:-3]


def repo_path_of(target: str) -> str:
    """把手冊裡的相對路徑換算成 repo 根起算的路徑。

    手冊檔案住在 `docs/handbook/`，所以 `../../skills/x` → `skills/x`、
    `../pilot/y` → `docs/pilot/y`。用字串運算而不是 `os.path.normpath` 之後再
    拼接，是為了讓這支在任何工作目錄下結果都一樣。
    """
    parts = []
    for seg in f"docs/handbook/{target}".split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    return "/".join(parts)


def rewrite_links(text: str, source_name: str, sources: dict,
                  link_policy: str, repo_blob_url: str) -> tuple:
    """改寫一份手冊的所有連結，回傳 `(改寫後文字, 警告清單)`。

    `sources` 是 `{來源檔名: 內容}`，用來查目標章節的標題以換算錨點。
    警告是「投影得出來但可能不對」的東西（錨點在目標章節查無此標題之類），
    不阻斷投影——阻斷歸 `compare_projection.py`，那支才是閘門。
    """
    warnings = []
    anchor_cache = {name: anchor_map(body) for name, body in sources.items()}

    def convert(m):
        label, target = m.group(1), m.group(2)
        if EXTERNAL_RE.match(target):
            return m.group(0)

        page_part, sep, anchor = target.partition("#")

        # 同頁錨點（`#foo`）：頁面就是自己。
        if not page_part:
            new_anchor = anchor_cache.get(source_name, {}).get(anchor)
            if new_anchor is None:
                warnings.append(
                    f"{source_name}：同頁錨點 `#{anchor}` 在本章標題裡找不到對應，原樣保留"
                )
                return m.group(0)
            return f"[{label}](#{new_anchor})"

        basename = page_part.split("/")[-1]
        # 指向手冊內的另一章。
        if basename in sources and repo_path_of(page_part) == f"docs/handbook/{basename}":
            new_target = wiki_link_target(basename)
            if sep:
                new_anchor = anchor_cache.get(basename, {}).get(anchor)
                if new_anchor is None:
                    warnings.append(
                        f"{source_name}：連到 `{target}`，但 {basename} 沒有對得上的標題"
                        "——錨點原樣保留，投影後會斷"
                    )
                    new_anchor = anchor
                new_target = f"{new_target}#{new_anchor}"
            return f"[{label}]({new_target})"

        # 指向 repo 內、手冊外的路徑（skills/、templates/、docs/pilot/…）。
        repo_path = repo_path_of(page_part)
        if link_policy == "plain":
            return label
        return f"[{label}]({repo_blob_url.rstrip('/')}/{repo_path}{sep}{anchor})"

    out_lines, in_fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        # 圍欄裡的 `[x](y)` 是語法示例不是連結，改了就是竄改內容。
        out_lines.append(line if in_fence else MD_LINK_RE.sub(convert, line))
    tail = "\n" if text.endswith("\n") else ""
    return "\n".join(out_lines) + tail, warnings


def read_nav(mkdocs_yml: Path) -> list:
    """從私有 `mkdocs.yml` 讀手冊 nav，回傳 `[(標題, 來源檔名), …]`。

    **刻意不另寫一份 nav**：known-drift 已記錄「兩份 nav 的結構性漂移」
    （`mkdocs.yml` 與發佈腳本內嵌那份），新增手冊章節只改一份就會漏章。
    wiki 的側欄如果再手寫一份，那就是第三份。這裡改成轉寫既有的 `mkdocs.yml`，
    正是那條漂移記錄裡寫的「根治」方向。
    """
    if not mkdocs_yml.exists():
        return []
    nav = []
    for line in read_text(mkdocs_yml).splitlines():
        m = NAV_ENTRY_RE.match(line)
        if m:
            nav.append((m.group(1).strip(), m.group(2)))
    return nav


def build_sidebar(nav: list) -> str:
    lines = ["## Foundry 使用手冊", ""]
    for title, source_name in nav:
        lines.append(f"- [{title}]({wiki_link_target(source_name)})")
    lines.append("")
    return "\n".join(lines)


def build_footer(handbook_commit: str) -> str:
    return (
        "---\n\n"
        "🤖 **本 wiki 是機械投影，請勿直接編輯。**\n"
        "唯一可寫的真相是內部 repo `agent-foundry` 的 `docs/handbook/`；"
        "本站由 `scripts/publish-wiki.sh` 於每次手冊變更合併進 main 後同步產生。\n"
        f"在此編輯的內容會在下次同步時**被偵測到並擋下同步**（不是被覆蓋）——"
        "請改回源頭發 PR／開工單。\n\n"
        f"來源 commit：`{handbook_commit}`\n"
    )


def project(src_dir: Path, mkdocs_yml: Path, handbook_commit: str,
            link_policy: str = "absolute",
            repo_blob_url: str = "https://github.com/AugustusHsu/agent-foundry/blob/main"
            ) -> tuple:
    """把 `src_dir` 的手冊投影成 wiki 頁面集，回傳 `(頁面字典, 警告清單)`。"""
    sources = {p.name: read_text(p) for p in sorted(src_dir.glob("*.md"))}
    pages, warnings = {}, []
    for name, body in sources.items():
        new_body, warn = rewrite_links(body, name, sources, link_policy, repo_blob_url)
        pages[wiki_page_name(name)] = new_body
        warnings.extend(warn)
    nav = read_nav(mkdocs_yml)
    if nav:
        pages["_Sidebar.md"] = build_sidebar(nav)
    else:
        warnings.append("讀不到 mkdocs.yml 的手冊 nav，未產生 _Sidebar.md")
    pages["_Footer.md"] = build_footer(handbook_commit)
    return pages, warnings


def digest_of(pages: dict) -> str:
    """頁面集的內容摘要，寫進投影 commit 的 trailer 供防手改比對。

    連頁名一起餵進去：只雜湊內容的話，把兩頁互換檔名不會被察覺。
    """
    h = hashlib.sha256()
    for name in sorted(pages):
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update(pages[name].encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def digest_of_dir(path: Path) -> str:
    """磁碟上一份 wiki 工作區的摘要，與 `digest_of` 同演算法。"""
    pages = {p.name: read_text(p) for p in sorted(path.glob("*.md"))}
    return digest_of(pages)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="把 docs/handbook/ 投影成 GitHub wiki 頁面")
    ap.add_argument("--src", required=True, help="來源目錄（docs/handbook）")
    ap.add_argument("--out", required=True, help="輸出目錄（wiki 工作區）")
    ap.add_argument("--mkdocs", required=True, help="私有 mkdocs.yml，側欄由它轉寫")
    ap.add_argument("--handbook-commit", required=True, help="來源手冊 commit sha")
    ap.add_argument("--link-policy", choices=("absolute", "plain"), default="absolute",
                    help="repo 內部連結：absolute＝改寫成絕對 URL；plain＝拆為純文字")
    ap.add_argument("--repo-blob-url",
                    default="https://github.com/AugustusHsu/agent-foundry/blob/main")
    ap.add_argument("--print-digest", action="store_true", help="只印內容摘要，不寫檔")
    args = ap.parse_args(argv)

    src = Path(args.src)
    if not src.is_dir():
        print(f"project_docs: 錯誤：來源目錄不存在：{src}", file=sys.stderr)
        return 2

    pages, warnings = project(src, Path(args.mkdocs), args.handbook_commit,
                              args.link_policy, args.repo_blob_url)
    if args.print_digest:
        print(digest_of(pages))
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.md"):
        stale.unlink()
    for name, body in pages.items():
        (out / name).write_text(body, encoding="utf-8")

    for w in warnings:
        print(f"   ⚠️  {w}", file=sys.stderr)
    print(f"   投影 {len(pages)} 頁 → {out}")
    print(f"   摘要 {digest_of(pages)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
