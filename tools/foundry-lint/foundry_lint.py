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
#   version-shape   規範與錯誤訊息拿舊形狀版本號舉例 → 讀者照做就錯（MYL-71）
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

# ── 版本號形狀（MYL-71，protocol `V4`／`V5`）──────────────────────────────
#: 只認手冊 tag 的**字面前綴**，不掃泛用的「v ＋數字」——後者會被工單編號、
#: 互動卡 slug、第三方 pin（`actions/checkout` 那類）整個淹沒，那是 MYL-41
#: 誤報「死連結」的同一個坑：掃得太寬的檢查，紅字會被習慣性忽略。
VERSION_TAG_PREFIX = "handbook-v"
#: 合法佔位符只有這一種寫法，其餘（單軸、帶算式的）都是 `V4` 之前的舊形狀。
VERSION_CANONICAL_PLACEHOLDER = "<a>.<b>.<c>.<d>"
#: 形狀一：字面數字，但位數不足四位。
#: `(?![\w.-])` 是為了**只抓真的位數不足的那些**——四碼合法字面會在讀到第四個
#: 分量前就被這個 lookahead 擋掉（回溯後每一種切法後面都還跟著 `.`），
#: 多一位或帶非數字後綴（`…0.0.0.x`、測試 tag 那種帶 `-` 的名字）同理不命中。
#: 這兩類不歸本檢查管：`V4` 違反段把它們明列為 `fnmatch` 的已知缺口，
#: adapter 也拿它們當反例講兩個平台的嚴格度差異——掃了只會誤殺說明文字。
VERSION_LITERAL_RE = re.compile(VERSION_TAG_PREFIX + r"(\d+(?:\.\d+){0,2})(?![\w.-])")
#: 形狀二：角括號佔位符。少了這一半就漏掉本檢查最該擋的兩處——規則本體自己的
#: 舊形狀舉例，與 `republish_decision()` 撞版本時吐給人看的錯誤訊息。
VERSION_PLACEHOLDER_RE = re.compile(
    VERSION_TAG_PREFIX + r"(<[^<>\n]*>(?:\.<[^<>\n]*>)*)"
)
#: 掃描範圍：規範、腳本、工具與手冊——「照著做會做錯」的那些。
VERSION_SCAN_ROOTS = ("skills", "scripts", "tools", "docs/handbook")
VERSION_SCAN_FILES = ("README.md", "CLAUDE.md", "AGENTS.md")
VERSION_SCAN_SUFFIXES = (".md", ".sh", ".py", ".yml", ".yaml")
#: 豁免清單。**顯式路徑，不用模式匹配**——這一格的風險方向是誤管而不是漏管
#: （protocol `V5`）：把反例測試、綁 sha 的發佈審查記錄與反悔錄「修正」成四碼，
#: 證據就對不上了，而且沒有人會發現，因為改完看起來更整齊。
#: 清單裡有幾條目前落在 `VERSION_SCAN_ROOTS` 之外、掃不到，仍然列著：
#: 會變的是掃描範圍，而範圍一放寬，第一個被改壞的就是它們。
VERSION_SHAPE_ALLOW = (
    "tools/publish-docs/test_site_docs.py",
    "tools/foundry-lint/test_foundry_lint.py",
    ".foundry/config.yml",
    "docs/publish-reviews",
    "docs/pilot",
    "docs/standards/known-drift.md",
    "docs/features",
)

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
#: 戳記行形狀：`> 最後對照 protocol \`<sha>\`（YYYY-MM-DD）`；sha 允許短碼（至少 7 碼）。
#: 寫成 blockquote 原意是在 mkdocs 上與正文區隔，實際上四章有三章的引言本身也是
#: blockquote，mkdocs 會把兩塊併成同一條豎線（known-drift `X4`，MYL-49 實測）。
#: MYL-44 判定不修——改形式的連動成本大於一條豎線的價值。要動這條正則前先讀 `X4`。
STAMP_RE = re.compile(
    r"^>\s*最後對照 protocol\s*`([0-9a-fA-F]{7,40})`\s*（(\d{4}-\d{2}-\d{2})）\s*$"
)


#: MYL-40 的「違反：⟨後果⟩ ＋ 標記」行，MYL-47 補上維護觸發點。
#: 標記只有兩個值，但**合法結尾有三種**——`§7 手冊版本 tag` 一節含 `V1`／`V2`／`V3`
#: 三條、機械後盾程度不同，單一違反段的誠實寫法就是併記。要它二選一得先把那節拆成
#: 三段違反行，那是改節結構、不是改標記。放行的是**字面完全相同**的三種，不是自由
#: 組合：一旦開放組合，標記就從「可判定的值」退化成散文，本檢查也就白寫了。
RULE_MARK_PREFIX = "**違反：**"
RULE_MARK_VALUES = ("機械", "自律")
RULE_MARK_ENDINGS = ("`【自律】`", "`【機械】`", "`【自律】`＋`【機械】`")
#: 標記本身的 token（含全形括號），用來抓「第三種值」——寫成 `【半機械】` 之類的東西。
RULE_MARK_TOKEN_RE = re.compile(r"【([^】]*)】")
#: 行尾**整串**標記（含中間的連接號），用來跟上面三種合法字面做全等比對。
#: 不能只用 `endswith`：`【機械】＋【自律】`（順序顛倒）的尾巴正好是合法的
#: `【自律】`，會被當成單一自律標記放行——而它讀起來剛好少掉機械那一半。
RULE_MARK_TAIL_RE = re.compile(r"(?:`【[^】]*】`[＋+、，,／/]?)+\s*$")


@dataclass
class SelfcheckResult:
    """單項自檢結果。`failures` 每一則都要能讓讀者直接知道去改哪裡。

    `skipped` 是 MYL-54 加的第三種姿態：本項**沒有實際檢查**（缺憑證、缺工具、
    刻意離線）。它不算失敗——CI 拿不到來源端憑證是常態，讓它紅等於逼所有人
    習慣性忽略紅字；但它**更不能算通過**：把「沒查」印成 ✅，讀者會以為鏡像
    已經對過帳。因此 `skipped` 有值時印 ⏭ 並在總結行另報跳過數，
    `passed` 仍然只看 `failures`（跳過不擋 commit）。
    """

    name: str
    summary: str
    failures: list = field(default_factory=list)
    skipped: str = ""

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
    """手冊章節檔與 `mkdocs.yml` 的 nav 必須一致，且全 repo 只有這一份手寫 nav。

    本項的形狀在 MYL-55 換過一次。原本比的是**三者**：磁碟章節數、`mkdocs.yml`、
    `scripts/publish-handbook.sh` 內嵌的第二份 heredoc mkdocs.yml——因為當時公開
    鏡像站真的另外維護一份 nav，只改一份就會讓公開站漏章（MYL-31 踩過）。

    精裝站搬回本 repo 之後那份 heredoc 不存在了：站台的 `mkdocs.yml` 由
    `tools/publish-docs/site_docs.py` **轉寫**私有這一份（wiki 側欄同樣是轉寫）。
    於是這一項要守的東西也跟著換：不再是「兩份要一致」，而是
    **「不准再出現第二份」**——所以下面除了比對磁碟與 nav，還掃 `scripts/` 與
    `.github/workflows/` 有沒有人又在腳本裡內嵌一份 nav。少了這道守衛，這項檢查
    會退化成「nav 對得上磁碟」，而漂移是從「有人另寫一份」開始的，不是從對不上開始的。
    """
    res = SelfcheckResult("nav-sync", "手冊章節與 nav 一致（且只有一份手寫 nav）")
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

    if in_mkdocs:
        for missing in sorted(on_disk - in_mkdocs):
            res.failures.append(
                f"mkdocs.yml 的 nav 沒有 {missing}"
                "——手冊有這一章但 nav 漏了，站台與 wiki 側欄都會看不到"
            )
        for extra in sorted(in_mkdocs - on_disk):
            res.failures.append(
                f"mkdocs.yml 的 nav 指向不存在的章節 {extra}——檔案已刪或改名，nav 沒跟上"
            )

    for rel in sorted(_nav_scan_targets(root)):
        text = read_text(root / rel)
        if "nav:" in text and CHAPTER_FILE_RE.search(text):
            res.failures.append(
                f"{rel} 裡出現第二份 nav（同時含 `nav:` 與手冊章節檔名）"
                "——投影用的 nav 一律轉寫 mkdocs.yml，不要再手寫一份"
                "（known-drift「兩份 nav 的結構性漂移」）"
            )

    res.summary += f"（章節 {len(on_disk)} 篇）"
    return res


