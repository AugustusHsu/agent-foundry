#!/usr/bin/env python3
"""foundry-lint：檢查文件是否含模板規定的必備二級標題，並提供 repo 規範自檢。

規格來源：docs/features/foundry-lint/LLD.md（介面、資料模型、流程、錯誤表均依該文件）。
`--selfcheck` 為 MYL-36 增訂的機械層閘門，四項檢查各對應一個實際踩過的缺陷。
exit code：0＝通過、1＝不通過、2＝執行／使用錯誤。
"""

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

TYPE_TO_TEMPLATE: dict = {
    "brd": "brd.md", "prd": "prd.md", "hld": "hld.md", "lld": "lld.md",
    "review-report": "review-report.md", "test-plan": "test-plan.md",
}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")


class LintError(Exception):
    """執行／使用錯誤（exit 2），訊息直接寫 stderr。"""


@dataclass
class CheckResult:
    file: str
    doc_type: str
    required: list
    missing: list

    @property
    def passed(self) -> bool:
        return not self.missing


def extract_headings(text: str) -> list:
    """回傳二級標題的標題文字有序清單（不含 ``## `` 前綴），保序、不去重。

    圍欄程式碼區塊（``` 或 ~~~）內的行一律跳過；已知簡化：不區分兩種
    圍欄的配對、不比對圍欄長度（見 LLD 第 4 節）。
    """
    headings = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) == 2:
            headings.append(m.group(2))
    return headings


