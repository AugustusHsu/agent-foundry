#!/usr/bin/env python3
"""逐章比對「來源手冊」與「投影到 wiki 的結果」，產出對照表。

MYL-52 驗收條件 4：**不接受「應該搬完了」，缺一章就是紅燈。**
所以這支的輸出是一張逐章對照表（貼工單當證據），退出碼是閘門本身：
任何一格紅，`exit 1`，`scripts/publish-wiki.sh` 就不會 push。

比對四件事，全部是使用者點名要的：

| 比什麼 | 為什麼是這個 |
| --- | --- |
| 標題文字 | 章節搬錯位、搬了空檔，H1 會先露餡 |
| 章節數（H2） | 內容被截斷最容易在這裡看出來——投影是整檔覆寫，截半不會有語法錯誤 |
| 內部連結目標 | 投影會改寫連結（去 `.md`、換錨點），**改寫本身就是最可能出錯的一步** |
| MYL-44 戳記行 | 戳記是手冊與 protocol 對照過的憑證；投影掉了它，wiki 讀者就無從判斷自己讀的是哪一版規則 |

**這支證得了什麼、證不了什麼**（照 known-drift `X4` 的教訓寫清楚）：
它驗的是「投影自我一致」——連結指得到投影後真的存在的頁面與標題。
它**不驗** GitHub 實際渲染出來的錨點字串是否等於 `project_docs.github_slug` 算的那個。
那件事本機證不了，只能在 wiki 實站點一遍。表格因此把錨點另列一欄標明「待實站驗」。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "foundry-lint"))

from foundry_lint import (  # noqa: E402
    STAMP_RE,
    STAMPED_CHAPTERS,
    extract_headings,
    read_text,
)
from project_docs import (  # noqa: E402
    EXTERNAL_RE,
    MD_LINK_RE,
    github_anchors,
    wiki_link_target,
    wiki_page_name,
)


class ChapterReport:
    def __init__(self, source_name: str):
        self.source = source_name
        self.page = wiki_page_name(source_name)
        self.problems = []
        self.src_h1 = ""
        self.wiki_h1 = ""
        self.src_h2 = 0
        self.wiki_h2 = 0
        self.links_checked = 0
        self.anchors_to_verify = 0
        self.stamp = "—"

    @property
    def ok(self) -> bool:
        return not self.problems


def first_h1(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def stamp_line(text: str) -> str:
    """章標題後第一個非空行，若它是 MYL-44 戳記就回傳原文，否則空字串。"""
    lines = text.splitlines()
    candidate = next((ln for ln in lines[1:] if ln.strip()), "")
    return candidate.strip() if STAMP_RE.match(candidate) else ""


def compare(src_dir: Path, wiki_dir: Path) -> tuple:
    """回傳 `(逐章報告清單, 全域問題清單)`。"""
    sources = {p.name: read_text(p) for p in sorted(src_dir.glob("*.md"))}
    wiki_pages = {p.name: read_text(p) for p in sorted(wiki_dir.glob("*.md"))}
    anchors = {name: github_anchors(body) for name, body in wiki_pages.items()}

    reports, global_problems = [], []

    expected_pages = {wiki_page_name(n) for n in sources}
    generated = {"_Sidebar.md", "_Footer.md"}
    for extra in sorted(set(wiki_pages) - expected_pages - generated):
        global_problems.append(
            f"wiki 多出一頁 `{extra}`：不在來源手冊裡，也不是投影產生的側欄／頁尾"
            "——多半是有人手動建的頁面"
        )
    for required in ("_Sidebar.md", "_Footer.md"):
        if required not in wiki_pages:
            global_problems.append(f"投影少了 `{required}`")

    for name, src_text in sources.items():
        rep = ChapterReport(name)
        wiki_text = wiki_pages.get(rep.page)
        if wiki_text is None:
            rep.problems.append(f"wiki 沒有 `{rep.page}` 這一頁——整章沒搬過去")
            reports.append(rep)
            continue

        rep.src_h1 = first_h1(src_text)
        rep.wiki_h1 = first_h1(wiki_text)
        if rep.src_h1 != rep.wiki_h1:
            rep.problems.append(
                f"H1 標題不一致：來源「{rep.src_h1}」vs wiki「{rep.wiki_h1}」"
            )

        rep.src_h2 = len(extract_headings(src_text))
        rep.wiki_h2 = len(extract_headings(wiki_text))
        if rep.src_h2 != rep.wiki_h2:
            rep.problems.append(
                f"二級章節數不一致：來源 {rep.src_h2} 節、wiki {rep.wiki_h2} 節"
                "——投影是整檔覆寫，數量對不上代表內容被截斷或多塞了東西"
            )

        if name in STAMPED_CHAPTERS:
            src_stamp = stamp_line(src_text)
            wiki_stamp = stamp_line(wiki_text)
            if not src_stamp:
                rep.problems.append("來源本身沒有 MYL-44 戳記行——先修來源，不是投影的問題")
            elif src_stamp != wiki_stamp:
                rep.problems.append(
                    f"MYL-44 戳記行沒存活：來源「{src_stamp}」、wiki「{wiki_stamp or '（不見了）'}」"
                )
            else:
                rep.stamp = "✅ 存活"

        for _, target in MD_LINK_RE.findall(wiki_text):
            if EXTERNAL_RE.match(target):
                continue
            page_part, sep, anchor = target.partition("#")
            rep.links_checked += 1
            target_page = rep.page if not page_part else f"{page_part}.md"
            if target_page not in wiki_pages:
                rep.problems.append(
                    f"投影後的連結 `{target}` 指向 wiki 沒有的頁面 `{target_page}`"
                )
                continue
            if sep and anchor:
                rep.anchors_to_verify += 1
                if anchor not in anchors[target_page]:
                    rep.problems.append(
                        f"投影後的連結 `{target}` 的錨點在 `{target_page}` 找不到"
                        "對應標題——連結改寫算錯了"
                    )
        reports.append(rep)

    return reports, global_problems


def render_table(reports: list, global_problems: list) -> str:
    lines = [
        "| 章節 | wiki 頁 | H1 標題 | H2 節數（源／wiki） | 內部連結 | 錨點 | 戳記 | 判定 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in reports:
        h1 = "✅ 相同" if r.src_h1 and r.src_h1 == r.wiki_h1 else "❌ 不一致"
        counts = f"{r.src_h2} / {r.wiki_h2}"
        counts = f"✅ {counts}" if r.src_h2 == r.wiki_h2 else f"❌ {counts}"
        links = f"✅ {r.links_checked} 條" if r.links_checked else "—"
        anchor = f"{r.anchors_to_verify} 個待實站驗" if r.anchors_to_verify else "—"
        verdict = "🟢 綠" if r.ok else "🔴 紅"
        lines.append(
            f"| `{r.source}` | `{r.page}` | {h1} | {counts} | {links} | {anchor} "
            f"| {r.stamp} | {verdict} |"
        )
    bad = [r for r in reports if not r.ok]
    lines.append("")
    if bad or global_problems:
        lines.append(f"**未通過 {len(bad)} 章**：")
        for r in bad:
            for p in r.problems:
                lines.append(f"- `{r.source}`：{p}")
        for p in global_problems:
            lines.append(f"- （全域）{p}")
    else:
        total_anchors = sum(r.anchors_to_verify for r in reports)
        lines.append(
            f"**全綠**：{len(reports)} 章全部搬到，標題／節數／連結目標／戳記皆相符。"
            f"其中 {total_anchors} 個錨點是**依 GitHub 的 slug 演算法重算**的，"
            "本機驗不了實際渲染（沒有渲染器，見 known-drift `X4`）——要驗就抓實站的 "
            '`id="user-content-…"` 比對；判準與已驗結果見 known-drift `L16`。'
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="逐章比對來源手冊與 wiki 投影結果")
    ap.add_argument("--src", required=True)
    ap.add_argument("--wiki", required=True)
    args = ap.parse_args(argv)

    src, wiki = Path(args.src), Path(args.wiki)
    for label, path in (("來源", src), ("wiki", wiki)):
        if not path.is_dir():
            print(f"compare_projection: 錯誤：{label}目錄不存在：{path}", file=sys.stderr)
            return 2

    reports, global_problems = compare(src, wiki)
    print(render_table(reports, global_problems))
    return 1 if global_problems or any(not r.ok for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