def _nav_scan_targets(root: Path) -> list:
    """會被掃「有沒有內嵌第二份 nav」的檔案清單（repo 相對路徑）。"""
    targets = []
    for sub, pattern in (("scripts", "*.sh"), (".github/workflows", "*.yml")):
        base = root / sub
        if base.is_dir():
            targets.extend(p.relative_to(root) for p in base.rglob(pattern))
    return targets


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


def check_rule_marks(root: Path) -> SelfcheckResult:
    """protocol 每行「違反：」都要以合法的 `【機械】`／`【自律】` 標記收尾。

    MYL-40 為硬規則補了標記，但**標記本身沒有維護觸發點**：光是 MYL-40 審查
    期間 repo 就多了 `big-files`（MYL-42）與 `internal-links`（MYL-41）兩項
    機械檢查，而標記詞彙自己也漂過一次——`【自律】＋【機械】` 這個合併形是
    MYL-55（`1f1a2d7`）之後才出現的，比本檢查的原始規格還早。標記一旦過期，
    就從「據實記錄」變成「誤導」，正好是 MYL-40 想解決的問題的反面。

    只擋三個方向，都是機械判得準的：
      1. 有「違反：」行卻沒有標記收尾——增訂時漏標；
      2. 標記寫成合法三種以外的字面——例如 `【機械】＋【自律】`（順序顛倒）；
      3. 全檔出現第三種值——例如 `【半機械】`。

    **不擋**「哪些小節該有違反行」。哪一條規則值得配一段後果是編輯判斷（MYL-40
    盤了 20 條、其餘小節刻意留白），讓機械來管會逼出一堆為了過檢查而寫的廢話段。
    圖例節的措辭因此也不宣稱全覆蓋——見 protocol「怎麼讀規則末尾的標記」。

    標記只認**行尾**，不認「這行有沒有出現過這兩個詞」：`§7` 有兩段違反文在正文裡
    引用另一個標記（「從 `【自律】` 轉為機械攔截」），那是敘述不是標記，用 contains
    去判會把兩段都誤殺。
    """
    res = SelfcheckResult("rule-marks", "protocol 違反行的標記合法")
    protocol = root / PROTOCOL_REL
    if not protocol.exists():
        res.failures.append(f"{PROTOCOL_REL} 不存在——標記無從核對")
        return res

    text = read_text(protocol)
    section = ""
    marked = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        heading = HEADING_RE.match(line)
        if heading:
            section = heading.group(2)
        if not line.startswith(RULE_MARK_PREFIX):
            continue
        marked += 1
        tail = RULE_MARK_TAIL_RE.search(line.rstrip())
        where = f"{PROTOCOL_REL}:{lineno}（{section}）"
        legal = "、".join(RULE_MARK_ENDINGS)
        if tail is None:
            res.failures.append(
                f"{where}的「違反：」行沒有以標記收尾"
                "——每段後果都要講清楚這條**現在有沒有工具會擋**，"
                f"合法結尾只有：{legal}"
            )
        elif tail.group(0).strip() not in RULE_MARK_ENDINGS:
            res.failures.append(
                f"{where}的「違反：」行以「{tail.group(0).strip()}」收尾，不是合法字面"
                f"——合法結尾只有：{legal}（順序、連接號都要一模一樣）"
            )

    for value in sorted(set(RULE_MARK_TOKEN_RE.findall(text))):
        if value not in RULE_MARK_VALUES:
            res.failures.append(
                f"{PROTOCOL_REL} 出現第三種標記值 `【{value}】`"
                f"——標記只有 {'／'.join(f'`【{v}】`' for v in RULE_MARK_VALUES)} 兩個值，"
                "「有沒有工具會擋」沒有中間態；要記程度差異寫在後果散文裡"
            )

    # 圖例是讀者查標記含義的地方，它跟這裡的值域必須是同一份。
    # 對照 `big-files`：那邊也是拿程式常數去核散文裡的門檻數字。
    legend = text.split("## 1.")[0]
    for ending in RULE_MARK_ENDINGS:
        if ending not in legend:
            res.failures.append(
                f"protocol 開頭的標記圖例沒有列出合法結尾 {ending}"
                "——程式放行的形式圖例查不到，讀者會以為那是漂移"
            )
    res.summary += f"（{marked} 行違反段）"
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


def version_shape_allowed(rel: str) -> bool:
    """這個 repo 相對路徑是否落在豁免清單裡（目錄項涵蓋其下全部）。"""
    return any(rel == item or rel.startswith(item + "/") for item in VERSION_SHAPE_ALLOW)


def version_shape_targets(root: Path) -> list:
    """掃描範圍內所有該檢查的檔案，回傳 repo 相對路徑（POSIX 形式），已排序。"""
    found = set()
    for name in VERSION_SCAN_FILES:
        if (root / name).is_file():
            found.add(name)
    for top in VERSION_SCAN_ROOTS:
        base = root / top
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in VERSION_SCAN_SUFFIXES:
                found.add(path.relative_to(root).as_posix())
    return sorted(rel for rel in found if not version_shape_allowed(rel))