def read_text(path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def build_rules(template_path) -> list:
    """讀模板並抽出必備標題（去重保序）；讀不到或抽不出即 LintError。"""
    try:
        text = read_text(template_path)
    except OSError as e:
        raise LintError(
            f"foundry-lint: 錯誤：無法讀取模板：{template_path}（{e.strerror or e}）"
        ) from e
    required = list(dict.fromkeys(extract_headings(text)))
    if not required:
        raise LintError(
            f"foundry-lint: 錯誤：模板未含任何二級標題，無法建立規則：{template_path}"
        )
    return required


def check_file(file: str, doc_type: str, required: list) -> CheckResult:
    try:
        text = read_text(file)
    except OSError as e:
        raise LintError(
            f"foundry-lint: 錯誤：無法讀取檔案：{file}（{e.strerror or e}）"
        ) from e
    found = set(extract_headings(text))
    missing = [h for h in required if h not in found]
    return CheckResult(file=file, doc_type=doc_type, required=required, missing=missing)


def render_text(result: CheckResult) -> str:
    if result.passed:
        return (
            f"✅ {result.file} 通過 {result.doc_type} 模板章節檢查"
            f"（必備章節 {len(result.required)} 項齊備）"
        )
    lines = [
        f"❌ {result.file} 未通過 {result.doc_type} 模板章節檢查，"
        f"缺少 {len(result.missing)} 項必備章節："
    ]
    lines.extend(f"  - ## {h}" for h in result.missing)
    return "\n".join(lines)


def render_json(result: CheckResult) -> str:
    return json.dumps(
        {
            "file": result.file,
            "type": result.doc_type,
            "passed": result.passed,
            "missing_sections": [f"## {h}" for h in result.missing],
        },
        ensure_ascii=False,
        indent=2,
    )


# ══════════════════════ selfcheck：repo 規範自檢（MYL-36） ══════════════════════
#
# 四項檢查，每一項都對應一個實際發生過的缺陷——不是預想的風險：
#   entry-sync  雙入口 CLAUDE.md／AGENTS.md 共用正文漂移
#   nav-sync    手冊章節與兩份 nav 不同步 → 公開站漏章（MYL-31）
#   anchors     中文錨點與 mkdocs slug 不符 → 點了不跳轉（MYL-25）
#   rule-ids    引用了不存在的規則 ID（protocol 第 11 節）

SHARED_BEGIN = "<!-- FOUNDRY:SHARED-BODY:BEGIN -->"
SHARED_END = "<!-- FOUNDRY:SHARED-BODY:END -->"

#: 規則 ID 的字面形狀：單一大寫字母 ＋（`-字母` 或數字）。例：`G-A`、`H3`、`C10`。
#: 前綴未登記於 protocol 第 11 節者一律略過（如 known-drift 自有的 L*／S*／R*／X*）。
ID_TOKEN_RE = re.compile(r"^([A-Z])(?:-([A-Z])|(\d+))$")
BACKTICK_RE = re.compile(r"`([^`\n]{2,8})`")
RANGE_RE = re.compile(r"`([A-Z])(\d+)`\s*[～~]\s*`([A-Z])(\d+)`")

LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
INLINE_CODE_RE = re.compile(r"`([^`]*)`")
EMPHASIS_RE = re.compile(r"\*{1,3}([^*]+)\*{1,3}")
MD_LINK_TARGET_RE = re.compile(r"\]\(([^)\s]+)\)")
CHAPTER_FILE_RE = re.compile(r"(\d{2}-[a-z0-9-]+\.md)")


@dataclass
class SelfcheckResult:
    """單項自檢結果。`failures` 每一則都要能讓讀者直接知道去改哪裡。"""

    name: str
    summary: str
    failures: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def _strip_inline(text: str) -> str:
    """去掉行內 markdown 標記，取出 mkdocs 實際拿去 slugify 的純文字。"""
    text = LINK_RE.sub(r"\1", text)
    text = INLINE_CODE_RE.sub(r"\1", text)
    text = EMPHASIS_RE.sub(r"\1", text)
    return text


def mkdocs_slug(text: str, separator: str = "-") -> str:
    """複製 markdown.extensions.toc 預設 slugify（unicode=False）的行為。

    關鍵：`unicode=False` 會把非 ASCII 字元整個丟掉，所以中文標題
    `## 3. HITL 發卡` 的 slug 是 `3-hitl` 而非中文字面——MYL-25 就是踩這個。
    """
    value = unicodedata.normalize("NFKD", _strip_inline(text))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[%s\s]+" % re.escape(separator), separator, value)


def extract_all_headings(text: str) -> list:
    """回傳所有層級的標題文字（跳過圍欄區塊），供錨點檢查用。"""
    headings = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            headings.append(m.group(2))
    return headings


def anchors_of(text: str) -> set:
    """一份文件可跳轉的錨點集合，含 mkdocs 對重複 slug 的 `_1` 後綴規則。"""
    seen: dict = {}
    anchors = set()
    for heading in extract_all_headings(text):
        slug = mkdocs_slug(heading)
        if not slug:
            continue
        if slug in seen:
            seen[slug] += 1
            slug = f"{slug}_{seen[slug]}"
        else:
            seen[slug] = 0
        anchors.add(slug)
    return anchors


def check_entry_sync(root: Path) -> SelfcheckResult:
    """CLAUDE.md 與 AGENTS.md 的共用正文必須逐字相同。"""
    res = SelfcheckResult("entry-sync", "雙入口共用正文同步")
    bodies = {}
    for name in ("CLAUDE.md", "AGENTS.md"):
        path = root / name
        if not path.exists():
            res.failures.append(f"{name} 不存在——repo 根缺少接手入口檔")
            continue
        text = read_text(path)
        if SHARED_BEGIN not in text or SHARED_END not in text:
            res.failures.append(
                f"{name} 缺少 {SHARED_BEGIN} / {SHARED_END} 標記，無法比對共用正文"
            )
            continue
        bodies[name] = text[text.index(SHARED_BEGIN) : text.index(SHARED_END)]
    if len(bodies) == 2 and bodies["CLAUDE.md"] != bodies["AGENTS.md"]:
        a = bodies["CLAUDE.md"].splitlines()
        b = bodies["AGENTS.md"].splitlines()
        diff = next(
            (
                i + 1
                for i, (x, y) in enumerate(zip(a, b))
                if x != y
            ),
            min(len(a), len(b)) + 1,
        )
        res.failures.append(
            f"CLAUDE.md 與 AGENTS.md 的共用正文不一致（首個差異在標記後第 {diff} 行）"
            "——改一份就要改另一份"
        )
    return res


def check_nav_sync(root: Path) -> SelfcheckResult:
    """手冊章節檔、mkdocs.yml nav、發佈腳本內嵌 nav 三者必須一致。

    腳本內嵌的是**第二份** mkdocs.yml；只改一份會讓公開站漏章（MYL-31）。
    """
    res = SelfcheckResult("nav-sync", "手冊章節與兩份 nav 一致")
    handbook = root / "docs" / "handbook"
    if not handbook.is_dir():
        res.failures.append("docs/handbook/ 不存在")
        return res

    on_disk = {p.name for p in handbook.glob("[0-9][0-9]-*.md")}

    mkdocs = root / "mkdocs.yml"
    in_mkdocs = set()
    if mkdocs.exists():
        in_mkdocs = set(CHAPTER_FILE_RE.findall(read_text(mkdocs)))
    else:
        res.failures.append("mkdocs.yml 不存在")

    script = root / "scripts" / "publish-handbook.sh"
    in_script = set()
    if script.exists():
        text = read_text(script)
        marker = 'cat > "$WORK/repo/mkdocs.yml" <<YMLEOF'
        if marker in text:
            block = text[text.index(marker) :]
            end = block.find("\nYMLEOF")
            in_script = set(CHAPTER_FILE_RE.findall(block[: end if end > 0 else None]))
        else:
            res.failures.append(
                f"scripts/publish-handbook.sh 找不到內嵌 mkdocs.yml 區塊標記：{marker}"
            )
    else:
        res.failures.append("scripts/publish-handbook.sh 不存在")

    for label, found in (("mkdocs.yml", in_mkdocs), ("publish-handbook.sh 內嵌 nav", in_script)):
        if not found:
            continue
        for missing in sorted(on_disk - found):
            res.failures.append(
                f"{label} 的 nav 沒有 {missing}——手冊有這一章但該 nav 漏了，公開站會看不到"
            )
        for extra in sorted(found - on_disk):
            res.failures.append(
                f"{label} 的 nav 指向不存在的章節 {extra}——檔案已刪或改名，nav 沒跟上"
            )
    res.summary += f"（章節 {len(on_disk)} 篇）"
    return res


def check_handbook_anchors(root: Path) -> SelfcheckResult:
    """手冊內部連結的錨點必須對得上 mkdocs 產生的 slug。"""
    res = SelfcheckResult("anchors", "手冊內部錨點可跳轉")
    handbook = root / "docs" / "handbook"
    if not handbook.is_dir():
        res.failures.append("docs/handbook/ 不存在")
        return res

    pages = {p.name: read_text(p) for p in sorted(handbook.glob("*.md"))}
    cache = {name: anchors_of(text) for name, text in pages.items()}
    total = 0
    for name, text in pages.items():
        for target in MD_LINK_TARGET_RE.findall(text):
            if "#" not in target or target.startswith(("http://", "https://", "mailto:")):
                continue
            page, _, anchor = target.partition("#")
            if not anchor:
                continue
            total += 1
            target_page = name if page in ("", ".") else page.split("/")[-1]
            if target_page not in cache:
                res.failures.append(
                    f"{name} 連到 {target}，但手冊裡沒有 {target_page} 這一章"
                )
                continue
            if anchor not in cache[target_page]:
                res.failures.append(
                    f"{name} 的連結 `{target}` 錨點不存在——"
                    f"mkdocs 對中文標題產生的是 ASCII slug，不是中文字面"
                )
    res.summary += f"（內部錨點連結 {total} 個）"
    return res


def parse_rule_id_registry(protocol_text: str) -> tuple:
    """從 protocol「規則 ID 索引」一節解析已登記的 ID 集合。

    回傳 (已登記 ID 集合, 已登記前綴集合, 索引節的原文)。
    """
    marker = "## 11. 規則 ID 索引"
    if marker not in protocol_text:
        return set(), set(), ""
    section = protocol_text[protocol_text.index(marker) :]
    nxt = section.find("\n## ", 1)
    section = section[: nxt if nxt > 0 else None]

    declared = set()
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        col = line.split("|")[1] if len(line.split("|")) > 1 else ""
        for a, lo, b, hi in RANGE_RE.findall(col):
            if a == b:
                declared.update(f"{a}{n}" for n in range(int(lo), int(hi) + 1))
        for tok in BACKTICK_RE.findall(col):
            if ID_TOKEN_RE.match(tok):
                declared.add(tok)
    prefixes = {ID_TOKEN_RE.match(t).group(1) for t in declared}
    return declared, prefixes, section


def check_rule_ids(root: Path) -> SelfcheckResult:
    """repo 內引用的規則 ID 必須已登記且在 protocol 有定義。"""
    res = SelfcheckResult("rule-ids", "規則 ID 引用有效")
    protocol = root / "skills" / "foundry-protocol" / "SKILL.md"
    if not protocol.exists():
        res.failures.append("skills/foundry-protocol/SKILL.md 不存在")
        return res

    text = read_text(protocol)
    declared, prefixes, registry = parse_rule_id_registry(text)
    if not declared:
        res.failures.append(
            "protocol 找不到「## 11. 規則 ID 索引」或該節未登記任何 ID"
        )
        return res

    # 每個登記的 ID 都要在 protocol 本文（索引節之外）真的被定義。
    body = text.replace(registry, "")
    body_tokens = set(BACKTICK_RE.findall(body))
    for rid in sorted(declared):
        if rid not in body_tokens:
            res.failures.append(
                f"`{rid}` 登記於第 11 節索引，但 protocol 本文找不到它的定義"
            )

    # repo 內所有 .md 對已登記前綴的引用，都必須落在已登記範圍內。
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if rel.parts[0] in (".git", "node_modules", "site"):
            continue
        for tok in set(BACKTICK_RE.findall(read_text(path))):
            m = ID_TOKEN_RE.match(tok)
            if not m or m.group(1) not in prefixes:
                continue
            if tok not in declared:
                res.failures.append(
                    f"{rel} 引用了 `{tok}`，但第 11 節索引沒有登記這個 ID"
                    "——ID 打錯，或新條款忘了登記"
                )
    res.summary += f"（已登記 {len(declared)} 個 ID）"
    return res


SELFCHECKS = (check_entry_sync, check_nav_sync, check_handbook_anchors, check_rule_ids)


def run_selfcheck(root: Path) -> list:
    return [check(root) for check in SELFCHECKS]


def render_selfcheck_text(results: list) -> str:
    lines = []
    for r in results:
        mark = "✅" if r.passed else "❌"
        lines.append(f"{mark} [{r.name}] {r.summary}")
        lines.extend(f"  - {f}" for f in r.failures)
    bad = sum(len(r.failures) for r in results)
    lines.append(
        "foundry-lint --selfcheck：全部通過"
        if not bad
        else f"foundry-lint --selfcheck：{bad} 項未通過"
    )
    return "\n".join(lines)


def render_selfcheck_json(results: list) -> str:
    return json.dumps(
        {
            "passed": all(r.passed for r in results),
            "checks": [
                {"name": r.name, "passed": r.passed, "failures": r.failures}
                for r in results
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


# ═══════════════════════════════ CLI ═══════════════════════════════


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="foundry-lint",
        description="檢查文件是否含模板規定的必備二級標題；--selfcheck 改跑 repo 規範自檢",
    )
    parser.add_argument("--type", choices=TYPE_TO_TEMPLATE.keys())
    parser.add_argument("--format", default="text", choices=["text", "json"])
    parser.add_argument("--templates-dir", default=None)
    parser.add_argument(
        "--selfcheck",
        action="store_true",
        help="跑 repo 規範自檢（雙入口同步、手冊 nav、錨點、規則 ID），不需 --type／file",
    )
    parser.add_argument("--repo-root", default=None, help="自檢的 repo 根目錄，預設為本檔上溯兩層")
    parser.add_argument("file", nargs="?")
    args = parser.parse_args(argv)
    if not args.selfcheck and (args.type is None or args.file is None):
        parser.error("需要 --type 與 file（或改用 --selfcheck）")
    return args


def main(argv=None):
    args = parse_args(argv)
    exit_code = 0

    if args.selfcheck:
        root = (
            Path(args.repo_root)
            if args.repo_root
            else Path(__file__).resolve().parent.parent.parent
        )
        try:
            results = run_selfcheck(root)
        except LintError as e:
            print(e, file=sys.stderr)
            sys.exit(2)
        render = render_selfcheck_json if args.format == "json" else render_selfcheck_text
        print(render(results))
        sys.exit(0 if all(r.passed for r in results) else 1)

    try:
        if args.templates_dir:
            templates_dir = Path(args.templates_dir)
        else:
            templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
        template_path = templates_dir / TYPE_TO_TEMPLATE[args.type]
        required = build_rules(template_path)
        result = check_file(args.file, args.type, required)
    except LintError as e:
        print(e, file=sys.stderr)
        exit_code = 2
    else:
        render = render_json if args.format == "json" else render_text
        print(render(result))
        if not result.passed:
            exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
