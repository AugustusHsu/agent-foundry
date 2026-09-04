#!/usr/bin/env python3
"""foundry-lint：檢查文件是否含模板規定的必備二級標題，並提供 repo 規範自檢。

規格來源：docs/features/foundry-lint/LLD.md（介面、資料模型、流程、錯誤表均依該文件）。
`--selfcheck` 為 MYL-36 增訂的機械層閘門，每項檢查各對應一個實際踩過的缺陷。
exit code：0＝通過、1＝不通過、2＝執行／使用錯誤。
"""

import argparse
import json
import os
import re
import subprocess
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
# 每一項檢查都對應一個實際發生過的缺陷——不是預想的風險：
#   entry-sync      雙入口 CLAUDE.md／AGENTS.md 共用正文漂移
#   nav-sync        手冊章節與兩份 nav 不同步 → 公開站漏章（MYL-31）
#   anchors         中文錨點與 mkdocs slug 不符 → 點了不跳轉（MYL-25）
#   rule-ids        引用了不存在的規則 ID（protocol 第 11 節）
#   big-files       入口檔的大檔清單漏列 → 接手者整份載入（MYL-42）
#   internal-links  相對連結指向不存在的檔案 → 點了 404（MYL-41）
#   handbook-stamp  protocol 改了而手冊沒跟 → 公開站開始騙人（MYL-44）
#
# （這裡刻意不寫「共 N 項」——那種數字沒有人會回來改，正是 MYL-42 要收掉的漂移。）

#: 自檢掃描 .md 時一律略過的頂層目錄（版控內部、依賴、mkdocs 建置輸出）。
SKIP_DIRS = (".git", "node_modules", "site")

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

#: 入口檔 §4 大檔清單的界線。用標記而非節號，因為節號會隨增訂變動。
BIG_BEGIN = "<!-- FOUNDRY:BIG-FILES:BEGIN -->"
BIG_END = "<!-- FOUNDRY:BIG-FILES:END -->"
#: 達此大小的 .md 就必須在入口檔列名。改這個常數要連帶改入口檔那句話——
#: `check_big_files` 會核對兩者一致，不讓程式與散文各說各話。
BIG_FILE_BYTES = 12 * 1024
#: 掃描範圍：全 repo 共用的規則與說明。不含 `docs/features/`——那是各模組
#: 自己的交付物，只在做該模組時讀，列進入口檔只會讓它隨模組數無限膨脹。
BIG_SCAN_DIRS = ("skills", "docs")
BIG_SKIP_PREFIXES = (("docs", "features"),)
#: 清單裡的路徑一律寫成 `反引號包住的 .md 路徑`。
MD_PATH_RE = re.compile(r"`([^`\n]+\.md)`")

#: 不需驗檔案存在性的連結目標：帶協定的 URL（`https:`、`mailto:`）、
#: 協定相對網址（`//host/…`）、以及純錨點（`#anchor`，同頁跳轉）。
EXTERNAL_TARGET_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|//|#)")

# ── 手冊同步戳記（MYL-44）─────────────────────────────────────────────────
#: 規則層本體。戳記追的就是這一份的修改歷史。
PROTOCOL_REL = "skills/foundry-protocol/SKILL.md"
HANDBOOK_REL = "docs/handbook"
#: 掛戳記的章節。只有這四章在複述規則層語意；`08-cross-platform` 講的是
#: 「把流程帶到別的平台」，不隨 protocol 條文變動，故不掛（計畫 v3 §7）。
STAMPED_CHAPTERS = (
    "03-workflow.md", "04-decision-points.md",
    "06-org-structure.md", "07-workflows.md",
)
#: 戳記行形狀：`> 最後對照 protocol \`<sha>\`（YYYY-MM-DD）`。
#: 寫成 blockquote 是為了在 mkdocs 上與正文區隔；sha 允許短碼（至少 7 碼）。
STAMP_RE = re.compile(
    r"^>\s*最後對照 protocol\s*`([0-9a-fA-F]{7,40})`\s*（(\d{4}-\d{2}-\d{2})）\s*$"
)


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