def check_version_shape(root: Path) -> SelfcheckResult:
    """提到手冊版本時一律用四碼形狀，佔位符只有一種合法寫法（protocol `V5`）。

    MYL-71：`V4` 把版本號改成四碼之後，repo 裡仍有九處沿用舊形狀舉例——
    其中兩處在**規則本體與錯誤訊息**上：`V3` 的內文拿舊形狀說明「不重打」，
    而 `republish_decision()` 撞版本時叫人去打下一版的那句話也是舊形狀。
    後者出現的時機正是有人要決定下一個版本號的當下，規範與錯誤訊息示範錯的
    形狀，讀者照做就錯——這是本檢查存在的主因，不是為了整齊。

    刻意只擋兩種形狀（字面位數不足、非標準佔位符），且只在
    `VERSION_TAG_PREFIX` 這個字面前綴後面判。不管的兩類寫在
    `VERSION_LITERAL_RE` 的註解裡，豁免清單的理由寫在 `VERSION_SHAPE_ALLOW`。
    反例見 `test_foundry_lint.py` 的 `VersionShapeTest`——兩種形狀各一個。
    """
    res = SelfcheckResult("version-shape", "手冊版本號用四碼形狀")
    targets = version_shape_targets(root)
    for rel in targets:
        for lineno, line in enumerate(read_text(root / rel).splitlines(), 1):
            for m in VERSION_LITERAL_RE.finditer(line):
                digits = m.group(1).count(".") + 1
                res.failures.append(
                    f"{rel}:{lineno} 用了 `{VERSION_TAG_PREFIX}{m.group(1)}`"
                    f"（{digits} 位）——手冊版本號是四位十進位整數，"
                    "形狀與遞增規則見 protocol `V4`，適用範圍見 `V5`"
                )
            for m in VERSION_PLACEHOLDER_RE.finditer(line):
                if m.group(1) == VERSION_CANONICAL_PLACEHOLDER:
                    continue
                res.failures.append(
                    f"{rel}:{lineno} 的佔位符寫成 `{VERSION_TAG_PREFIX}{m.group(1)}`"
                    f"——合法寫法只有 `{VERSION_TAG_PREFIX}"
                    f"{VERSION_CANONICAL_PLACEHOLDER}`（protocol `V4`／`V5`）"
                )
    res.summary += f"（掃 {len(targets)} 份檔案）"
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


#: `table-shape` 的掃描範圍（MYL-76 AC9）。`docs/features/` 也掃——那裡的表格
#: 一樣會被切斷，而它是交付物；`big-files` 排除它是因為那項管的是 context 預算，理由不同。
TABLE_SCAN_DIRS = ("docs", "skills")
#: markdown 表格的分隔列（`| --- | --- |`）。前後空白由呼叫端 `strip()` 掉。
TABLE_SEP_RE = re.compile(r"^\|(?:\s*:?-{2,}:?\s*\|)+$")


def is_table_row(line: str) -> bool:
    """這一行渲染時會被當成表格列（縮排在清單裡的表格也算）。"""
    return line.lstrip().startswith("|")


def table_breaks(text: str) -> list:
    """回傳「被空行截斷的表格續列」行號（1-based）。

    markdown 的表格在第一個空行處結束。所以表頭＋分隔列之後夾了一行空白，
    再接 `|` 開頭的列時，那些列**不會**被渲染成表格的一部分——它們變成普通段落，
    連同分隔符一起原樣印出來。MYL-73 就踩到：`known-drift` 的 `L23` 被一行既有
    空行切在表外，而當時 10 項自檢全綠、`make check` 也過，沒有任何一項在驗這件事。

    只報「續列」不報「新表」：空行之後那一段如果自己帶分隔列，就是兩張相鄰的表，
    合法。判準放在這裡而不是靠人眼，理由與本檢查存在的理由相同。
    """
    lines = text.splitlines()
    breaks = []
    in_fence = False
    i = 0
    while i < len(lines):
        if FENCE_RE.match(lines[i]):
            in_fence = not in_fence
            i += 1
            continue
        # 表頭單獨一行不算表格，要下一行是分隔列才算——少了這道，
        # 任何以 `|` 開頭的段落都會被誤判成表。
        if (in_fence or not is_table_row(lines[i])
                or i + 1 >= len(lines) or not TABLE_SEP_RE.match(lines[i + 1].strip())):
            i += 1
            continue
        end = i + 2
        while end < len(lines) and is_table_row(lines[end]):
            end += 1
        nxt = end
        while nxt < len(lines) and not lines[nxt].strip():
            nxt += 1
        starts_new_table = (nxt + 1 < len(lines)
                            and TABLE_SEP_RE.match(lines[nxt + 1].strip()))
        if nxt > end and nxt < len(lines) and is_table_row(lines[nxt]) and not starts_new_table:
            breaks.append(nxt + 1)
            i = nxt
            continue
        i = end
    return breaks


def check_table_shape(root: Path) -> SelfcheckResult:
    """markdown 表格中間不得夾空行——夾了會被切斷，而機械斷言看不見（MYL-76 AC9）。

    這一項與 `L13`／`L21`／`X4` 同族：**斷言全綠但渲染是壞的**。差別在於前三者
    是外部平台的行為，這一條是 markdown 自己的，所以擋得住，也就該擋。
    """
    res = SelfcheckResult("table-shape", "markdown 表格沒有被空行切斷")
    scanned = 0
    for top in TABLE_SCAN_DIRS:
        base = root / top
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            scanned += 1
            rel = path.relative_to(root).as_posix()
            for lineno in table_breaks(read_text(path)):
                res.failures.append(
                    f"{rel}:{lineno} 是上面那張表的續列，但中間隔了空行"
                    "——渲染時表格在空行處就結束了，這一行起會變成普通段落，"
                    "連分隔符一起原樣印出來。刪掉那個空行；真要分成兩張表，"
                    "就給下面這段補上自己的表頭與分隔列"
                )
    res.summary += f"（掃 {scanned} 份）"
    return res