def strip_code(text: str) -> str:
    """把圍欄區塊與行內程式碼挖掉，只留「真的會被渲染成連結」的正文。

    圍欄裡的 `[文字](路徑)` 是語法示例，反引號裡的是路徑字面——
    兩者都不是連結，掃了只會製造誤報（MYL-39 計畫 v3 §7 明確不做）。
    逐行處理並保留行數，讓挖掉的內容不會把上下兩行黏成一條假連結。
    """
    out = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else INLINE_CODE_RE.sub(" ", line))
    return "\n".join(out)


def check_internal_links(root: Path) -> SelfcheckResult:
    """markdown 相對連結 `[文字](路徑)` 的目標必須真的存在。

    MYL-41：`docs/publish-reviews/` 曾用裸章節檔名連手冊，而相對連結是從
    **所在目錄**解析、不是從 repo 根——`03-workflow.md` 於是指到不存在的
    `docs/publish-reviews/03-workflow.md`。閘門證據文件裡的死連結躺在 main 上，
    正是因為前四項自檢沒有一項驗目標存在性。

    只驗檔案存在；錨點正確性歸 anchors 那一項，外部 URL 的可達性一律不驗。
    """
    res = SelfcheckResult("internal-links", "markdown 相對連結目標存在")
    total = 0
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if rel.parts[0] in SKIP_DIRS:
            continue
        for target in MD_LINK_TARGET_RE.findall(strip_code(read_text(path))):
            if EXTERNAL_TARGET_RE.match(target):
                continue
            file_part = target.partition("#")[0]
            if not file_part:
                continue
            total += 1
            if not (path.parent / file_part).exists():
                resolved = os.path.normpath(str(rel.parent / file_part))
                res.failures.append(
                    f"{rel} 連到 `{target}`，但目標 {resolved} 不存在"
                    "——相對連結從所在目錄解析，不是從 repo 根"
                )
    res.summary += f"（相對連結 {total} 條）"
    return res


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
        if rel.parts[0] in SKIP_DIRS:
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


def scan_big_files(root: Path) -> list:
    """掃描範圍內所有達門檻的 .md，回傳 repo 相對路徑（POSIX 形式），已排序。"""
    found = []
    for top in BIG_SCAN_DIRS:
        base = root / top
        if not base.is_dir():
            continue
        for path in base.rglob("*.md"):
            rel = path.relative_to(root)
            if any(rel.parts[: len(skip)] == skip for skip in BIG_SKIP_PREFIXES):
                continue
            if path.stat().st_size >= BIG_FILE_BYTES:
                found.append(rel.as_posix())
    return sorted(found)


def check_big_files(root: Path) -> SelfcheckResult:
    """入口檔的大檔清單要涵蓋所有達門檻的檔案，且列出的路徑都還在。

    MYL-42：舊版清單把每個檔的 KB 數寫死在散文裡，沒有任何機械驗證——
    數字漂了（宣稱 13KB／實際 12KB），清單本身也漏了兩份後來長大的檔。
    現在改成不寫大小、只寫路徑，由本檢查兜住「漏列」與「路徑失效」兩個方向。

    只擋這兩個方向是刻意的：門檻以下的檔案要不要一併列出屬編輯判斷
    （例如當前平台的 adapter），那是判斷不是漂移，不該讓機械檢查來管。
    """
    res = SelfcheckResult("big-files", "入口檔大檔清單涵蓋所有達門檻檔案")
    kb = BIG_FILE_BYTES // 1024

    block = None
    for name in ("CLAUDE.md", "AGENTS.md"):
        path = root / name
        if not path.exists():
            res.failures.append(f"{name} 不存在——repo 根缺少接手入口檔")
            continue
        text = read_text(path)
        if BIG_BEGIN not in text or BIG_END not in text:
            res.failures.append(
                f"{name} 缺少 {BIG_BEGIN} / {BIG_END} 標記——大檔清單無法機械核對"
            )
            continue
        if block is None:
            # 兩檔的標記都在共用正文內，內容一致由 entry-sync 保證，取一份即可。
            block = text[text.index(BIG_BEGIN) : text.index(BIG_END)]
    if block is None:
        return res

    if f"{kb}KB" not in block:
        res.failures.append(
            f"入口檔的大檔清單沒有寫出 {kb}KB 這個門檻，"
            f"但 BIG_FILE_BYTES 就是 {kb}KB——程式與散文對不上，改了常數要順手改那句話"
        )

    listed = set(MD_PATH_RE.findall(block))
    over_threshold = scan_big_files(root)
    for rel in over_threshold:
        if rel not in listed:
            res.failures.append(
                f"{rel} 已達 {kb}KB 門檻，但入口檔的大檔清單沒有列它"
                "——接手者不會知道這份不該整份載入"
            )
    for rel in sorted(listed):
        if not (root / rel).exists():
            res.failures.append(
                f"入口檔的大檔清單列了 {rel}，但這個路徑不存在——檔案已刪或改名，清單沒跟上"
            )
    res.summary += f"（門檻 {kb}KB，達標 {len(over_threshold)} 份）"
    return res