# ── `org-sync`：組織宣告 ↔ protocol 第 9／8 節（MYL-76）────────────────────
ORG_REL = ".foundry/org.yml"
#: 本檢查認得的 `foundry_org` 版本。改 schema 形狀時一起改，讓舊檔停下報錯而不是被誤讀。
ORG_SCHEMA_VERSION = "1"
#: `model_tier` 的值 → protocol 第 8 節「三層預設」表第一欄的字面。
ORG_MODEL_TIERS = {"high": "高", "medium": "中", "low": "低"}
#: `permissions[]` 的封閉值域（Foundry 級名稱；落到各平台哪個欄位見 config-schema）。
ORG_PERMISSIONS = ("assign_tasks", "create_agents", "create_skills")
#: 第 9 節組織圖的樹根，以及 `reports_to` 裡代表它的值。
ORG_TREE_ROOT = "使用者"
ORG_ROOT_REPORTS_TO = "user"
ORG_TREE_HEADING = "現行結構"
ORG_TIER_HEADING = "三層預設"
#: 第 8 節分層表用簡稱寫某個角色時的補充比對名（第 9 節寫 `QA Engineer`、第 8 節寫 `QA`）。
#: 這是**放寬**不是改寫：全名與簡稱都算命中，所以 protocol 日後統一成全名也不會誤報。
#: 要加第二則之前先想清楚——別名一多，本檢查就從「三處一致」退化成「大致像」。
ORG_TIER_ALIASES = {"qa-engineer": ("QA",)}
#: 組織圖每一層的縮排寬度（`└── ` 四格）。
ORG_TREE_INDENT = 4
ORG_TREE_LINE_RE = re.compile(r"^(?P<prefix>[ │├└─]*)(?P<label>\S.*?)\s*$")
ORG_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def parse_org(text: str) -> dict:
    """把 `.foundry/org.yml` 讀成 dict。**刻意只支援本檔用得到的子集**。

    支援：頂層 `鍵: 純量`、`roles:` 底下的映射序列、角色欄位的純量與純量序列、
    `#` 註解、值兩側的引號。不支援的寫法**拋 `LintError` 而不是忽略**——這一點
    與 `parse_config` 相反，理由是用途不同：那個 parser 只從一份大設定檔裡挑幾個
    已知欄位出來，本檔則整份都是本檢查的輸入，靜靜漏掉一行等於漏檢一個角色。

    不用 PyYAML 的理由同 `parse_config`：foundry-lint 只用標準函式庫。
    """
    data: dict = {}
    roles: list = []
    role = None
    seq_key = None
    seq_indent = 0
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        where = f"{ORG_REL}:{lineno}"
        if body.startswith("- "):
            item = body[2:].strip()
            if seq_key is not None and indent > seq_indent:
                role[seq_key].append(item.strip("'\""))
                continue
            if ":" not in item:
                raise LintError(f"{where} 不支援的寫法 `{body}`：序列項不在任何欄位底下")
            role = {}
            roles.append(role)
            seq_key = None
            key, _, value = item.partition(":")
            role[key.strip()] = value.strip().strip("'\"")
            continue
        if ":" not in body:
            raise LintError(f"{where} 不支援的寫法 `{body}`：本 parser 只吃 `鍵: 值`")
        key, _, value = body.partition(":")
        key, value = key.strip(), value.strip().strip("'\"")
        seq_key = None
        if indent == 0:
            role = None
            if key == "roles":
                data["roles"] = roles
            elif value:
                data[key] = value
            else:
                raise LintError(f"{where} 頂層的 `{key}` 沒有值，而本 parser 只認得 `roles` 一個巢狀鍵")
            continue
        if role is None:
            raise LintError(f"{where} `{key}` 不在任何 role 底下")
        if value and value != "[]":
            role[key] = value
        else:
            role[key] = []
            seq_key, seq_indent = key, indent
    return data


def section_lines(text: str, heading: str) -> list:
    """取某個標題底下、到下一個同級或更上層標題為止的行（含空行，供表格／圍欄解析）。"""
    lines = text.splitlines()
    start = level = None
    for idx, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if not m:
            continue
        if start is None:
            if heading in m.group(2):
                start, level = idx + 1, len(m.group(1))
            continue
        if len(m.group(1)) <= level:
            return lines[start:idx]
    return lines[start:] if start is not None else []


def parse_org_tree(protocol_text: str) -> tuple:
    """protocol 第 9 節組織圖 → `(樹根, {節點: 上一層節點})`。樹根不在字典裡。"""
    block: list = []
    in_fence = False
    for line in section_lines(protocol_text, ORG_TREE_HEADING):
        if FENCE_RE.match(line):
            if in_fence:
                break
            in_fence = True
            continue
        if in_fence:
            block.append(line)
    parents: dict = {}
    stack: dict = {}
    root = ""
    for raw in block:
        if not raw.strip():
            continue
        m = ORG_TREE_LINE_RE.match(raw)
        if not m:
            continue
        depth = len(m.group("prefix")) // ORG_TREE_INDENT
        # 節點名後面的「（需求）」是說明，不是名字的一部分。
        label = m.group("label").split("（")[0].strip()
        stack[depth] = label
        if depth == 0:
            root = root or label
        else:
            parents[label] = stack.get(depth - 1, "")
    return root, parents


def parse_tier_table(protocol_text: str) -> dict:
    """protocol 第 8 節「三層預設」表 → `{層級字面: 預設適用欄的文字}`。"""
    tiers: dict = {}
    for line in section_lines(protocol_text, ORG_TIER_HEADING):
        stripped = line.strip()
        if not stripped.startswith("|") or TABLE_SEP_RE.match(stripped):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) >= 3:
            tiers.setdefault(cells[0], cells[-1])
    return tiers


def check_org_sync(root: Path) -> SelfcheckResult:
    """`.foundry/org.yml` 要與 protocol 第 9 節組織圖、第 8 節分層表三處一致。

    **本檢查刻意不比對平台實況**（MYL-76 AC7）。`org.yml` 是規則層的**應然**宣告，
    不是平台狀態的鏡子：AC2 要照定案組織填出 9 名，而 PM 的 agent 要到 MYL-79（T7）
    才真的被建出來，中間隔著幾張單——那段期間本檔宣告一個平台上還不存在的成員，
    是預期行為。**下一個看到這裡的人請不要「補上」一個比對平台的檢查**，
    那會在整段期間誤報；與平台實況的對帳歸 T7。

    `ai_platform` 的枚舉合法性歸 config-schema，本檢查只驗兩份設定檔講的是同一件事——
    在程式裡另養一份枚舉，就是再造一個會漂的來源。
    """
    res = SelfcheckResult("org-sync", "組織宣告與 protocol 第 9／8 節一致")
    path = root / ORG_REL
    if not path.exists():
        res.failures.append(
            f"{ORG_REL} 不存在——組織層宣告是可攜性的一部分，缺了它，"
            "導入新專案跑完只會得到看板與關卡設定，然後沒有任何一個 agent"
        )
        return res
    try:
        org = parse_org(read_text(path))
    except LintError as exc:
        res.failures.append(str(exc))
        return res

    version = org.get("foundry_org")
    if version != ORG_SCHEMA_VERSION:
        res.failures.append(
            f"{ORG_REL} 的 `foundry_org` 是 {version!r}，本檢查只認得 {ORG_SCHEMA_VERSION!r}"
            "——版本不合時停下報錯，不猜著解析（同 config.yml 的 `foundry`）"
        )
        return res

    roles = org.get("roles") or []
    if not roles:
        res.failures.append(f"{ORG_REL} 沒有任何 `roles` 項目")
        return res

    protocol = root / PROTOCOL_REL
    if not protocol.exists():
        res.failures.append(f"{PROTOCOL_REL} 不存在——比對基準缺席，本項無從判定")
        return res
    protocol_text = read_text(protocol)

    # ── 逐角色的形狀 ────────────────────────────────────────────────────
    seen_ids: set = set()
    by_id: dict = {}
    for idx, role in enumerate(roles, 1):
        rid = role.get("id", "")
        label = rid or f"第 {idx} 項"
        if not isinstance(rid, str) or not ORG_ID_RE.match(rid or ""):
            res.failures.append(f"{ORG_REL} {label} 的 `id` 缺席或形狀不合（要 `[a-z][a-z0-9-]*`）")
            continue
        if rid in seen_ids:
            res.failures.append(f"{ORG_REL} 的角色 id `{rid}` 重複")
            continue
        seen_ids.add(rid)
        by_id[rid] = role
        for field_name in ("title", "reports_to", "model_tier"):
            if not role.get(field_name):
                res.failures.append(f"{ORG_REL} `{rid}` 缺必填欄位 `{field_name}`")
        tier = role.get("model_tier")
        if tier and tier not in ORG_MODEL_TIERS:
            res.failures.append(
                f"{ORG_REL} `{rid}` 的 `model_tier` 是 `{tier}`，"
                f"值域是 {'｜'.join(ORG_MODEL_TIERS)}"
            )
        skills = role.get("skills")
        if not isinstance(skills, list) or not skills:
            res.failures.append(f"{ORG_REL} `{rid}` 的 `skills` 缺席或是空的——每個角色至少掛一份")
        else:
            for rel in skills:
                if not (root / rel).exists():
                    res.failures.append(
                        f"{ORG_REL} `{rid}` 掛的 `{rel}` 不存在——skill 改名或搬走了，宣告沒跟上"
                    )
        perms = role.get("permissions")
        if not isinstance(perms, list):
            res.failures.append(f"{ORG_REL} `{rid}` 缺 `permissions`（沒有要授權的權限就寫 `[]`）")
        else:
            for perm in perms:
                if perm not in ORG_PERMISSIONS:
                    res.failures.append(
                        f"{ORG_REL} `{rid}` 的 `permissions` 有 `{perm}`，"
                        f"值域是 {'｜'.join(ORG_PERMISSIONS)}"
                    )

    # ── 對第 9 節組織圖 ─────────────────────────────────────────────────
    tree_root, parents = parse_org_tree(protocol_text)
    if tree_root != ORG_TREE_ROOT or not parents:
        res.failures.append(
            f"讀不出 {PROTOCOL_REL} 第 9 節「{ORG_TREE_HEADING}」的組織圖"
            f"（樹根讀成 {tree_root!r}）——圖的形狀變了就要一起改本檢查，不要讓它靜靜失效"
        )
        return res

    titles = {role.get("title"): rid for rid, role in by_id.items() if role.get("title")}
    if len(titles) != len(by_id):
        res.failures.append(f"{ORG_REL} 有重複的 `title`——組織圖靠它對接，不能重複")
    for title in sorted(set(titles) - set(parents)):
        res.failures.append(
            f"{ORG_REL} 宣告了 `{title}`，但 protocol 第 9 節組織圖沒有這個節點"
            "——先改規範再改宣告（結構調整依第 9 節走使用者裁定）"
        )
    for node in sorted(set(parents) - set(titles)):
        res.failures.append(
            f"protocol 第 9 節組織圖有 `{node}`，但 {ORG_REL} 沒有宣告它"
            "——組織圖是權威來源，宣告漏了就等於 T5 建不出這個角色"
        )
    for rid, role in sorted(by_id.items()):
        title = role.get("title")
        if title not in parents:
            continue
        declared = role.get("reports_to")
        expected_parent = parents[title]
        if declared == ORG_ROOT_REPORTS_TO:
            actual_parent = ORG_TREE_ROOT
        elif declared in by_id:
            actual_parent = by_id[declared].get("title")
        else:
            res.failures.append(
                f"{ORG_REL} `{rid}` 的 `reports_to` 是 `{declared}`，"
                f"既不是本檔的角色 id 也不是 `{ORG_ROOT_REPORTS_TO}`"
            )
            continue
        if actual_parent != expected_parent:
            res.failures.append(
                f"{ORG_REL} `{rid}` 宣告匯報給 `{actual_parent}`，"
                f"但 protocol 第 9 節組織圖把 `{title}` 掛在 `{expected_parent}` 底下"
            )

    # ── 對第 8 節分層表 ─────────────────────────────────────────────────
    tiers = parse_tier_table(protocol_text)
    missing_rows = [zh for zh in ORG_MODEL_TIERS.values() if zh not in tiers]
    if missing_rows:
        res.failures.append(
            f"protocol 第 8 節「{ORG_TIER_HEADING}」表讀不到 {'、'.join(missing_rows)} 這幾層"
            "——表的形狀變了就要一起改本檢查"
        )
        return res
    for rid, role in sorted(by_id.items()):
        tier = role.get("model_tier")
        if tier not in ORG_MODEL_TIERS:
            continue
        names = (role.get("title", ""),) + ORG_TIER_ALIASES.get(rid, ())
        hits = [zh for zh, cell in tiers.items()
                if zh in ORG_MODEL_TIERS.values() and any(n and n in cell for n in names)]
        if not hits:
            res.failures.append(
                f"protocol 第 8 節分層表三層都沒提到 `{role.get('title')}`，"
                f"但 {ORG_REL} 宣告它是 `{tier}` 層——分層表漏了一個角色，或名字寫得對不上"
            )
        elif len(hits) > 1:
            res.failures.append(
                f"protocol 第 8 節分層表有 {len(hits)} 層（{'、'.join(hits)}）都提到 "
                f"`{role.get('title')}`——一個角色只能有一個預設層"
            )
        elif hits[0] != ORG_MODEL_TIERS[tier]:
            res.failures.append(
                f"{ORG_REL} `{rid}` 宣告 `{tier}`（＝{ORG_MODEL_TIERS[tier]}層），"
                f"但 protocol 第 8 節把它列在{hits[0]}層"
            )

    # ── 對 config.yml 的 `ai_platform` ──────────────────────────────────
    declared_ai = org.get("ai_platform")
    config_ai = read_config(root).get("ai_platform")
    if not declared_ai:
        res.failures.append(
            f"{ORG_REL} 缺 `ai_platform`——這份組織宣告在哪個軸 A 平台上實現要顯式寫出來"
        )
    elif config_ai and config_ai != declared_ai:
        res.failures.append(
            f"{ORG_REL} 的 `ai_platform` 是 `{declared_ai}`，"
            f"但 {CONFIG_REL} 寫 `{config_ai}`——同一件事寫了兩個值"
        )

    res.summary += f"（{len(by_id)} 名）"
    return res


# git 在 hook 裡會匯出這幾個「指向哪個 repo」的變數，而它們的優先序高於 `-C`。
# 從**一般 checkout** commit 時它們是相對路徑（`GIT_INDEX_FILE=.git/index`、
# 沒有 `GIT_DIR`），`-C` 照常生效；從 **worktree** commit 時兩者都是絕對路徑，
# 於是 `git -C <別的目錄>` 會被悄悄導回外層 repo——查的對象整個換掉而且不報錯。
# `git_run` 的契約是「對 root 跑 git」，所以這裡清掉它們，讓 `-C` 說了算。
# 清掉 `GIT_INDEX_FILE` 是安全的：git 會改用 `-C` 找到的那個 git dir 底下的
# `index`，跟被清掉的那個變數指的是同一個檔案（兩種形狀都實測過）。
GIT_LOCATION_ENV = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_PREFIX", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


def git_env() -> dict:
    """去掉會蓋過 `-C` 的 git 環境變數；測試也用這份，免得兩邊各清各的。"""
    return {k: v for k, v in os.environ.items() if k not in GIT_LOCATION_ENV}