# ══════════════════ 手冊同步戳記：三層閘門（MYL-44） ══════════════════
#
# 層 0  pre-commit 觸發器（`--staged-handbook-sync`）：改了 protocol 沒動手冊就擋下。
# 層 1  戳記驗證（本檔的 `handbook-stamp` 自檢，跑在 `make check`／CI）。
# 層 2  agent 判斷——**只在被層 0 攔下時才跑**，約每 12 顆 commit 一次。
#
# 設計關鍵：**推戳記本身就是銷案憑證**。agent 不寫「已同步／不需同步＋理由」那種
# 會退化成儀式的散文，它必須把戳記推到新 sha，而那是 diff 上看得見的。
# 「看過了」與「沒看過」因此不再靠自我申報。


def git_run(root: Path, *args) -> tuple:
    """跑 git，回傳 `(ok, stdout)`；git 不存在或不是 repo 時 `ok` 為 False。

    自檢會在沒有 `.git` 的環境跑（單元測試把 repo 複製出來時就刻意不帶），
    所以「拿不到 git」是正常狀況而不是錯誤——那時只驗戳記的字面合法性，
    落後與否留給有 git 的地方（`make check`／CI／pre-commit）判。
    """
    try:
        proc = subprocess.run(
            ("git", "-C", str(root)) + args,
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return False, ""
    return proc.returncode == 0, proc.stdout.strip()


def unsynced_protocol_commits(root: Path, stamp_sha: str) -> list:
    """`stamp_sha` 之後動了 protocol、卻沒有手冊變更同行的 commit（新到舊）。

    判準刻意不是「戳記要等於 protocol 最新 sha」——那個條件在同一顆 commit 內
    永遠無法成立：戳記只能指向已經存在的 commit，指不到自己這顆。改成
    「戳記之後的每一顆 protocol 改動都要有手冊變更同行」，於是「protocol 與手冊
    一起改」的那顆自然算已同步，不必再補一顆戳記 commit 去指它。

    `--no-merges`：合併本身不是改動，改動由被合併的那顆代表；把 merge commit
    算進來的話，每次 `--no-ff` 合併都會冒出一顆假的「動了 protocol 沒動手冊」。
    代價是在 merge commit 裡順手改 protocol（evil merge）會漏掉，那種改法本來就該避免。
    """
    ok, out = git_run(root, "log", "--no-merges", "--format=%H",
                      f"{stamp_sha}..HEAD", "--", PROTOCOL_REL)
    if not ok or not out:
        return []
    unsynced = []
    for sha in out.splitlines():
        _, touched = git_run(root, "diff-tree", "--no-commit-id", "--name-only",
                             "-r", sha, "--", HANDBOOK_REL)
        if not touched:
            unsynced.append(sha)
    return unsynced


def check_handbook_stamp(root: Path) -> SelfcheckResult:
    """四章戳記要存在、格式合法，且不落後於 protocol 的修改歷史。

    MYL-44：`docs/handbook/` 是規則層的說明層，protocol 改了而手冊沒跟，公開站
    就開始騙人。實測 74 顆 commit 裡 16 顆動 protocol，其中 10 顆同一顆就同步了
    手冊，真正會漏的只有 5～6 顆——問題真實但稀疏，所以要零 token 的機械攔截。

    戳記必須落在**標題後第一個非空行**：四章裡有三章的標題下方本來就是引言
    blockquote，位置不定死的話戳記會跟引言黏成同一塊，也無從機械定位。
    """
    res = SelfcheckResult("handbook-stamp", "手冊四章戳記不落後於 protocol")
    has_git, _ = git_run(root, "rev-parse", "--verify", "HEAD")
    for name in STAMPED_CHAPTERS:
        rel = f"{HANDBOOK_REL}/{name}"
        path = root / HANDBOOK_REL / name
        if not path.exists():
            res.failures.append(f"{rel} 不存在——掛戳記的章節少了一份")
            continue
        lines = read_text(path).splitlines()
        # 第 0 行是 H1 標題（手冊每章都以 `# ` 開頭），戳記緊接其後第一個非空行。
        stamp_line = next((ln for ln in lines[1:] if ln.strip()), "")
        m = STAMP_RE.match(stamp_line)
        if not m:
            res.failures.append(
                f"{rel} 標題後第一個非空行不是戳記行，讀到的是"
                f"「{stamp_line.strip() or '（沒有內容）'}」——形狀為"
                " `> 最後對照 protocol `<sha>`（YYYY-MM-DD）`"
            )
            continue
        if not has_git:
            continue
        sha = m.group(1)
        ok, _ = git_run(root, "rev-parse", "--verify", f"{sha}^{{commit}}")
        if not ok:
            res.failures.append(f"{rel} 的戳記 sha `{sha}` 不是本 repo 的 commit")
            continue
        ok, _ = git_run(root, "merge-base", "--is-ancestor", sha, "HEAD")
        if not ok:
            res.failures.append(
                f"{rel} 的戳記 sha `{sha}` 不在 HEAD 的歷史上"
                "——戳記指向別的分支，這份對照無從查證"
            )
            continue
        lagging = unsynced_protocol_commits(root, sha)
        if lagging:
            shown = "、".join(s[:8] for s in lagging[:5])
            more = f"（另有 {len(lagging) - 5} 顆）" if len(lagging) > 5 else ""
            res.failures.append(
                f"{rel} 的戳記停在 `{sha}`，其後有 {len(lagging)} 顆改了 protocol "
                f"卻沒有手冊變更同行的 commit：{shown}{more}"
                "——讀那幾顆的 diff，該補的補進本章，再把戳記推到 protocol 最新 sha"
            )
    ok, latest = git_run(root, "log", "-1", "--format=%h", "--", PROTOCOL_REL)
    res.summary += f"（protocol 最新 {latest}）" if has_git and ok and latest \
        else "（拿不到 git，只驗字面）"
    return res


def check_staged_handbook_sync(root: Path) -> SelfcheckResult:
    """層 0 觸發器：本次 staged 動了 protocol，就必須有手冊變更同行。

    這一項不在 `SELFCHECKS` 裡——它看的是 index 而不是工作區，只在 pre-commit
    跑得到（`--staged-handbook-sync`）。`make check` 那邊由層 1 接手。
    """
    res = SelfcheckResult("staged-handbook-sync", "本次 commit 的 protocol 改動有手冊同行")
    ok, out = git_run(root, "diff", "--cached", "--name-only")
    if not ok:
        res.summary += "（拿不到 git，略過）"
        return res
    staged = out.splitlines()
    if PROTOCOL_REL not in staged:
        res.summary += "（本次未動 protocol）"
        return res
    if any(p.startswith(HANDBOOK_REL + "/") for p in staged):
        res.summary += "（protocol 與手冊同行）"
        return res
    _, latest = git_run(root, "log", "-1", "--format=%h", "--", PROTOCOL_REL)
    res.failures.append(
        f"本次 commit 改了 {PROTOCOL_REL}，但 {HANDBOOK_REL}/ 沒有任何變更。\n"
        f"  手冊是規則層的說明層，規則改了而說明沒跟，公開站就開始騙人。\n"
        f"  讀本次 protocol diff，判斷 {'、'.join(STAMPED_CHAPTERS)} 這四章要不要改，然後：\n"
        f"    (1) 要改內容 → 改完連戳記一起 commit；\n"
        f"    (2) 內容不用改 → 只把戳記推到 `{latest or '<protocol 最新 sha>'}`＋今天日期，一起 commit；\n"
        f"    (3) 戳記已是該 sha 且日期同天（同一天第二次改 protocol）→ 把本次改動\n"
        f"        `git commit --amend` 併進前一顆，或先 `--no-verify` commit 這顆、\n"
        f"        再補一顆戳記-only commit 把戳記推到新 sha（漏補的話 `make check` 的\n"
        f"        handbook-stamp 會紅，這條路封閉，矇混不過去）。"
    )
    return res


def handbook_diff_is_stamp_only(root: Path, base_sha: str) -> tuple:
    """`base_sha..HEAD` 的手冊變更是不是只有戳記行。

    回傳 `(只有戳記?, 動到手冊的 commit 摘要清單, 第一個實質變更行)`。
    `scripts/publish-handbook.sh` 用它判斷能否略過發佈審查——戳記-only 的 commit
    會換掉手冊 sha，找不到對應的 APPROVED 記錄，發佈就會被自己的閘門擋死。
    判定條件是機械的（`git diff` 說了算），所以這是封閉的洞、不是人治例外：
    夾帶任何一行實質內容就會落回原來的閘門。
    """
    ok, out = git_run(root, "diff", "-U0", f"{base_sha}..HEAD", "--", HANDBOOK_REL)
    if not ok:
        return False, [], f"取不到 {base_sha}..HEAD 的手冊 diff（sha 無效或不是 git repo）"
    offending = ""
    for line in out.splitlines():
        # diff header（`diff --git`、`index`、`@@`）與 `\ No newline` 都不是變更行；
        # `+++`／`---` 是檔名行，長得像變更行但不是。
        if line.startswith(("+++", "---")) or line[:1] not in ("+", "-"):
            continue
        if not STAMP_RE.match(line[1:]):
            offending = line
            break
    _, log = git_run(root, "log", "--format=%h %s", f"{base_sha}..HEAD",
                     "--", HANDBOOK_REL)
    return (not offending), (log.splitlines() if log else []), offending


SELFCHECKS = (check_entry_sync, check_nav_sync, check_handbook_anchors, check_rule_ids,
              check_big_files, check_internal_links, check_handbook_stamp)


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
        help="跑 repo 規範自檢（雙入口同步、手冊 nav、錨點、規則 ID、大檔清單、"
             "相對連結、手冊戳記），不需 --type／file",
    )
    parser.add_argument(
        "--staged-handbook-sync",
        action="store_true",
        help="層 0 觸發器（pre-commit 用）：本次 staged 改了 protocol 卻沒動"
             " docs/handbook/ 就擋下",
    )
    parser.add_argument(
        "--stamp-only-since",
        metavar="SHA",
        default=None,
        help="判定 SHA..HEAD 的 docs/handbook/ 變更是否只有同步戳記行；"
             "通過時 stdout 列出那些 commit（scripts/publish-handbook.sh 的戳記旁路用）",
    )
    parser.add_argument("--repo-root", default=None, help="自檢的 repo 根目錄，預設為本檔上溯兩層")
    parser.add_argument("file", nargs="?")
    args = parser.parse_args(argv)
    other_modes = args.selfcheck or args.staged_handbook_sync or args.stamp_only_since
    if not other_modes and (args.type is None or args.file is None):
        parser.error("需要 --type 與 file（或改用 --selfcheck）")
    return args


def repo_root_of(args) -> Path:
    """自檢類模式的 repo 根：`--repo-root` 優先，否則由本檔位置上溯兩層。"""
    return (Path(args.repo_root) if args.repo_root
            else Path(__file__).resolve().parent.parent.parent)


def main(argv=None):
    args = parse_args(argv)
    exit_code = 0

    if args.staged_handbook_sync:
        result = check_staged_handbook_sync(repo_root_of(args))
        print(render_selfcheck_text([result]))
        sys.exit(0 if result.passed else 1)

    if args.stamp_only_since:
        only, commits, offending = handbook_diff_is_stamp_only(
            repo_root_of(args), args.stamp_only_since
        )
        if only:
            print("\n".join(commits))
        else:
            print(f"手冊變更含戳記以外的內容：{offending}", file=sys.stderr)
        sys.exit(0 if only else 1)

    if args.selfcheck:
        root = repo_root_of(args)
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