def git_run(root: Path, *args) -> tuple:
    """跑 git，回傳 `(ok, stdout)`；git 不存在或不是 repo 時 `ok` 為 False。

    自檢會在沒有 `.git` 的環境跑（單元測試把 repo 複製出來時就刻意不帶），
    所以「拿不到 git」是正常狀況而不是錯誤——那時只驗戳記的字面合法性，
    落後與否留給有 git 的地方（`make check`／CI／pre-commit）判。
    """
    try:
        proc = subprocess.run(
            ("git", "-C", str(root)) + args,
            capture_output=True, text=True, check=False, env=git_env(),
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

    ⚠️ **覆蓋範圍是「有動到手冊任一檔」，不是「動到對應章」——這是已知且刻意的**
    （MYL-76 AC10 判定，記在 `docs/standards/known-drift.md` `GAP-6`）。
    `unsynced_protocol_commits()` 只看 `diff-tree ... -- docs/handbook` 有沒有輸出，
    所以「改了 protocol 第 3 節、手冊只動 `06` 章、`03` 章戳記照樣停在舊 sha」會全綠
    （MYL-73 的 `0a0b461` 就是這個形狀）。**不要補一張 protocol 節 → 手冊章的對應表**：
    兩者不是一對一，硬做會變成第二份需要人工維護的映射，而那正是本 repo 反覆記錄的
    漂移來源——這道閘門要擋的是「完全沒看手冊」，判斷「哪一章要改」本來就在層 2 的
    agent 身上（見上方三層設計）。
    """
    res = SelfcheckResult("handbook-stamp", "手冊四章戳記不落後於 protocol")
    has_git, _ = git_run(root, "rev-parse", "--verify", "HEAD")
    # 淺 clone 是「有 git 但沒有歷史」——戳記 sha 一律解不出來，於是四章一起偽裝成
    # 「戳記寫錯了」。那個訊息把人指向手冊，真正該改的卻是 checkout 的 fetch-depth
    # （MYL-44 D1：main 連四顆 commit 的 CI 全紅，排查繞了三個 run）。這裡擋一次並
    # 說出真正的處置。**不是靜靜略過**——略過等於閘門在淺 clone 下無聲失效。
    _, shallow = git_run(root, "rev-parse", "--is-shallow-repository")
    is_shallow = has_git and shallow == "true"
    if is_shallow:
        res.failures.append(
            "這是淺 clone（`--depth`），戳記指到的歷史 commit 解不出來，落後與否"
            "驗不了——CI 把 checkout 的 `fetch-depth` 設成 `0`，本機用完整 clone。"
            "（戳記的字面格式仍照驗）"
        )
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
        if not has_git or is_shallow:
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
        content = line[1:]
        # 空白行一併放行：戳記的錨點形狀是「標題／空行／戳記／空行／既有引言」，
        # 首次掛上時必然連帶新增一個空行。空行不帶進任何可見內容，放行它不開洞
        # ——真要夾帶東西，那幾行帶著文字，落不進這個條件。
        if content.strip() and not STAMP_RE.match(content):
            offending = line
            break
    _, log = git_run(root, "log", "--format=%h %s", f"{base_sha}..HEAD",
                     "--", HANDBOOK_REL)
    return (not offending), (log.splitlines() if log else []), offending


# ══════════════════ 工單鏡像對帳（MYL-54） ══════════════════
#
# 規格：`skills/foundry-platform/adapters/github.md`「鏡像模式 → 對帳」。
# 分工：**同步本身是【自律】**（agent 建單／改狀態／結案時自己要做），
#       **本檢查是【機械】兜底**——但它是**延遲偵測，不是即時防護**：
#       只在 `make check`／pre-commit／CI 跑，而工單狀態變動不一定伴隨 commit，
#       所以漏同步會等到「下一次有人 commit」才被抓到。
#
# 而且在 CI 上它**一定是跳過的**——CI 沒有來源端憑證。真正跑得到完整對帳的
# 只有同時握有 `gh` 登入與 `PAPERCLIP_API_KEY` 的本機 `make check`。
# 這不是缺陷，是這個檢查能力的實際邊界；寫在這裡是為了不讓人高估它。

#: 鏡像 issue body 首行的對應標記。經網頁編輯過的 body 行尾可能是 CRLF，先剝 `\r`。
MIRROR_MARK_RE = re.compile(r"^Foundry-Source: ([a-z-]+)/(\S+)$")
#: 來源工單上的「這張刻意不鏡像」聲明。有這行就不算漏建。
MIRROR_SKIPPED_RE = re.compile(r"^Mirror-skipped:\s*\S", re.MULTILINE)
#: 六態 → GitHub project 的 Status 選項名（adapter `update_status` 的同一張表）。
SIX_STATE_TO_GH_STATUS = {
    "todo": "Todo", "in_progress": "In Progress", "in_review": "In Review",
    "blocked": "Blocked", "done": "Done", "cancelled": "Cancelled",
}
#: 來源端為這兩態時鏡像 issue 應為關閉，其餘應為開啟。
MIRROR_CLOSED_STATES = frozenset({"done", "cancelled"})
#: `gh issue list` 的單次上限。撈到剛好等於上限就當作可能截斷並報紅——
#: 截斷過的對帳會把漏建報成「全過」，比不對帳更危險。
MIRROR_LIST_LIMIT = 500
#: 工單編號形狀 `<前綴>-<序號>`，用來與 `mirror_since` 比大小。
ISSUE_REF_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*)-(\d+)$")
#: 設了就整項跳過（測試與離線環境用）。跳過印 ⏭ 不印 ✅，見 `SelfcheckResult`。
MIRROR_OFFLINE_ENV = "FOUNDRY_LINT_OFFLINE"

CONFIG_REL = ".foundry/config.yml"


@dataclass(frozen=True)
class SourceIssue:
    """來源端（真相端）的一張工單。"""

    ref: str            # 例 `MYL-54`
    status: str         # 六態之一；不在表上時對帳報紅而不是自行推導對照
    mirror_skipped: bool = False


@dataclass(frozen=True)
class MirrorIssue:
    """鏡像端的一張 issue（**已確認帶對應標記**；沒標記的不進來，見下）。"""

    number: int
    source_platform: str
    ref: str
    state: str          # `open` / `closed`
    status: str = ""    # project 的 Status 選項名；空字串＝沒掛進 project


def parse_config(text: str) -> dict:
    """把 `.foundry/config.yml` 讀成巢狀 dict。**刻意只支援本檔用得到的子集**。

    支援：`鍵: 純量`、`鍵:`（開一層巢狀）、`#` 註解、值兩側的引號。
    不支援：陣列、多行字串、錨點、流式寫法。踩到不支援的寫法時該鍵被忽略，
    而不是拋例外——這個 parser 的用途只有「取出幾個已知欄位」，不是驗整份設定檔。

    為什麼不用 PyYAML：`.github/workflows/foundry-lint.yml` 明寫 foundry-lint
    只用標準函式庫，讓閘門在任何環境都跑得起來。為了讀三個欄位引入依賴，
    等於拿掉那個保證。
    """
    root: dict = {}
    stack = [(-1, root)]
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if ":" not in line:
            continue
        key, _, value = line.strip().partition(":")
        key, value = key.strip(), value.strip().strip("'\"")
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            stack = [(-1, root)]
        parent = stack[-1][1]
        if value:
            parent[key] = value
        else:
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
    return root


def read_config(root: Path) -> dict:
    path = root / CONFIG_REL
    return parse_config(read_text(path)) if path.exists() else {}


def parse_mirror_marker(body: str):
    """從鏡像 issue 的 body 首行取 `(來源平台, issue_ref)`；沒有標記回 `None`。

    `body` 為 `None`（空內文的 issue，API 回的就是 null）時視同沒有標記——
    這是 adapter 的對帳指令特地寫兩層 `// ""` 要擋的那個中斷點。
    """
    first = (body or "").split("\n", 1)[0].rstrip("\r")
    m = MIRROR_MARK_RE.match(first)
    return (m.group(1), m.group(2)) if m else None


def ref_sort_key(ref: str):
    """`MYL-54` → `('MYL', 54)`；形狀不符回 `None`（無從比大小）。"""
    m = ISSUE_REF_RE.match(ref)
    return (m.group(1).upper(), int(m.group(2))) if m else None


def in_mirror_scope(ref: str, since: str) -> bool:
    """`ref` 是否落在鏡像範圍內（`since` 起、含 `since` 本身）。

    `since` 是 MYL-54 的界線：本單只鏡像**新單**，既有舊單的回填屬批次對外
    動作、要另外核可。沒有這條界線，對帳一啟用就會把 50 幾張舊單全報成漏建，
    於是整項檢查在第一天就被當成雜訊關掉。
    """
    if not since:
        return True
    a, b = ref_sort_key(ref), ref_sort_key(since)
    if a is None or b is None or a[0] != b[0]:
        return True     # 比不出大小時一律納入：寧可誤報，不要漏報
    return a[1] >= b[1]


def reconcile_mirror(sources: list, mirrors: list, source_platform: str) -> list:
    """純函式對帳：比對單號、狀態、開關狀態，回傳 failure 訊息清單。

    三種紅燈都**只回報、不自動修**（見 adapter「對帳」節）：漏建、孤兒、一對多。
    修法牽涉建單或關單，那是對外動作（`G-C`），對帳自己不動手。
    """
    failures = []
    by_ref: dict = {}
    for m in mirrors:
        by_ref.setdefault(m.ref, []).append(m)

    source_refs = {s.ref for s in sources}

    for ref, group in sorted(by_ref.items()):
        if len(group) > 1:
            nums = "、".join(f"#{m.number}" for m in sorted(group, key=lambda x: x.number))
            failures.append(
                f"一對多：`{ref}` 對到 {len(group)} 張鏡像 issue（{nums}）"
                "——關掉多餘的那張屬對外動作，要使用者核可，對帳不自己動手"
            )
        if ref not in source_refs:
            failures.append(
                f"孤兒：鏡像 issue #{group[0].number} 的標記指到 `{ref}`，"
                "來源端沒有這張單——來源單被刪或標記打錯"
            )

    for s in sorted(sources, key=lambda x: ref_sort_key(x.ref) or (x.ref, 0)):
        group = by_ref.get(s.ref, [])
        if not group:
            if not s.mirror_skipped:
                failures.append(
                    f"漏建：來源端 `{s.ref}` 在鏡像端找不到對應標記，"
                    "且來源工單沒有 `Mirror-skipped:` 留言"
                )
            continue
        m = min(group, key=lambda x: x.number)

        if m.source_platform != source_platform:
            failures.append(
                f"`{s.ref}`：鏡像 issue #{m.number} 的標記寫的來源平台是 "
                f"`{m.source_platform}`，設定檔的 `devtools_platform` 是 `{source_platform}`"
            )

        expected_status = SIX_STATE_TO_GH_STATUS.get(s.status)
        if expected_status is None:
            failures.append(
                f"`{s.ref}`：來源端狀態 `{s.status}` 不在六態對照表上，無從換算 "
                "Status——要嘛補 adapter 的對照表（經核可），要嘛把這張單改回六態；"
                "**不得在這裡自行推導一個對應**"
            )
        elif not m.status:
            failures.append(
                f"`{s.ref}`：鏡像 issue #{m.number} 沒有掛進 project（讀不到 Status），"
                f"來源端是 `{s.status}`——建單時漏了 `gh project item-add`"
            )
        elif m.status != expected_status:
            failures.append(
                f"`{s.ref}`：狀態不同步——來源端 `{s.status}`（應為 "
                f"`{expected_status}`），鏡像端 Status 是 `{m.status}`"
            )

        expected_state = "closed" if s.status in MIRROR_CLOSED_STATES else "open"
        if m.state != expected_state:
            failures.append(
                f"`{s.ref}`：開關狀態不同步——來源端 `{s.status}`（應為 "
                f"{expected_state}），鏡像 issue #{m.number} 是 {m.state}"
            )
    return failures


def gh_json(root: Path, *args):
    """跑 `gh` 並解析 JSON 輸出；失敗回 `(None, 原因)`。

    失敗一律當「查不到」而不是「不同步」：`gh` 沒裝、沒登入、網路不通都不是
    鏡像漂移，報成紅燈只會讓人學會忽略這一項。
    """
    try:
        proc = subprocess.run(("gh",) + args, capture_output=True, text=True,
                              check=False, cwd=str(root))
    except OSError:
        return None, "`gh` CLI 不在 PATH 上"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        return None, f"`gh {' '.join(args[:2])}` 失敗：{detail[0] if detail else '未知錯誤'}"
    try:
        return json.loads(proc.stdout or "null"), ""
    except json.JSONDecodeError:
        return None, f"`gh {' '.join(args[:2])}` 的輸出不是 JSON"


def fetch_mirror_issues(root: Path, project_title: str, project_owner: str):
    """撈鏡像端。回傳 `(issues, 跳過原因)`——原因非空時 `issues` 不可用。

    **沒有對應標記的 issue 不進結果**：那是人手開的，不歸鏡像管，
    當成孤兒清掉會誤傷。

    截斷旗標**兩份清單都要看**：issue 清單決定有哪些鏡像單，看板項目清單決定
    它們的 Status。後者被截斷時查不到的 Status 會變成空字串，於是每一張都報成
    「狀態不同步」——紅燈方向是安全的，但理由是錯的，讀者會去追一個不存在的漂移。
    """
    raw, why = gh_json(root, "issue", "list", "--state", "all",
                       "--limit", str(MIRROR_LIST_LIMIT),
                       "--json", "number,state,body")
    if raw is None:
        return None, why
    truncated = len(raw) >= MIRROR_LIST_LIMIT

    projects, why = gh_json(root, "project", "list", "--owner", project_owner,
                            "--format", "json")
    if projects is None:
        return None, why
    number = next((p["number"] for p in projects.get("projects", [])
                   if p.get("title") == project_title), None)
    if number is None:
        return None, f"找不到標題為 `{project_title}` 的 project（owner `{project_owner}`）"

    items, why = gh_json(root, "project", "item-list", str(number),
                         "--owner", project_owner, "--format", "json",
                         "--limit", str(MIRROR_LIST_LIMIT))
    if items is None:
        return None, why
    truncated = truncated or len(items.get("items", [])) >= MIRROR_LIST_LIMIT
    status_by_number = {
        it["content"]["number"]: it.get("status") or ""
        for it in items.get("items", [])
        if isinstance(it.get("content"), dict) and "number" in it["content"]
    }

    issues = []
    for it in raw:
        mark = parse_mirror_marker(it.get("body"))
        if mark is None:
            continue
        issues.append(MirrorIssue(
            number=it["number"], source_platform=mark[0], ref=mark[1],
            state=str(it.get("state", "")).lower(),
            status=status_by_number.get(it["number"], ""),
        ))
    return (issues, truncated), ""


def api_get(base: str, path: str, token: str):
    """Paperclip API 的 GET。回傳 `(資料, 錯誤訊息)`。"""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"{base}{path}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), ""
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as e:
        return None, f"`GET {path}` 失敗：{e}"


def fetch_source_issues(base: str, token: str, company_id: str, project_id: str,
                        since: str, mirrored_refs: set):
    """撈來源端。`mirrored_refs` 用來省下留言查詢：只有看起來漏建的才去翻留言。

    翻留言是為了找 `Mirror-skipped:`。對每張單都翻等於 N 次 API 呼叫，
    而絕大多數單都對得上——只查對不上的那幾張。

    來源端**沒有分頁**：`GET /api/companies/{id}/issues` 在 openapi 上只吃
    `companyId` 與 `view` 兩個參數，一次回全部（2026-09-04 實測 56 張）。
    所以這裡不像鏡像端那樣需要截斷防護。**這是實測結論不是假設**——哪天
    這個端點加了分頁，這裡會開始靜默漏單，而漏掉的單看起來就像沒有漂移。
    """
    data, why = api_get(base, f"/api/companies/{company_id}/issues", token)
    if data is None:
        return None, why
    if not isinstance(data, list):
        return None, "來源端 issues 端點沒有回陣列"

    out = []
    for it in data:
        if project_id and it.get("projectId") != project_id:
            continue
        if it.get("hiddenAt"):
            continue
        ref = it.get("identifier") or ""
        if not ref or not in_mirror_scope(ref, since):
            continue
        skipped = False
        if ref not in mirrored_refs:
            comments, _ = api_get(base, f"/api/issues/{it['id']}/comments", token)
            skipped = any(
                MIRROR_SKIPPED_RE.search(c.get("body") or "")
                for c in (comments or []) if isinstance(c, dict)
            )
        out.append(SourceIssue(ref=ref, status=it.get("status") or "",
                               mirror_skipped=skipped))
    return out, ""


def check_mirror_recon(root: Path) -> SelfcheckResult:
    """來源端與鏡像端的單號／狀態／開關狀態要一致（MYL-54）。

    `mirror_platform` 整段缺席＝不鏡像＝本項無事可做（schema 明訂缺席是預設
    狀態、不是設定缺漏），直接通過。
    """
    res = SelfcheckResult("mirror-recon", "工單鏡像與來源端對得上帳")
    cfg = read_config(root)
    mirror_platform = cfg.get("mirror_platform", "")
    if not mirror_platform:
        res.summary += "（`mirror_platform` 未設定＝不鏡像，無事可對）"
        return res
    if mirror_platform != "github":
        res.skipped = f"`mirror_platform: {mirror_platform}` 目前沒有對帳實作（只有 github 有）"
        return res

    if os.environ.get(MIRROR_OFFLINE_ENV):
        res.skipped = f"{MIRROR_OFFLINE_ENV} 已設，本次不連線對帳"
        return res

    source_platform = cfg.get("devtools_platform", "")
    opts = cfg.get("platform_options", {})
    gh_opts = opts.get("github", {}) if isinstance(opts, dict) else {}
    pc_opts = opts.get("paperclip", {}) if isinstance(opts, dict) else {}

    fetched, why = fetch_mirror_issues(
        root, gh_opts.get("project_title", "Foundry"),
        gh_opts.get("project_owner", "@me"))
    if fetched is None:
        res.skipped = f"讀不到鏡像端：{why}"
        return res
    mirrors, truncated = fetched
    if truncated:
        res.failures.append(
            f"鏡像端 issue 或看板項目數達 `--limit {MIRROR_LIST_LIMIT}` 上限，結果可能被截斷"
            "——截斷過的對帳會把漏建報成全過，先把上限提高或改分頁再跑"
        )

    base = (os.environ.get("PAPERCLIP_API_URL") or "").rstrip("/")
    base = base[:-4] if base.endswith("/api") else base
    token = os.environ.get("PAPERCLIP_API_KEY") or ""
    company_id = pc_opts.get("company_id", "")
    if company_id.startswith("${") and company_id.endswith("}"):
        company_id = os.environ.get(company_id[2:-1], "")
    if not (base and token and company_id):
        res.skipped = ("讀不到來源端：缺 `PAPERCLIP_API_URL`／`PAPERCLIP_API_KEY`／"
                       "company id（CI 上必然如此，見本節註解）")
        return res

    sources, why = fetch_source_issues(
        base, token, company_id, pc_opts.get("project_id", ""),
        gh_opts.get("mirror_since", ""), {m.ref for m in mirrors})
    if sources is None:
        res.skipped = f"讀不到來源端：{why}"
        return res

    res.failures.extend(reconcile_mirror(sources, mirrors, source_platform))
    res.summary += f"（來源端 {len(sources)} 張、鏡像端 {len(mirrors)} 張）"
    return res


SELFCHECKS = (check_entry_sync, check_nav_sync, check_handbook_anchors, check_rule_ids,
              check_rule_marks, check_big_files, check_internal_links,
              check_version_shape, check_table_shape, check_org_sync,
              check_handbook_stamp, check_mirror_recon)


def run_selfcheck(root: Path) -> list:
    return [check(root) for check in SELFCHECKS]


def render_selfcheck_text(results: list) -> str:
    lines = []
    for r in results:
        mark = "❌" if r.failures else ("⏭" if r.skipped else "✅")
        lines.append(f"{mark} [{r.name}] {r.summary}")
        if r.skipped:
            lines.append(f"  - 跳過（未實際檢查）：{r.skipped}")
        lines.extend(f"  - {f}" for f in r.failures)
    bad = sum(len(r.failures) for r in results)
    skipped = sum(1 for r in results if r.skipped)
    # 跳過數要跟在總結行後面：只印「全部通過」會讓沒查過的項目看起來查過了。
    tail = f"，{skipped} 項跳過未檢查" if skipped else ""
    lines.append(
        f"foundry-lint --selfcheck：全部通過{tail}"
        if not bad
        else f"foundry-lint --selfcheck：{bad} 項未通過{tail}"
    )
    return "\n".join(lines)


def render_selfcheck_json(results: list) -> str:
    return json.dumps(
        {
            "passed": all(r.passed for r in results),
            "checks": [
                {"name": r.name, "passed": r.passed, "failures": r.failures,
                 "skipped": r.skipped or None}
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
        help="跑 repo 規範自檢（雙入口同步、手冊 nav、錨點、規則 ID、規則標記、"
             "大檔清單、相對連結、手冊戳記、鏡像對帳），不需 --type／file",
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
