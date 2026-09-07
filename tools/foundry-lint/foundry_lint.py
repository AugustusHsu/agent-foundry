#!/usr/bin/env python3
"""foundry-lint：檢查文件是否含模板規定的必備二級標題，並提供 repo 規範自檢。

規格來源：docs/features/foundry-lint/LLD.md（介面、資料模型、流程、錯誤表均依該文件）。
`--selfcheck` 為 MYL-36 增訂的機械層閘門，每項檢查各對應一個實際踩過的缺陷。
exit code：0＝通過、1＝不通過、2＝執行／使用錯誤。
"""

import argparse
import ast
import inspect
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
#: 哪一行算「違反段」。原本是 `startswith("**違反：**")`，字面到連多一個界定語
#: 都認不得，於是三種寫法悄悄掉出覆蓋而檢查照樣綠：規則 ID 冠在前
#: （`` **`O4` 違反：** ``）、限定語塞進粗體內（`**違反（本節矩陣整體）：**`）、
#: 寫成清單項目（`- **違反：**`）。前兩種是 MYL-79 第 1 輪的實際漏網——覆蓋數
#: 從 26 掉到 25，沒有任何東西出聲；漏標本身也就跟著不會被擋（MYL-99）。
#:
#: 放寬的只有**界定前綴／後綴**：粗體裡除了「違反：」，只准再多一段反引號包的
#: 規則 ID 或一組括號限定語。**不放寬成「粗體裡出現『違反：』就算」**——圖例節
#: 本來就有 `- **沒有「違反：」行的小節…**` 這種散文句，把它算進覆蓋等於要求
#: 散文去補標記，而誤殺比漏標更難救：它會逼下一個人把誠實的敘述改成假標記去
#: 迎合檢查。行內、句中的「違反」照樣不算，理由見 `check_rule_marks` docstring。
_RULE_MARK_QUALIFIER = r"(?:`[^`]+`|（[^）]*）|\([^)]*\))"
RULE_MARK_LINE_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?"                # 行首容許縮排與清單項目符號
    rf"\*\*(?:{_RULE_MARK_QUALIFIER}[ \t]*)?"  # 粗體開頭，可帶界定前綴
    rf"違反(?:[ \t]*{_RULE_MARK_QUALIFIER})?"   # 「違反」本體，可帶界定後綴
    r"：\*\*"
)
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


#: 判定「這個 repo 是不是 Foundry 規則本體」的唯一依據（MYL-87）。
#: ⚠️ **這不是隨手挑的特徵，是規格上的硬對應**：`skills/foundry-init/SKILL.md` §2
#: 第 3 點的複製清單最後一行明寫「不複製：`skills/foundry-init/`（目標專案用不到）」，
#: 所以「有這個目錄 ⇔ 是規則本體」，任何照那份清單初始化出來的專案都不會有。
#: 那一行同時留了一句回指本檔的註解——兩邊互鎖，改一邊要先看另一邊。
RULE_REPO_MARKER_REL = "skills/foundry-init"


def is_rule_repo(root: Path) -> bool:
    """本 repo 是 Foundry 規則本體，而不是被 `foundry-init` 導入的目標專案。"""
    return (root / RULE_REPO_MARKER_REL).is_dir()


def handbook_absent_skip(root: Path) -> str:
    """手冊兩項（`nav-sync`／`anchors`）該不該跳過；回傳跳過理由。

    MYL-87：這兩項守的是「手冊與 nav／錨點對得上」。目標專案沒有
    `docs/handbook/`，那個對應關係根本不存在，於是它們一起紅——而 `make check`
    正是入口檔叫每個新 session 跑的那一行，第一次跑就掛。

    **跳過條件刻意是兩層，缺一不可**：

    1. 不是規則本體（`is_rule_repo()`）——只有這一層擋得住「本 repo 的手冊被誤刪
       會從 ❌ 變成 ⏭」。那是把閘門放鬆，不是修好它。
    2. `docs/handbook/` 真的不存在——只有這一層擋得住「目標專案哪天自建了手冊卻
       與 nav 對不上，檢查卻沉默」。手冊一旦存在就照驗，不因為它是目標專案而放寬。
       這一層對這兩項成立，是因為它們的對照端（`mkdocs.yml` 的 nav、章內錨點）
       **是目標專案自己的東西**：自建手冊後報出來的紅字（`mkdocs.yml 不存在`）
       既是真缺陷、也修得掉。**`handbook-stamp` 不同**，它的對照端是 agent-foundry
       自家那四章，第 2 層另立判準，見 `stamped_chapters_absent_skip()`（MYL-92）。

    ⚠️ 本函式只在**呼叫點已經確定 `docs/handbook/` 不存在**時才被問到（兩處都是
    `if not handbook.is_dir():` 底下）。所以上面第 2 層在這裡其實恆真——它寫出來是
    為了讓條件的完整形狀留在單一來源，不是每次呼叫都真的在判。要把呼叫點上移到
    檢查最前面（`handbook-stamp` 就是那樣）之前，先讀 `stamped_chapters_absent_skip()`
    最後那段：那正是兩支函式沒有合併的理由。

    跳過用 `SelfcheckResult.skipped`（印 ⏭、總結行另報跳過數），**不是靜靜略過**：
    沿用 `mirror-recon` 已經在用的那套姿態，不新增第二種。
    """
    if is_rule_repo(root) or (root / HANDBOOK_REL).is_dir():
        return ""
    return (f"本專案不是 Foundry 規則本體（沒有 `{RULE_REPO_MARKER_REL}/`）"
            f"且沒有 `{HANDBOOK_REL}/`，沒有手冊可對照")


def stamped_chapters_absent_skip(root: Path) -> str:
    """`handbook-stamp` 該不該跳過；回傳跳過理由（MYL-92）。

    第 1 層與 `handbook_absent_skip()` 相同（`is_rule_repo()`），第 2 層不同：
    問的是「**那四章一份都不在**」，而不是「`docs/handbook/` 不存在」。

    **為什麼要換掉第 2 層**：`STAMPED_CHAPTERS` 是 agent-foundry 自家的四章，目標
    專案沒有任何理由擁有它們。沿用「手冊不存在」那一層，目標專案一自建手冊（哪怕
    只放一份 `01-start.md`），本項就立刻吐四條「章節不存在」，指名它不該有的檔案
    ——**那個紅字在目標專案修不掉**，等於逼維護者習慣性忽略紅字（`SelfcheckResult`
    的 docstring 論證過這個失效模式）。

    **為什麼是另立函式，而不是把條件改進 `handbook_absent_skip()`**：不是因為那樣
    會弄壞另外兩項——實測過，不會。`nav-sync`／`anchors` 是**在 `docs/handbook/`
    不存在時才**去問那支函式（見兩處呼叫點的 `if not handbook.is_dir():`），而目錄
    不存在時四章必然也不在，兩種寫法對它們等價。理由是這個等價**靠的是呼叫點的
    守衛、不是函式本身的契約**：條件一旦寫進共用函式，那支函式就開始依賴
    `STAMPED_CHAPTERS`，而它對三個呼叫者裡的兩個毫無意義，回傳的理由字串也會說成
    「沒有掛戳記的章節」——對那兩項而言那不是它們跳過的原因。誰哪天把呼叫點上移
    統一（本項就是這麼寫的），等價就沒了，而且不會有任何測試紅。分成兩支函式，
    每一支的條件與訊息都只對自己的呼叫者負責。
    ⚠️ MYL-92 的 AC0 留言把這一段說成「改共用函式會讓那兩項一起跳過」，**那句是
    錯的**，正確的理由是上面這段；定案（(a) 改程式）不受影響。

    判準①（本 repo 不得因此變鬆）由第 1 層保證，與第 2 層無關：規則本體恆有
    `skills/foundry-init/`，四章刪光也照驗、戳記落後也照驗。
    規則本體**少一章**同樣照驗——還有三章在，第 2 層不成立。

    已知且刻意的邊界：目標專案若只複製四章中的一部分，缺的那幾章仍報紅。
    那個紅是對的——它確實有掛戳記的章節，就該把戳記維護齊全。
    """
    if is_rule_repo(root):
        return ""
    if any((root / HANDBOOK_REL / name).exists() for name in STAMPED_CHAPTERS):
        return ""
    return (f"本專案不是 Foundry 規則本體（沒有 `{RULE_REPO_MARKER_REL}/`）"
            f"且 `{HANDBOOK_REL}/` 裡沒有任何一份掛戳記的章節"
            f"（{'、'.join(STAMPED_CHAPTERS)}），沒有戳記可對照")


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
        # MYL-87：判準與兩層條件的理由都在 `handbook_absent_skip()`。
        res.skipped = handbook_absent_skip(root)
        if not res.skipped:
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
        # MYL-87：同 `check_nav_sync`，判準見 `handbook_absent_skip()`。
        res.skipped = handbook_absent_skip(root)
        if not res.skipped:
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

    哪一行算違反段則交給 `RULE_MARK_LINE_RE`（MYL-99 放寬到容許界定前綴與清單
    項目符號）。兩端都是同一個取捨：**判太窄會漏標無聲，判太寬會誤殺散文**。
    所以放寬的是行首那一小段的形狀，不是「出現『違反：』就算」——後者會把圖例
    節的敘述句一起抓進來，而那類誤報只能靠改散文去迎合，等於把檢查倒過來用。
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
        if not RULE_MARK_LINE_RE.match(line):
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


#: 產生模式給第二欄填的佔位字串。第二欄（「通常只需要哪一部分」）是編輯判斷，
#: 機械產不出來——留一個**看得出來還沒填**的字串，比留空白誠實。
#: `check_big_files` 只驗第一欄的路徑集合，所以這一欄不影響紅綠。
BIG_FILES_TODO = "{待填：通常只需要哪一部分}"


def render_big_files_list(root: Path) -> str:
    """印出可直接貼進入口檔 §4 的大檔清單表格列（MYL-87）。

    `foundry-init` 步驟 2.5 產生入口檔時跑這一支，把輸出填進 `<TARGET>` 的
    `CLAUDE.md`／`AGENTS.md`。**為什麼要機械產生**：模板那格是 `| {路徑} |`
    佔位符，人手抄一次就等著漂——而「寫死在散文裡的清單沒有人會回來改」正是
    MYL-42 已經處理過一輪的漂移形狀，不該在導入的每個專案重來一次。

    這一支**不放鬆 `check_big_files` 一行**：它只是把該檢查自己的掃描結果
    （`scan_big_files()`，同一個函式）換成表格列印出來，所以產生的清單與檢查
    要求的集合必然相等。目標專案照樣受 `big-files` 管（MYL-87 AC4）。
    """
    rows = [f"| `{rel}` | {BIG_FILES_TODO} |" for rel in scan_big_files(root)]
    return "\n".join(rows)


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
#: 根目錄的雙入口（MYL-85 AC9）。上面那份目錄清單涵蓋不到它們，而那是全 repo 表格
#: 最密的兩份檔案，又受「共用正文逐字相同」約束——一處被空行切斷會**同時**壞兩份。
#: ⚠️ 引用區塊內的表格（`> | … |`）**不在覆蓋內**且刻意不補：`is_table_row()` 只認
#: 行首是 `|` 的行。目前全 repo 只有一處（`docs/features/git-flow/proposal.md`）、
#: 屬歷史交付物，為它加一層前綴剝離不划算；日後手冊或 protocol 真的出現引用區塊內
#: 的表格再回頭補。
TABLE_SCAN_FILES = ("CLAUDE.md", "AGENTS.md")
#: markdown 表格的分隔列（`| --- | --- |`）。前後空白由呼叫端 `strip()` 掉。
TABLE_SEP_RE = re.compile(r"^\|(?:\s*:?-{2,}:?\s*\|)+$")
#: 切格用的 `|`。GFM 是**先切格、再解析行內語法**，所以反引號與粗體都保護不了管線符號，
#: 只有 `\|` 逃得掉——`` `a|b` `` 寫在表格列裡實際會切成兩格。這裡照 GFM 數，
#: 不照作者的意圖數：意圖數不出來，而讀者看到的正是 GFM 數出來的那個結果。
TABLE_CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


def is_table_row(line: str) -> bool:
    """這一行渲染時會被當成表格列（縮排在清單裡的表格也算）。"""
    return line.lstrip().startswith("|")


def is_table_header(lines: list, i: int) -> bool:
    """`lines[i]` 是表頭列——它自己是表格列，且**下一行是分隔列**。

    少了後半這道，任何以 `|` 開頭的段落都會被誤判成表。
    """
    return (is_table_row(lines[i]) and i + 1 < len(lines)
            and bool(TABLE_SEP_RE.match(lines[i + 1].strip())))


def table_cells(line: str) -> list:
    """這一列渲染出來的每一格（已去頭尾空白）。

    前導與收尾的 `|` 在 GFM 都是可選的裝飾，各自切出一個空段，不算格。
    """
    parts = TABLE_CELL_SPLIT_RE.split(line.strip())
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [p.strip() for p in parts]


def count_cells(line: str) -> int:
    """這一列渲染出來會有幾格。"""
    return len(table_cells(line))


def table_column_mismatches(text: str) -> list:
    """回傳欄數與表頭對不上的列：`(行號, 這列幾格, 表頭幾格, 是不是分隔列)`。

    GFM 用**表頭那一列**決定表格有幾欄，其餘每一列一律裁切或補齊到那個數：
    多出來的格子**整格丟掉**、少的補成空白。兩邊都不會有任何警告。

    `8416f66`（MYL-79 訂正 `known-drift` 的 `S5`）就是多出來那一種：改寫後的
    `S5` 有 4 格、同表其餘 8 列與表頭都是 3 格，於是**整個「正確寫法」欄在渲染時
    消失**——原文讀起來完全正常，`--selfcheck` 全綠，`table-shape` 當時只驗連續性。

    分隔列另外看：它的格數與表頭不符時 GFM 判定**整段根本不是表格**，會原樣印出
    每一行的管線符號。這種時候後面的列數多少都沒有意義，所以報完就跳過整張表。
    """
    lines = text.splitlines()
    bad = []
    in_fence = False
    i = 0
    while i < len(lines):
        if FENCE_RE.match(lines[i]):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence or not is_table_header(lines, i):
            i += 1
            continue
        want = count_cells(lines[i])
        sep = count_cells(lines[i + 1])
        j = i + 2
        if sep != want:
            bad.append((i + 2, sep, want, True))
        else:
            while j < len(lines) and is_table_row(lines[j]):
                got = count_cells(lines[j])
                if got != want:
                    bad.append((j + 1, got, want, False))
                j += 1
        while j < len(lines) and is_table_row(lines[j]):
            j += 1
        i = j
    return bad


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
        if in_fence or not is_table_header(lines, i):
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


def table_scan_targets(root: Path) -> list:
    """`table-shape` 要掃的 .md：`TABLE_SCAN_DIRS` 底下全部，加上根目錄雙入口。

    去重後排序——雙入口不在那幾個目錄底下，這裡的 `set` 是為了讓日後往
    `TABLE_SCAN_FILES` 加一份已經被目錄涵蓋的檔案時不會被掃兩次（同一處
    報兩條一模一樣的紅字，讀的人會以為有兩個地方壞掉）。
    """
    found = set()
    for top in TABLE_SCAN_DIRS:
        base = root / top
        if base.is_dir():
            found.update(base.rglob("*.md"))
    for rel in TABLE_SCAN_FILES:
        path = root / rel
        if path.is_file():
            found.add(path)
    return sorted(found)


def check_table_shape(root: Path) -> SelfcheckResult:
    """markdown 表格的兩種「原文正常、渲染是壞的」：夾空行被切斷、欄數對不上表頭。

    - 夾空行（MYL-76 AC9）：表格在空行處結束，後面的續列變成普通段落。
    - 欄數（MYL-98，出處 `8416f66`）：GFM 以表頭決定欄數，多的格子整格丟掉、
      少的補空白，兩邊都不出聲——`S5` 那次多出來的那一格裝著整個「正確寫法」欄。

    這一項與 `L13`／`L21`／`X4` 同族：**斷言全綠但渲染是壞的**。差別在於前三者
    是外部平台的行為，這兩條是 markdown 自己的，所以擋得住，也就該擋。

    掃描範圍見 `TABLE_SCAN_DIRS` ＋ `TABLE_SCAN_FILES`——後者是 MYL-85 AC9 補上的
    根目錄雙入口，在那之前全 repo 表格最密的兩份檔案不在覆蓋內。
    """
    res = SelfcheckResult("table-shape", "markdown 表格沒有被空行切斷、每列欄數與表頭一致")
    scanned = 0
    for path in table_scan_targets(root):
        scanned += 1
        rel = path.relative_to(root).as_posix()
        text = read_text(path)
        for lineno in table_breaks(text):
            res.failures.append(
                f"{rel}:{lineno} 是上面那張表的續列，但中間隔了空行"
                "——渲染時表格在空行處就結束了，這一行起會變成普通段落，"
                "連分隔符一起原樣印出來。刪掉那個空行；真要分成兩張表，"
                "就給下面這段補上自己的表頭與分隔列"
            )
        for lineno, got, want, is_sep in table_column_mismatches(text):
            if is_sep:
                res.failures.append(
                    f"{rel}:{lineno} 是分隔列，卻有 {got} 格、表頭有 {want} 格"
                    "——兩者不等時 GFM 判定這整段根本不是表格，每一行的管線符號"
                    f"都會原樣印出來。把分隔列補成 {want} 格"
                )
            elif got > want:
                res.failures.append(
                    f"{rel}:{lineno} 有 {got} 格，表頭只有 {want} 格"
                    f"——GFM 以表頭定欄數，多出來的第 {want + 1} 格起會被**整格丟掉**，"
                    "原文讀得到、渲染出來看不到。把多的格子併回去；"
                    "格子內容裡的管線符號（含反引號裡的）要寫成 `\\|` 才不算分隔"
                )
            else:
                res.failures.append(
                    f"{rel}:{lineno} 只有 {got} 格，表頭有 {want} 格"
                    "——渲染時缺的格子補成空白，看起來像漏填。補齊到 "
                    f"{want} 格；真的要留白就寫成空格子"
                )
    res.summary += f"（掃 {scanned} 份）"
    return res


# ── `config-schema`：設定欄位名與 schema 版本 ↔ config-schema.md（MYL-85）──
#
# 這一格的特性是**錯了不會有任何聲音**：欄位名寫錯的設定檔在讀取端只是「必填欄位
# 缺席」，而文件裡的欄位名多半只是散文。MYL-82 把 `platform` 正名成
# `devtools_platform` 時，全 repo 沒有一項自檢在驗「設定欄位叫什麼名字」——那次靠
# 的是全 repo 正則掃描＋人工判讀。做完了，缺口原樣留著；本項就是那個機械兜底。

#: schema 權威。`.foundry/config.yml` 的每一個頂層欄位叫什麼、必不必填、值域是
#: 什麼，都只寫在這一份的「頂層結構」表裡。本檢查把它當**唯一來源**讀，不在程式
#: 裡另抄一份——另抄的那份就是下一個會漂的來源。
CONFIG_SCHEMA_REL = "skills/foundry-platform/config-schema.md"
#: 範例檔跟真設定檔一起驗：`foundry-init` 拿它當起點，它要是留著舊欄位名，錯誤會
#: 被複製到之後導入的每一個專案，而那些專案不會知道自己抄到的是舊名。
CONFIG_EXAMPLE_REL = "skills/foundry-platform/config.example.yml"
CONFIG_SCHEMA_TOP_HEADING = "頂層結構"
CONFIG_SCHEMA_HISTORY_HEADING = "版本沿革"
#: 「頂層結構」表 `foundry` 那一列的散文側現行版本宣告。
CONFIG_SCHEMA_CURRENT_RE = re.compile(r"目前固定 `(\d+)`")
#: 表格第一欄的欄位名（`` `devtools_platform` ``）。整格必須就是一個反引號詞。
CONFIG_SCHEMA_FIELD_RE = re.compile(r"^`([a-z][a-z0-9_]*)`$")
#: 「版本沿革」表第一欄的版本號（`` `2` ``）。
CONFIG_SCHEMA_VERSION_CELL_RE = re.compile(r"^`(\d+)`$")
#: 必填欄的字面（非必填寫 `─`）。整格比對，所以**表裡只准出現這兩種寫法**：加任何
#: 註記（`✅（見下）`）就會讓該欄位靜靜掉出必填集合，而必填集合同時是
#: `foundry_config_fences()` 判準第 3 層的證據集，它縮小 ⇒ 舊欄位名掃描的覆蓋跟著
#: 無聲變窄。認不得的第三種寫法由 `check_config_schema()` 的形狀守衛報紅。
CONFIG_SCHEMA_REQUIRED_MARK = "✅"
CONFIG_SCHEMA_OPTIONAL_MARK = "─"
CONFIG_SCHEMA_REQUIRED_MARKS = (CONFIG_SCHEMA_REQUIRED_MARK, CONFIG_SCHEMA_OPTIONAL_MARK)
#: 型別欄標這個字面的欄位，一定要讀得出值域——拿它當 `CONFIG_SCHEMA_ENUM_RE` 的對照
#: 物（同樣由形狀守衛報紅）。少了對照，把分隔符從 `｜` 改成別的寫法會讓值域整組
#: 靜默消失，而其餘檢查照常運作、紅綠完全無異狀。
CONFIG_SCHEMA_ENUM_TYPE = "枚舉"
#: 型別欄的合法字面——**白名單，不認得就紅**，不是「等於『枚舉』才檢查」那種相等
#: 比對。相等比對的失敗方向是**靜靜跳過**：型別格被加一個註記（`枚舉（見下）`），
#: 那一欄的值域守衛就整條消失，之後把它的值域寫壞也不會有人出聲（實測 M3a／M3c，
#: MYL-111 審查補正）。⚠️ 這道守衛只擋得住加註記，擋不住把「枚舉」整格換成「物件」
#: ——那是把宣告本身改了，不是本檢查讀錯。白名單的代價是：日後表裡真的要多一種型別
#: 時本項會紅。那是刻意的——改型別欄的形狀就該回頭確認本檢查還讀得懂它。
CONFIG_SCHEMA_TYPES = ("整數", CONFIG_SCHEMA_ENUM_TYPE, "物件")
#: 說明欄**開頭**那一串 `a｜b｜c` ＝ 枚舉值域。只認開頭、不掃整格：說明文字裡本來
#: 就到處是反引號（其他欄位名、檔案路徑、規則 ID、工單編號），掃整格會把它們全收
#: 成「合法值」，那樣的值域擋不住任何東西。
CONFIG_SCHEMA_ENUM_RE = re.compile(r"^(`[a-z0-9-]+`(?:｜`[a-z0-9-]+`)+)")
#: 說明欄寫「值域同 `x`」時借用該欄的值域（`mirror_platform` 就是這樣寫的）。
CONFIG_SCHEMA_ENUM_ALIAS_RE = re.compile(r"值域同 `([a-z][a-z0-9_]*)`")
#: 已正名掉的舊欄位名 → 現名。手維護，但這份清單是**封閉**的：只有正名才會多一則，
#: 而正名必經 CEO 提案＋使用者核可＋遞增 `foundry` 版本號（config-schema「合法性
#: 總則」）。反過來從「版本沿革」表把改名剖析出來要讀散文，而散文會用各種寫法描述
#: 同一次改名，剖析失敗的方向是**靜默漏掉**——比手維護一則更糟。
RETIRED_CONFIG_FIELDS = {"platform": "devtools_platform"}   # MYL-82

#: 掃「文件裡還有沒有人拿舊欄位名當設定欄位用」的範圍。
CONFIG_FIELD_SCAN_DIRS = ("skills", "docs")
CONFIG_FIELD_SCAN_FILES = ("CLAUDE.md", "AGENTS.md")
#: ⚠️ `docs/features/` 排除（MYL-85 AC4，同 MYL-82 AC3）：那底下是各模組**當時**的
#: 交付物（BRD／PRD／HLD／LLD／審查報告），寫的是那個時點的事實。把 MYL-9 HLD 裡的
#: `platform:` 改成新名，等於竄改一份簽核過的設計文件，而且改完看起來更整齊、沒有
#: 人會發現。與 `VERSION_SHAPE_ALLOW` 是同一條取捨（`V5`：這一格的風險方向是誤管
#: 而不是漏管）。
CONFIG_FIELD_SCAN_SKIP_PREFIXES = (("docs", "features"),)
#: yaml 圍欄的開頭：資訊字串必須就是 `yaml`／`yml`。
YAML_FENCE_RE = re.compile(r"^\s{0,3}(?:```|~~~)[ \t]*(?:yaml|yml)[ \t]*$", re.I)
#: 頂格的 `鍵:`。**只認第 0 欄**——巢狀鍵（`platform_options` 底下那些）不是頂層
#: 設定欄位，而被正名掉的都是頂層欄位。
YAML_TOP_KEY_RE = re.compile(r"^([a-z][a-z0-9_]*):(?:[ \t]|$)")


def first_table_rows(lines: list) -> list:
    """這段裡**第一張**表的資料列（不含表頭與分隔列）。

    只取第一張是必要的：`section_lines()` 取到的段落含更下層的子節，而
    「頂層結構」底下的子節自己還有一張表（兩條軸的對照表）。混進來的話，
    欄位清單會多出「開發工具面」這種不是欄位名的東西。
    """
    for i in range(len(lines)):
        if is_table_header(lines, i):
            rows = []
            j = i + 2
            while j < len(lines) and is_table_row(lines[j]):
                rows.append(lines[j])
                j += 1
            return rows
    return []


def parse_schema_fields(text: str) -> dict:
    """config-schema.md「頂層結構」表 → `{欄位名: (必填?, 說明欄原文)}`，保序。"""
    fields: dict = {}
    for row in first_table_rows(section_lines(text, CONFIG_SCHEMA_TOP_HEADING)):
        cells = table_cells(row)
        if len(cells) < 4:
            continue
        m = CONFIG_SCHEMA_FIELD_RE.match(cells[0])
        if m:
            fields[m.group(1)] = (cells[2] == CONFIG_SCHEMA_REQUIRED_MARK, cells[3])
    return fields


def parse_schema_marks(text: str) -> dict:
    """同一張表 → `{欄位名: (型別欄原文, 必填欄原文)}`。只給形狀守衛用。

    另開一個函式而不是把 `parse_schema_fields()` 的二元組擴成三元組：那個回傳值
    有數處在做 `(req, desc)` 解包，改 arity 會一起壞，而這兩格只有守衛需要原文。

    ⚠️ **本函式的鍵集與 `parse_schema_fields()` 相同是被依賴的性質，不是巧合**：
    `check_config_schema()` 的行完整性守衛只比對 `first_table_rows()` 與
    `parse_schema_fields()` 的長度，靠「兩者取列條件字面相同」（同一個
    `first_table_rows()` ＋同一個 `len(cells) < 4` ＋同一個
    `CONFIG_SCHEMA_FIELD_RE`）順帶覆蓋本函式——於是本函式底下那三道格守衛不會被
    「整列讀丟」繞過。哪天這裡的取列條件與 `parse_schema_fields()` 被改得不一樣，
    那道覆蓋會**無聲**消失（守衛數得對、卻守到另一批列）。要改取列條件請兩邊一起
    改，或給本函式補一道自己的行完整性守衛（MYL-111 審查第 4 輪）。
    """
    marks: dict = {}
    for row in first_table_rows(section_lines(text, CONFIG_SCHEMA_TOP_HEADING)):
        cells = table_cells(row)
        if len(cells) < 4:
            continue
        m = CONFIG_SCHEMA_FIELD_RE.match(cells[0])
        if m:
            marks[m.group(1)] = (cells[1], cells[2])
    return marks


def parse_schema_enums(fields: dict) -> dict:
    """欄位 → 枚舉值域；沒有宣告值域的欄位不在回傳裡（物件型欄位就是這種）。

    兩種來源：說明欄開頭那一串 `a｜b｜c`，以及「值域同 `x`」的借用。借用**只解
    一層**——`mirror_platform` 借 `devtools_platform`，而後者自己寫了值域。哪天寫成
    互相借用，這裡讀到的就是空的，於是那個欄位不受值域管；那是漏報不是誤報，
    與本項其餘判準同一個方向。
    """
    direct: dict = {}
    for name, (_, desc) in fields.items():
        m = CONFIG_SCHEMA_ENUM_RE.match(desc)
        if m:
            direct[name] = tuple(v.strip("`") for v in m.group(1).split("｜"))
    enums = dict(direct)
    for name, (_, desc) in fields.items():
        if name in enums:
            continue
        alias = CONFIG_SCHEMA_ENUM_ALIAS_RE.search(desc)
        if alias and alias.group(1) in direct:
            enums[name] = direct[alias.group(1)]
    return enums


def parse_schema_versions(text: str) -> tuple:
    """`(「頂層結構」表宣告的現行版本, 「版本沿革」表最後一列的版本)`。

    兩處各讀一次而不是只讀一處：它們是同一件事寫在兩個地方，而**遞增版本號時漏
    改其中一處**是最可能的失手——只讀一處的話，本檢查就會拿一個過期的數字去核對
    設定檔，而且核得振振有詞。讀不出來的那一側回 `None`，由呼叫端報形狀漂了。
    「版本沿革」表按時間排，所以現行版本是最後一列。
    """
    declared = latest = None
    for row in first_table_rows(section_lines(text, CONFIG_SCHEMA_TOP_HEADING)):
        cells = table_cells(row)
        if len(cells) >= 4 and cells[0] == "`foundry`":
            m = CONFIG_SCHEMA_CURRENT_RE.search(cells[3])
            declared = m.group(1) if m else None
    for row in first_table_rows(section_lines(text, CONFIG_SCHEMA_HISTORY_HEADING)):
        cells = table_cells(row)
        m = CONFIG_SCHEMA_VERSION_CELL_RE.match(cells[0]) if cells else None
        if m:
            latest = m.group(1)
    return declared, latest


def config_field_scan_targets(root: Path) -> list:
    """舊欄位名要掃的 .md（repo 相對路徑，已排序）。範圍與排除見上方常數註解。"""
    found = set()
    for top in CONFIG_FIELD_SCAN_DIRS:
        base = root / top
        if not base.is_dir():
            continue
        for path in base.rglob("*.md"):
            rel = path.relative_to(root)
            if any(rel.parts[: len(skip)] == skip
                   for skip in CONFIG_FIELD_SCAN_SKIP_PREFIXES):
                continue
            found.add(rel.as_posix())
    for rel in CONFIG_FIELD_SCAN_FILES:
        if (root / rel).is_file():
            found.add(rel)
    return sorted(found)


def foundry_config_fences(text: str, required: set) -> list:
    """文中每一段「看得出是 `.foundry/config.yml` 範例」的 yaml 圍欄裡的頂層鍵。

    回傳 `[(行號, 鍵), …]`。判準有三層，**全部往寧可漏報的方向收**（MYL-85 AC3）：

    1. 圍欄的資訊字串是 `yaml`／`yml`——散文裡提到某個欄位名或平台名不算。
    2. 鍵頂格（第 0 欄）——巢狀鍵不是頂層設定欄位。
    3. 這段圍欄裡至少有一個鍵是 schema 標**必填**的欄位——這是「這段 yaml 是一份
       Foundry 設定檔」的證據。少了這一層，`adapters/gitlab.md` 那段 GitLab CI
       的 `pages:` 也會被收進來，而它跟設定欄位名毫無關係。

    代價是漏報：孤零零示範改名那一行的圍欄（整段只有 `platform: github`）逃得掉。
    這是刻意的——MYL-82 實測過寬鬆判準會掃出 25 檔而多數只是行文，那種檢查會變成
    每次改文件都要哄它的雜訊源，**比沒有更糟**（誤報的檢查最後一定被關掉，
    連同它本來擋得住的那些一起消失）。
    """
    out: list = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if not YAML_FENCE_RE.match(lines[i]):
            i += 1
            continue
        j = i + 1
        keys = []
        while j < len(lines) and not FENCE_RE.match(lines[j]):
            m = YAML_TOP_KEY_RE.match(lines[j])
            if m:
                keys.append((j + 1, m.group(1)))
            j += 1
        if any(key in required for _, key in keys):
            out.extend(keys)
        i = j + 1
    return out


def check_config_schema(root: Path) -> SelfcheckResult:
    """`.foundry/` 設定檔的欄位名與 schema 版本要對得上 config-schema.md（MYL-85）。

    驗四件事：

    1. **欄位名**：schema 標必填的欄位都在；設定檔裡沒有 schema 不認得的頂層欄位。
       **兩個方向都要**——只驗前者的話，把 `devtools_platform` 打成
       `devtool_platform` 只會報「缺必填欄位」，讀的人不會知道那個鍵其實就在檔案裡、
       只是拼錯了一個字。
    2. **schema 版本**：`foundry:` ＝ config-schema.md 宣告的現行版本；而
       config-schema.md 自己的兩處版本宣告（散文側的「目前固定 `N`」與「版本沿革」
       表最後一列）也要一致。
    3. **枚舉值域**：值域寫在 schema 表裡的欄位，值要落在值域內。`org.yml` 的
       `ai_platform` 一併驗（AC8）——⚠️ 它是**選填**，只驗「有填就要合法」，
       不得驗成必填（MYL-82 的裁定，語意留給 `foundry-ai-platform`）。
    4. **文件裡的舊欄位名**：已正名掉的名字不得再被當成設定欄位用。判準與它刻意
       選的漏報方向見 `foundry_config_fences()`。

    `.foundry/config.yml` 與 `config.example.yml` 兩份都驗，理由見
    `CONFIG_EXAMPLE_REL` 的註解。

    上面四件事全靠「讀得懂 config-schema.md 那張表」，所以另有一道**形狀守衛**：
    不只擋「整表讀不出來」，也擋「只讀錯一格」（必填欄出現第三種字面、型別標
    「枚舉」卻讀不出值域）。少了它，改 schema 時最可能發生的那兩種編輯會讓本項的
    一部分靜默失效而仍然全綠——那正是本項存在要防的事（MYL-111 審查 §3）。

    **本項不跳過目標專案**：兩份設定檔與 config-schema.md 都在 `foundry-init` 的
    複製範圍內，對照端在目標專案照樣存在——而目標專案正是最需要這道把關的地方
    （導入時抄到舊欄位名，讀取端只會說「缺必填欄位」）。
    """
    res = SelfcheckResult("config-schema", "設定檔欄位名與 schema 版本對得上 config-schema")
    schema_path = root / CONFIG_SCHEMA_REL
    if not schema_path.exists():
        res.failures.append(
            f"{CONFIG_SCHEMA_REL} 不存在——設定欄位名的唯一權威缺席，本項無從判定"
        )
        return res
    schema_text = read_text(schema_path)

    fields = parse_schema_fields(schema_text)
    required = {name for name, (req, _) in fields.items() if req}
    if not fields or not required:
        res.failures.append(
            f"讀不出 {CONFIG_SCHEMA_REL}「{CONFIG_SCHEMA_TOP_HEADING}」的欄位表"
            f"（讀到 {len(fields)} 個欄位、{len(required)} 個必填）"
            "——表的形狀變了就要一起改本檢查，不要讓它靜靜失效"
        )
        return res
    enums = parse_schema_enums(fields)

    # 形狀守衛：上面那道 `not fields or not required` 擋得住「整表讀不出來」，擋不住
    # **只讀錯一格**——而本項存在的理由就是「設定欄位錯了不會有任何聲音」，讀 schema
    # 的方式自己有這個失效點就自打嘴巴（MYL-111 審查 §3）。表裡的兩格各配對照物，
    # 三道守衛**一律寫成白名單**（不認得就紅），不寫成相等比對——相等比對認不得的那
    # 一格會被靜靜跳過，等於每加一層守衛只是把同一個靜默點往上搬一格（審查補正）：
    #   - 必填欄字面限定 `✅`／`─`。出現第三種寫法時，該欄位會靜靜掉出必填集合，
    #     接著「缺必填欄位」那一半與舊欄位名掃描的覆蓋一起無聲變窄。
    #   - 型別欄字面限定 `CONFIG_SCHEMA_TYPES`。本檢查是拿這一格判「哪些欄位該有
    #     值域」的，加了註記就等於把下面那道值域守衛從該欄位身上拆掉。
    #   - 標「枚舉」卻讀不出值域 ⇒ 說明欄的分隔符被改寫了（`｜` → `/`、頓號…）。
    #     那會讓值域與 `org.yml` 的 `ai_platform` 整組消失，而本項照樣印 ✅。
    # 這幾道都是「schema 的形狀漂了」，先修 schema 再談設定檔，所以報完就 return。
    #
    # 行完整性擺在三道格守衛**之前**：它們守的是「格」的字面，守不住「整列根本沒被
    # 讀進來」。`parse_schema_fields()`／`parse_schema_marks()` 都是 regex 不 match 就
    # 跳過該列（沒有 else），而 `CONFIG_SCHEMA_FIELD_RE` 兩端錨定 ⇒ 欄位名格加任何裝飾
    # （`**`x`**`、腳註）或少一格，那一列就連同它的必填／型別／值域三道守衛一起靜靜
    # 消失。實測（MYL-111 審查 M4）：schema 把 `ai_platform` 那格加粗、`config.yml` 依
    # schema 明文省略該段（合法），AC8 的 `org.yml` 值域驗證整項失效而 `--selfcheck`
    # 退 0——綠字只從「3 組值域」變成「2 組值域」，沒有人會去 diff 一個 ✅ 的計數。
    # 到這一層就收斂：表找不找得到 → 每一列都解得出 → 每一格都是認得的字面。
    # ⚠️ 只 append 不 return：與下面三道守衛及舊欄位名後盾一起結算。搶先 return 會遮蔽
    # 更具體的原因——欄位名被改掉的那一列同時觸發本條與 `RETIRED_CONFIG_FIELDS` 後盾，
    # 而後盾那句才講得出「映射寫反還是又被正名一次」。
    top_rows = first_table_rows(section_lines(schema_text, CONFIG_SCHEMA_TOP_HEADING))
    if len(top_rows) != len(fields):
        res.failures.append(
            f"{CONFIG_SCHEMA_REL}「{CONFIG_SCHEMA_TOP_HEADING}」表有 {len(top_rows)} "
            f"個資料列，只解得出 {len(fields)} 個欄位名——解不出的那一列會連同它的"
            "必填／型別／值域三道守衛一起靜靜消失。欄位名格只認 `` `欄位名` ``"
            "（整格，不帶粗體或註記），且每一列至少要有四格"
        )
    for name, (typ, mark) in parse_schema_marks(schema_text).items():
        if mark not in CONFIG_SCHEMA_REQUIRED_MARKS:
            res.failures.append(
                f"{CONFIG_SCHEMA_REL}「{CONFIG_SCHEMA_TOP_HEADING}」表 `{name}` 的"
                f"必填欄寫成 {mark!r}——本檢查是拿整格字面判必填的，只認 "
                f"{'／'.join(CONFIG_SCHEMA_REQUIRED_MARKS)}。加了註記的那一格會讓"
                "該欄位靜靜掉出必填集合，缺欄位與舊欄位名兩半的覆蓋跟著變窄"
            )
        if typ not in CONFIG_SCHEMA_TYPES:
            res.failures.append(
                f"{CONFIG_SCHEMA_REL}「{CONFIG_SCHEMA_TOP_HEADING}」表 `{name}` 的"
                f"型別欄寫成 {typ!r}——本檢查是拿型別欄的字面判「哪些欄位該有值域」"
                f"的，只認 {'／'.join(CONFIG_SCHEMA_TYPES)}。加了註記的那一格會讓該"
                "欄位的值域守衛整條消失，之後把它的值域寫壞不會有任何聲音"
            )
        if typ == CONFIG_SCHEMA_ENUM_TYPE and name not in enums:
            res.failures.append(
                f"{CONFIG_SCHEMA_REL}「{CONFIG_SCHEMA_TOP_HEADING}」表 `{name}` 的"
                f"型別是「{CONFIG_SCHEMA_ENUM_TYPE}」，說明欄卻讀不出值域——值域要"
                "寫成開頭那一串 `` `a`｜`b`｜`c` ``（全形分隔符）或「值域同 `x`」。"
                "換成別的寫法不會有任何聲音：值域整組消失，本項仍然全綠"
            )
    # `RETIRED_CONFIG_FIELDS` 是手維護的（取捨見它的註解），配一條廉價後盾：現名一定
    # 在表裡、舊名一定不在。映射寫反、或現名日後又被正名一次而沒回頭改這份清單時，
    # 當場報紅而不是讓「舊欄位名」那一半指著一個不存在的名字。
    for old, new in sorted(RETIRED_CONFIG_FIELDS.items()):
        if new not in fields:
            res.failures.append(
                f"`RETIRED_CONFIG_FIELDS` 說 `{old}` 的現名是 `{new}`，但 "
                f"{CONFIG_SCHEMA_REL} 的「{CONFIG_SCHEMA_TOP_HEADING}」表沒有 "
                f"`{new}`——不是映射寫反，就是它自己又被正名一次而沒回頭改這份清單"
            )
        if old in fields:
            res.failures.append(
                f"`RETIRED_CONFIG_FIELDS` 把 `{old}` 當已正名掉的舊名，"
                f"{CONFIG_SCHEMA_REL} 卻還把它列成現行欄位——兩邊講的不是同一件事"
            )
    # 形狀守衛與這條後盾一起結算：兩者都是「schema 那張表已經對不上程式的讀法」，
    # 而改一格常常同時觸發兩邊（把現名改掉 ⇒ 借用它值域的欄位也解不到）。先把
    # schema 修好再談設定檔，所以此處報完就 return。
    if res.failures:
        return res

    declared, latest = parse_schema_versions(schema_text)
    if not declared or not latest:
        res.failures.append(
            f"讀不出 {CONFIG_SCHEMA_REL} 宣告的現行 schema 版本"
            f"（「{CONFIG_SCHEMA_TOP_HEADING}」表讀成 {declared!r}、"
            f"「{CONFIG_SCHEMA_HISTORY_HEADING}」表讀成 {latest!r}）"
            "——兩處任一改了寫法就要一起改本檢查"
        )
        return res
    if declared != latest:
        res.failures.append(
            f"{CONFIG_SCHEMA_REL} 自己就不一致：「{CONFIG_SCHEMA_TOP_HEADING}」表寫"
            f"「目前固定 `{declared}`」，「{CONFIG_SCHEMA_HISTORY_HEADING}」表最後一列"
            f"是 `{latest}`——遞增版本號時漏改其中一處，設定檔就會被拿一個過期的"
            "數字去核對。先把 schema 自己對齊，再談設定檔"
        )
        return res

    for rel in (CONFIG_REL, CONFIG_EXAMPLE_REL):
        path = root / rel
        if not path.exists():
            res.failures.append(
                f"{rel} 不存在——本項比對的兩份設定檔少了一份。"
                f"把檔案補回來，或把它從本檢查的清單移除"
            )
            continue
        cfg = parse_config(read_text(path))
        version = cfg.get("foundry")
        if version != declared:
            res.failures.append(
                f"{rel} 的 `foundry` 是 {version!r}，而 {CONFIG_SCHEMA_REL} 宣告"
                f"現行版本是 `{declared}`——依「合法性總則」，讀取者遇到不認得的版本"
                "要停下報錯，不得猜著解析"
            )
        for name in sorted(required - set(cfg)):
            res.failures.append(
                f"{rel} 缺必填欄位 `{name}`——依 config-schema「合法性總則」"
                "整檔視為非法，依賴它的操作全部停擺，而讀取端只會說「缺欄位」"
            )
        for name in cfg:
            if name in fields:
                continue
            if name in RETIRED_CONFIG_FIELDS:
                res.failures.append(
                    f"{rel} 還在用舊欄位名 `{name}`，現名是 "
                    f"`{RETIRED_CONFIG_FIELDS[name]}`——舊名會被當成未知欄位丟掉，"
                    "於是必填欄位缺席、整檔非法。這是全有全無的失效，不是部分退化"
                )
            else:
                res.failures.append(
                    f"{rel} 有頂層欄位 `{name}`，但 {CONFIG_SCHEMA_REL} 的"
                    f"「{CONFIG_SCHEMA_TOP_HEADING}」表沒有它——不是打錯字，"
                    "就是加了欄位沒回頭改 schema（加欄位走 CEO 提案＋使用者核可）"
                )
        for name in sorted(enums):
            value = cfg.get(name)
            if isinstance(value, str) and value and value not in enums[name]:
                res.failures.append(
                    f"{rel} 的 `{name}` 是 `{value}`，值域是 "
                    f"{'｜'.join(enums[name])}（權威在 {CONFIG_SCHEMA_REL}）"
                )

    # `org.yml` 側的 `ai_platform`（MYL-85 AC8）。`org-sync` 只比對「兩份檔都有寫時
    # 值是否相同」，所以 `config.yml` 整欄沒寫的時候，`org.yml` 填 `banana` 也照樣
    # 通過——實測過。這裡補的是值域那一半，**不碰選填性**。
    org_path = root / ORG_REL
    if org_path.exists() and "ai_platform" in enums:
        try:
            org = parse_org(read_text(org_path))
        except LintError:
            org = {}    # 檔案形狀壞掉是 `org-sync` 的事，不在這裡重複報一次
        value = org.get("ai_platform")
        if isinstance(value, str) and value and value not in enums["ai_platform"]:
            res.failures.append(
                f"{ORG_REL} 的 `ai_platform` 是 `{value}`，值域是 "
                f"{'｜'.join(enums['ai_platform'])}（權威在 {CONFIG_SCHEMA_REL}）"
                f"——{CONFIG_REL} 沒寫這一欄時 `org-sync` 的兩檔比對不觸發，"
                "值域外的值於是整個沒人擋"
            )

    scanned = 0
    for rel in config_field_scan_targets(root):
        scanned += 1
        for lineno, key in foundry_config_fences(read_text(root / rel), required):
            if key in RETIRED_CONFIG_FIELDS:
                res.failures.append(
                    f"{rel}:{lineno} 的 yaml 範例還拿 `{key}` 當設定欄位，現名是 "
                    f"`{RETIRED_CONFIG_FIELDS[key]}`——照這段抄出來的設定檔會缺必填"
                    "欄位而整檔非法，而讀取端只會說「缺欄位」，不會說「你抄到的是舊名」"
                )
    # 值域數也印出來：值域靜默消失（分隔符改寫）除了形狀守衛擋一道，摘要行上也會
    # 當場現形——成本一個數字（MYL-111 審查 §4-4）。
    res.summary += (f"（schema v{declared}、{len(required)} 個必填欄位、"
                    f"{len(enums)} 組值域，掃 {scanned} 份文件）")
    return res


# ── `org-sync`：組織宣告 ↔ protocol 第 9／8 節（MYL-76）────────────────────
ORG_REL = ".foundry/org.yml"
#: 本檢查認得的 `foundry_org` 版本。改 schema 形狀時一起改，讓舊檔停下報錯而不是被誤讀。
ORG_SCHEMA_VERSION = "1"
#: `model_tier` 的值 → protocol 第 8 節「三層預設」表第一欄的字面。
ORG_MODEL_TIERS = {"high": "高", "medium": "中", "low": "低"}
#: `permissions[]` 的封閉值域（Foundry 級名稱；落到各平台哪個欄位見 config-schema）。
#: `configure_agents` 由 MYL-79 加入：它與前三個不同，在 Paperclip 上**只讀得到、寫不進去**
#: （沒有對應的面板布林，來源是建 agent 時自帶的 grant），所以它永遠只能是「登記現況」。
ORG_PERMISSIONS = ("assign_tasks", "configure_agents", "create_agents", "create_skills")
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

    `ai_platform` 的枚舉合法性歸 `config-schema`（那一項直接讀 config-schema.md 的
    值域，MYL-85 AC8），本檢查只驗兩份設定檔講的是同一件事——在程式裡另養一份枚舉，
    就是再造一個會漂的來源。
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

    # 重複只能靠「同一個 title 出現兩次」判定（MYL-85 AC7）。原本比的是
    # `len(titles) != len(by_id)`，而**缺 `title` 的角色同樣會讓左邊變短**——於是
    # 一份只是漏填 `title` 的 org.yml 會同時收到「缺必填欄位 `title`」與一句
    # 根本不存在的「有重複的 `title`」。不會造成假綠（只在檔案已經非法時一起出現），
    # 但那句話會把下一個人指去找一個不存在的重複。
    titles: dict = {}
    for rid, role in by_id.items():
        title = role.get("title")
        if not title:
            continue
        if title in titles:
            res.failures.append(
                f"{ORG_REL} `{rid}` 與 `{titles[title]}` 的 `title` 都是 `{title}`"
                "——組織圖靠它對接，不能重複"
            )
            continue
        titles[title] = rid
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
    # MYL-87／MYL-92：目標專案一份掛戳記的章節都沒有時整項跳過。判準**不是**
    # 另外兩項那支共用函式，理由見 `stamped_chapters_absent_skip()` 的 docstring。
    # 位置在最前面是刻意的：底下淺 clone 那一段講的是「有章節但驗不了歷史」，
    # 跟「根本沒有那幾章」是兩件事，混在一起會吐出一個指錯方向的處置。
    res.skipped = stamped_chapters_absent_skip(root)
    if res.skipped:
        res.summary += "（沒有掛戳記的章節，未驗）"
        return res
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


#: 區塊純量的起頭：`|`／`>` 加上可選的 chomping 指示符（`-`／`+`）。
#: **刻意不吃明確縮排指示符**（`|2`）——本 repo 沒有用到，而認得它卻不照它縮排
#: 只會讀出一個「看起來對」的錯值；認不得時退回原本的純量路徑，至少是顯性的怪值。
BLOCK_SCALAR_RE = re.compile(r"^(?P<style>[|>])[-+]?$")


def parse_config(text: str) -> dict:
    """把 `.foundry/config.yml` 讀成巢狀 dict。**刻意只支援本檔用得到的子集**。

    支援：`鍵: 純量`、`鍵:`（開一層巢狀）、`#` 註解、值兩側的引號，以及
    **區塊純量**（`|`／`>` 及其 `-`／`+` 變體）。
    不支援：陣列、錨點、流式寫法。踩到不支援的寫法時該鍵被忽略，
    而不是拋例外——這個 parser 的用途只有「取出幾個已知欄位」，不是驗整份設定檔。

    區塊純量是 MYL-130 補的，理由不是「順手多支援一種寫法」，而是**不補就會讀錯**：
    在此之前 `waiver_reason: >-` 會被讀成字面值 `">-"`（一個非空字串！），於是
    `model-routing-sync` 想擋的「掛了 `waives_m4` 卻沒寫理由」永遠擋不住——理由欄
    是空的也照樣非空。更糟的是續行被當成同層的鍵：`waiver_reason` 底下那句
    「2026-09-07 14:41」裡的冒號，讓 `claude-only` profile 憑空多出一個
    `27125d26，2026-09-07 14` 欄位。兩個症狀都是靜默的。

    折疊語意刻意只做到「夠判斷空與非空」：`>` 併行、`|` 保行，
    但 `-`／`+` 的收尾換行差異一律以 strip 收掉。本檔沒有任何一項檢查在意尾端換行。

    為什麼不用 PyYAML：`.github/workflows/foundry-lint.yml` 明寫 foundry-lint
    只用標準函式庫，讓閘門在任何環境都跑得起來。為了讀三個欄位引入依賴，
    等於拿掉那個保證。
    """
    root: dict = {}
    stack = [(-1, root)]
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
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
        block = BLOCK_SCALAR_RE.match(value)
        if block:
            # 區塊本體＝後續所有縮排比本行深的行（空行也算本體的一部分，不作為終止條件）。
            # `#` 在區塊本體裡是字面字元，不是註解——所以這裡刻意不剝註解。
            body = []
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and len(nxt) - len(nxt.lstrip(" ")) <= indent:
                    break
                body.append(nxt)
                i += 1
            if block.group("style") == ">":
                joined = " ".join(ln.strip() for ln in body)
            else:
                # `|` 保行，所以縮排得照 YAML 的規矩剝掉「本體的共同縮排」——
                # 由第一個非空行決定，而不是逐行 lstrip：逐行剝會把本體裡
                # 刻意的階層縮排一起弄平，而保行區塊用的就是那個階層。
                first = next((ln for ln in body if ln.strip()), "")
                strip_n = len(first) - len(first.lstrip(" "))
                joined = "\n".join(ln[strip_n:] if ln[:strip_n].isspace() else ln.lstrip(" ")
                                   for ln in body)
            parent[key] = joined.strip()
        elif value:
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


def ref_at_or_after(ref: str, since: str) -> bool:
    """`ref` 是否在 `since` 之後（含 `since` 本身）；`since` 為空＝不設界線。

    「規則從某一張單開始適用」是這個 repo 反覆出現的形狀（`mirror_since`、
    `ISSUE_RULES_SINCE`），判法都一樣，所以抽成一支：**比不出大小時一律納入**
    ——寧可誤報（看得見、修得掉），不要漏報（靜默，跟通過長得一模一樣）。
    """
    if not since:
        return True
    a, b = ref_sort_key(ref), ref_sort_key(since)
    if a is None or b is None or a[0] != b[0]:
        return True     # 比不出大小時一律納入：寧可誤報，不要漏報
    return a[1] >= b[1]


def in_mirror_scope(ref: str, since: str) -> bool:
    """`ref` 是否落在鏡像範圍內（`since` 起、含 `since` 本身）。

    `since` 是 MYL-54 的界線：本單只鏡像**新單**，既有舊單的回填屬批次對外
    動作、要另外核可。沒有這條界線，對帳一啟用就會把 50 幾張舊單全報成漏建，
    於是整項檢查在第一天就被當成雜訊關掉。
    """
    return ref_at_or_after(ref, since)


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


def paperclip_source_endpoint(cfg: dict):
    """來源端（Paperclip）的連線四件套；缺任一件回 `(None, 跳過理由)`。

    憑證走環境變數、company id 走 `.foundry/config.yml`（值可以是 `${VAR}`）。
    **CI 上必然缺憑證**——公開 runner 沒有 Paperclip token，也不該有；所以缺件是
    `skipped` 不是 `failure`（姿態的理由見 `SelfcheckResult` 的 docstring）。

    三項連線來源端的檢查（`mirror-recon`／`issue-authors`／`pm-issue-fields`）共用
    這一支，是為了讓「什麼情況算跳過」只有一份定義：三處各寫一次的話，哪天多支援
    一種憑證來源就會有兩處被漏掉，而漏掉的那一處**是靜默跳過**、看起來跟通過一樣。
    """
    opts = cfg.get("platform_options", {})
    pc_opts = opts.get("paperclip", {}) if isinstance(opts, dict) else {}
    base = (os.environ.get("PAPERCLIP_API_URL") or "").rstrip("/")
    base = base[:-4] if base.endswith("/api") else base
    token = os.environ.get("PAPERCLIP_API_KEY") or ""
    company_id = pc_opts.get("company_id", "")
    if company_id.startswith("${") and company_id.endswith("}"):
        company_id = os.environ.get(company_id[2:-1], "")
    if not (base and token and company_id):
        return None, ("讀不到來源端：缺 `PAPERCLIP_API_URL`／`PAPERCLIP_API_KEY`／"
                      "company id（CI 上必然如此，見 `paperclip_source_endpoint()` "
                      "的註解）")
    return (base, token, company_id, pc_opts.get("project_id", "")), ""


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

    endpoint, why = paperclip_source_endpoint(cfg)
    if endpoint is None:
        res.skipped = why
        return res
    base, token, company_id, project_id = endpoint

    sources, why = fetch_source_issues(
        base, token, company_id, project_id,
        gh_opts.get("mirror_since", ""), {m.ref for m in mirrors})
    if sources is None:
        res.skipped = f"讀不到來源端：{why}"
        return res

    res.failures.extend(reconcile_mirror(sources, mirrors, source_platform))
    res.summary += f"（來源端 {len(sources)} 張、鏡像端 {len(mirrors)} 張）"
    return res


# ── 開單規則的兩項事後檢查（MYL-116，依 MYL-96 裁定 #5／#6／#17）─────────────
#
# **兩項都是事後檢查、不是閘門**，而這不是實作偷懶：實查 Paperclip 的 21 個
# `permissionKey` **沒有任何 `issues:*`**（known-drift `L28`），平台上關不掉任何
# agent 的開單權，規則層也就沒有「擋得住」的位置可站。訊息措辭因此一律寫成
# 「已經發生了、去補救」，不得寫成「不允許」——把事後檢查說成閘門，讀的人會
# 以為違規開不出來，於是不再去看這一項的輸出。
#
#: `I1` 白名單的成員，以 `.foundry/org.yml` 的 `roles[].id` 表示；對照到平台上是
#: 各該角色的 `title`（＝平台 agent 的顯示名，見 `resolve_allowed_authors()`）。
#: **寫死在這裡而不是去解析條文散文**，體例同 `STAMPED_CHAPTERS`（MYL-92）：散文
#: 的措辭一改，解析就靜默失效；而這組值是使用者逐條裁定的（MYL-96 裁定 #17，卡
#: `651aaee9`），要改它本來就得再裁一次，不是順手改字。
#: 白名單第三個成員「使用者」不在這個常數裡——它不是 org.yml 上的角色，判法是
#: 「開單者的使用者欄有值」，見 `audit_issue_authors()`。
ISSUE_AUTHOR_ALLOWED_ROLE_IDS = ("ceo", "product-manager")

#: `I2` 只拘束 Product Manager 開的單，這是它在 org.yml 上的 `roles[].id`。
PM_ROLE_ID = "product-manager"

#: 兩項共同的起算點，姿態同 `mirror_since`（見 `ref_at_or_after()`）：規則生效前
#: 開的單不回溯。**這條界線不是「少看幾條紅燈」**——2026-09-06 實查 124 張單裡，
#: 有 37 張的開單者是 Scrum Master／Tech Lead／Developer／QA／Code Reviewer，全部
#: 早於本規則；而平台**沒有任何路徑改得動開單者**（known-drift `L28`），那 37 條
#: 紅字永遠修不掉，只會逼人把整項關掉——`mirror_since` 的註解講的是同一件事。
#: ⚠️ 值是「本規則落地後開的第一張單」。條文合併當下若最大單號已經越過它，這裡
#: 要跟著往後推；推之前先逐張確認中間那幾張確實不在射程內，不要只為了轉綠而推。
ISSUE_RULES_SINCE = "MYL-125"

#: `I1` 違規的**收斂出口**：覆核完成標記（MYL-116 CR 第 1 輪瑕疵 #1）。體例同
#: `MIRROR_SKIPPED_RE`——來源工單上留一則固定形狀的留言，本項讀到就不再報那一張。
#: **為什麼非有一條不可**：`I1` 認的是 `createdByAgentId`，那一格平台沒有任何更新
#: 路徑（known-drift `L28`），而 `--selfcheck` 掛在 pre-commit 的 `always_run` 上
#: ⇒ 沒有出口的話，一張違規單＝**所有 agent、所有 commit、永久被擋**，最後只會
#: 逼人把整項關掉——與 `ISSUE_RULES_SINCE` 註解講的是同一件事的兩端：那條線收的
#: 是規則上線前的舊單，這條出口收的是上線後真的發生的違規。
#: **它不是把違規抹掉**：留言與開單者欄位都留在單上，收斂掉的只有那條紅字。
#: ⚠️ 弱點與 `UPSTREAM_LINE_RE` 同一型：形狀寫死在這裡，措辭一改就靜默失效。
ISSUE_AUTHOR_CLEARED_RE = re.compile(r"^I1-覆核完成[：:]\s*\S", re.M)

#: 誰留的覆核完成標記才算數，以 `.foundry/org.yml` 的 `roles[].id` 表示。
#: **使用者一律算數**，不必列在這裡（判法是留言的使用者欄有值，見
#: `has_author_review_mark()`）——他是白名單第一位，也是 PM 缺席時的唯一出口。
#: 為什麼要限作者：不限的話，違規開單的那位自己補一行就把自己的紅字關掉了，
#: 這一項當場退化成打勾。`Mirror-skipped:` 不需要這一層——它聲明的是「這張刻意
#: 不鏡像」（誰講都一樣可查），這裡聲明的是「**另一個人**覆核過了」。
#: 值引用 `PM_ROLE_ID` 而不是再寫一次字面值：條文說的覆核者就是 `I2` 拘束的
#: 那一位，兩處各寫一次的話，角色 id 哪天改了會有一處被漏掉。
ISSUE_AUTHOR_REVIEWER_ROLE_IDS = (PM_ROLE_ID,)

#: `I3` 的頂層單宣告：agent 開的單刻意不掛上位單時，描述裡要有這一行。
#: 形狀與 `UPSTREAM_LINE_RE` 同族（行首粗體＋冒號＋同一行要有內容），但**這裡
#: 要的是理由、不是單號**——正是「掛不到任何一張單底下」才走這一條。
#:
#: ⚠️ **這一條與 `I1` 的覆核完成標記不是同一種東西，不要照它的樣子讀。**
#: `I1` 非有出口不可，是因為 `createdByAgentId` 沒有任何更新路徑（known-drift
#: `L28`）⇒ 違規單修不掉、紅字永久擋住所有人的 commit。`I3` **沒有這個問題**：
#: `parentId` 改得動（2026-09-07 實測，一次補掛 29 張），所以絕大多數違規的正解
#: 是**把上位單補上**，不是宣告。宣告留給真正掛不上去的那種單。
#:
#: 為什麼還是留一條：不留的話，一張真的無所歸屬的單只剩兩條路——掛到一個不相干
#: 的父單底下（為了轉綠而弄髒樹，而樹正是這條規則要保護的東西），或把整項關掉。
#: 留一條看得見、要寫理由的出口，比這兩條都好。
#: 為什麼收得窄：2026-09-07 全專案實查，agent 開的 **97 張單沒有一張是頂層單**
#: （97/97 都掛得到樹上，含 CEO 開的 60 張）。這一條因此是**預期為空的例外**——
#: 用到它就該被看見、被問一句，不是常態出口。「被看見」那半有機械兌現：走了這條
#: 出口的單會連張數帶單號印在 `issue-parent` 的 summary 裡（`toplevel_exception_note()`）。
ISSUE_TOPLEVEL_RE = re.compile(r"^\s*\*\*頂層單\*\*[：:]\s*\S", re.M)

#: `I2` 上游欄的欄位名。它**不是**單一個平台欄位，是「依賴欄非空 **或** 描述裡有
#: 那一行」的合成判準（見 `PmIssueFields.upstream`），所以取一個不叫 `blocked_by`
#: 的名字——叫 `blocked_by` 會讓下一個人以為它只讀那一格。
UPSTREAM_FIELD = "upstream"

#: `I2` 驗收標準那一欄的欄位名。取常數是為了讓訊息那一段（要告訴 PM 這一格認的
#: 是什麼形狀）與 `PM_REQUIRED_FIELDS` 指的是同一格，不靠字面字串對上。
AC_FIELD = "has_ac"

#: 上游欄的第二條路（使用者於卡 `2ed8d122` q1 選 B）：`blockedBy` 空著時，描述裡
#: 要有一行固定形狀寫出前置單編號。**為什麼要有第二條路**：實查 agent 開的 47 張
#: 無上游單，27 張的前置在開單當下就已經 `done`（填進去是一個開出來就已解除的
#: blocker，零阻擋），14 張的上游就是母單（填進去做出醒不來的單，正是
#: `PM_FORBIDDEN_FIELDS` 那一格擋的事）——它們**答得出來源，只是寫不進那一欄**。
#: ⚠️ 這一半是散文正則，兩個弱點要講在明處：措辭一改就靜默失效（體例同
#: `AC_SECTION_RE`），而且寫空話它擋不住——「那一行的內容是否成立」是【自律】。
#: 形狀因此收得窄：行首粗體「上游」＋冒號，且**同一行內要有單號**（`<前綴>-<數字>`）
#: ——只允許寫「無上游」之類的空話會讓這一格退化成打勾。
UPSTREAM_LINE_RE = re.compile(
    r"^\s*\*\*上游\*\*[：:][^\n]*[A-Za-z][A-Za-z0-9]*-\d+", re.M)

#: `I2` 的必備欄位：`(欄位, 報訊息時的稱呼)`。順序＝條文列舉的順序。
#: **原本是五欄，「下游被擋」拿掉了**（使用者於卡 `117b822a` q2 選 B）：那一欄
#: 開單者**填不動**——`issue_relations` 只有 `blocks` 一種關係型別，`blockedBy`
#: 與 `blocks` 是同一張表的兩個讀取方向，而全 API 只開放寫「下游那張單自己的
#: `blockedByIssueIds`」（known-drift `L29`）。要一張單的下游欄非空，只有一條路：
#: 後來有人開了單、把它填進自己的上游欄。⇒ 把它列進「開單當下要備齊」，是在
#: 要求先把下游單開出來或預測未來。它改成條文裡的【自律】句（見第 1 節 `I2`）。
PM_REQUIRED_FIELDS = (
    ("assignee", "指派對象"),
    ("parent", "上位單"),
    (UPSTREAM_FIELD, "上游依賴（擋住本單的單）"),
    (AC_FIELD, "驗收標準"),
)

#: `I2` 的反向欄位：值為真就是違規。刻意與 `PM_REQUIRED_FIELDS` 同形
#: （都是 `(欄位, 稱呼)`），兩族守衛才跑得了同一套反向突變證。
#: 目前只有一格：**上位單不得同時被填進上游依賴**。平台完全不擋這件事——
#: `syncBlockedByIssueIds()` 只有三道守衛（不得自我阻擋、必須同公司、`blocks`
#: 圖不得成環），父子關係不在其中（known-drift `L29`）——但它會做出一張**醒不來
#: 的單**：blocker 只有停在 `done` 才算解除，而母單多半要等子單做完才結。
PM_FORBIDDEN_FIELDS = (
    ("parent_is_blocker", "上位單同時被填進上游依賴"),
)

#: 描述欄裡的「驗收標準」段（第 1 節四段骨架的第三段）。只認粗體標題那一行，
#: 與 `templates/` 與第 1 節寫的骨架同形；散文裡提到「驗收標準」四個字不算。
AC_SECTION_RE = re.compile(r"^\s*\*\*驗收標準\*\*\s*$", re.M)


@dataclass(frozen=True)
class AuthoredIssue:
    """來源端一張單的「誰開的」。

    **兩個欄位皆空＝平台自建**（例如生產力審查單），`I1` 明文收容——那不是任何
    角色的動作，收不進白名單，也修不掉。

    `issue_id` 是平台的 uuid（`ref` 是看得懂的那個編號）。留著它是因為三件事都得
    拿 uuid 去打端點：`I1` 違規時要翻該單的留言找覆核完成標記，`I2` 要逐張撈欄位，
    `I3` 要對沒有上位單的那幾張翻描述找頂層單宣告。

    `parent` 是 `I3` 用的上位單 uuid，**清單端點就給得出來**，所以判「有沒有掛到
    樹上」不必多打任何一次 API。真正要多打的只有頂層單宣告那一格（見
    `ISSUE_TOPLEVEL_RE`）：宣告住在描述裡，而清單端點的 `description` **截在
    1200 字**（2026-09-07 實測：MYL-124 清單 1200／單筆 3046），拿清單那份找宣告
    會把寫在後半的宣告讀成不存在＝假紅。
    """

    ref: str
    author_agent: str = ""
    author_user: str = ""
    issue_id: str = ""
    parent: str = ""


@dataclass(frozen=True)
class PmIssueFields:
    """`I2` 要看的幾格。`blocked_by` 存的是依賴**條數**，零＝那一欄空著。

    上游欄的判準是 `upstream`（合成的，見下）而不是 `blocked_by` 本身：兩條路
    都算交代，raw 的那兩格分開存才驗得出「是哪一條路過的」。
    `parent_is_blocker` 不是「有沒有填」而是「填錯了沒有」，判在
    `PM_FORBIDDEN_FIELDS` 那一族。
    """

    ref: str
    assignee: str = ""
    parent: str = ""
    blocked_by: int = 0
    upstream_line: bool = False
    has_ac: bool = False
    parent_is_blocker: bool = False

    @property
    def upstream(self) -> bool:
        """上游欄過不過：依賴欄非空，**或**描述裡有 `UPSTREAM_LINE_RE` 那一行。

        `parentId` 刻意**不算**第三條路：它已經是必備欄位裡的「上位單」，拿它
        來抵上游欄，那個「或」就永遠成立、抓漏力歸零（同一個病因報兩次而已）。
        """
        return bool(self.blocked_by) or self.upstream_line


def issue_author_violations(issues: list, allowed: dict, since: str) -> list:
    """純函式：挑出射程內、開單者不在 `I1` 白名單的單（還沒看覆核標記）。

    與組訊息那支拆開，是為了讓「覆核完成標記」只對**這幾張**去翻留言——體例同
    `fetch_source_issues()` 只對看起來漏建的單翻留言：對每張單都翻等於 N 次呼叫，
    而絕大多數單根本不在射程內。
    """
    out = []
    for it in issues:
        if not ref_at_or_after(it.ref, since):
            continue
        if it.author_user:
            # 白名單第一位：使用者。**目前不可達**——實查 124 張單沒有一張兩欄
            # 同時有值，使用者開的單 `createdByAgentId` 一律 null，會被下一行的
            # 「平台自建」收容接走。留著是防「哪天平台改成兩欄都填」那種形狀；
            # ⚠️ 它是 fail-open（那時白名單外的 agent 代開會被放行），真出現了
            # 要回頭改成「兩欄都看」而不是只信這一行。
            continue
        if not it.author_agent:
            continue                        # 平台自建，`I1` 明文收容
        if it.author_agent in allowed:
            continue
        out.append(it)
    return out


def audit_issue_authors(issues: list, allowed: dict, names: dict, since: str,
                        cleared=None) -> list:
    """純函式：`I1` 白名單對帳，回傳 failure 訊息清單。

    `allowed`／`names` 都是 `{agent id: 顯示名}`；前者是白名單、後者是全編制
    （用來把違規訊息裡的 id 換成讀得懂的名字）。**白名單依傳入順序印**（呼叫端
    給的是 `ISSUE_AUTHOR_ALLOWED_ROLE_IDS` 的宣告順序）——照 agent uuid 排的話，
    同一句話在不同環境會印出不同順序，讀紅字的人以為規則變了。

    `cleared(it) -> bool` 是可選的「這張的覆核完成標記在不在」查詢，**只會對違規
    的那幾張呼叫**（見 `issue_author_violations()`）。不傳＝不查，一律當作沒有：
    純函式測試因此不必假造留言，連線那條路才把它接上去。
    """
    failures = []
    allowed_label = "／".join(["使用者"] + [allowed[k] for k in allowed])
    for it in issue_author_violations(issues, allowed, since):
        if cleared is not None and cleared(it):
            continue
        who = names.get(it.author_agent) or f"`{it.author_agent}`"
        failures.append(
            f"{it.ref} 的開單者是「{who}」，不在 `I1` 的白名單（{allowed_label}）"
            "——`I1` 是事後檢查不是閘門，這張單已經開出來了。處置是把它交回 "
            "Product Manager 覆核、依 `D1`～`D4` 判要不要退回原單；"
            "**不要刪單、也改不了作者**（平台沒有更新開單者的路徑，known-drift `L28`）。"
            "覆核完成後由覆核者（Product Manager，或使用者本人）在該單留一則 "
            "`I1-覆核完成：<判了什麼>` 的留言，本項就不再報它——**那是唯一的收斂"
            "路徑**，不要改起算點、不要把單藏起來"
        )
    return failures


def issue_parent_violations(issues: list, since: str) -> list:
    """純函式：挑出射程內、agent 開的、沒有上位單的單（還沒看頂層單宣告）。

    與組訊息那支拆開的理由同 `issue_author_violations()`：頂層單宣告住在描述裡，
    要再打一次單筆端點才讀得到未截斷的全文（清單端點截在 1200 字），而**絕大多數
    單都有上位單**，只對這幾張翻才不會每次 `make check` 多打 N 次 API。

    三道排除各自的依據不同，**不要合併成一句「開單者不是 agent 就跳過」**：
    - `author_user`：**裁定 B1**——使用者自建的單不在射程內。這與 `I1` 那支
      「使用者是白名單第一位」不是同一個理由：那裡說的是「他開單合法」，這裡
      說的是「他的單我們一張都不動」（MYL-96 核可卡 `10db376e`）。使用者是從
      系統外面開單的，他的單就是這棵樹的根，要求它們掛到別的單底下沒有意義。
    - `author_agent` 空：平台自建（生產力審查單那一型），同 `I1` 明文收容——
      不是任何角色的動作，收不進規則、也沒有人修得動。
    - `parent` 非空：已經掛在樹上，本項不管它掛得對不對（掛錯父單是內容問題，
      機械判不了；本項只判「有沒有掛」）。
    """
    out = []
    for it in issues:
        if not ref_at_or_after(it.ref, since):
            continue
        if it.author_user:
            continue                        # 裁定 B1：使用者自建的單不在射程內
        if not it.author_agent:
            continue                        # 平台自建，同 `I1` 明文收容
        if it.parent:
            continue                        # 已經掛在樹上
        out.append(it)
    return out


def audit_issue_parents(issues: list, since: str, declared=None) -> list:
    """純函式：`I3` 上位單對帳，回傳 failure 訊息清單。

    `declared(it) -> bool` 是可選的「這張的頂層單宣告在不在」查詢，**只會對違規
    的那幾張呼叫**（見 `issue_parent_violations()`）。不傳＝不查，一律當作沒有：
    純函式測試因此不必假造描述，連線那條路才把它接上去。姿態與 `cleared` 同。

    只要 failure 那一半的呼叫端用這支；連線那條路走
    `partition_issue_parents()`，因為它**還要把走例外的那幾張印出來**。
    """
    missing, _ = partition_issue_parents(issues, since, declared)
    return [issue_parent_failure(it) for it in missing]


def partition_issue_parents(issues: list, since: str, declared=None) -> tuple:
    """純函式：射程內沒有上位單的單，分成 `(要報的, 走頂層單例外的)` 兩堆。

    **分兩堆而不是把例外那堆丟掉**，是 MYL-117 CR 第 1 輪瑕疵 #1：protocol 的
    `I3` 寫「用到這條例外的單應該被看見、被問一句」，而例外的出口寫在**描述**
    裡——描述沒有作者欄、開單者本人 PATCH 得動（`allow_self`），所以它與 `I1`
    的覆核標記相反，是**可自我特赦的**。直接 `continue` 掉等於那句話在機械層
    是空頭支票：寫一行 `**頂層單**：因為我不想掛` 紅字就消失且無人得知。
    放行照舊（例外本來就該放行），改的只是**它不再是靜默的**。

    `declared` 每張**只呼叫一次**：連線那條路它是一次單筆端點呼叫，分兩次問
    等於把 API 次數翻倍。
    """
    missing, exempt = [], []
    for it in issue_parent_violations(issues, since):
        (exempt if declared is not None and declared(it) else missing).append(it)
    return missing, exempt


def issue_parent_failure(it, unreadable: str = "") -> str:
    """一張沒有上位單的單的紅字。

    訊息刻意把「補上位單」擺在「宣告」前面：兩條路都收斂得掉紅字，但預設答案是
    補掛（`parentId` 改得動），宣告是例外。順序寫反了，讀紅字的人會先去寫宣告。

    `unreadable`＝這一輪根本沒讀到該單描述時的**原因**（CR 第 1 輪次要建議 #1）。
    判準本身不變（讀不到就照樣報，漏報看不見、誤報看得見），但**訊息要跟著
    分岔**：否則連線瞬斷時，一張宣告早就寫好的單會拿到一段叫它「去加一行宣告」
    的紅字，讀的人照做完才發現本來就有。原因原樣帶出來而不是寫成一句籠統的
    「讀不到」——連線瞬斷（重跑就好）與 404／403（要去查別的東西）是兩回事。
    """
    msg = (
        f"{it.ref} 是 agent 開的單，卻沒有上位單（`I3`）"
        "——每一張 agent 開的單都要掛得到樹上，否則它不屬於任何一條工作線，"
        "看板上找不到、結案時也沒有人會回頭看它。"
        "處置**優先是把上位單補上**：`parentId` 改得動（`PATCH /api/issues/{id}`），"
        "依據就寫在該單描述裡——它多半是某張單的審查、溢出或衍生。"
        "真的掛不到任何一張單底下（整條工作線的起點）才走例外："
        "在描述裡加一行 `**頂層單**：<為什麼它不屬於任何現有工作線>`，"
        "本項讀到就不再報它。**不要為了轉綠把它掛到不相干的父單底下**"
        "——那是把樹弄髒來換一個綠燈，而樹正是這一條要保護的東西"
    )
    if unreadable:
        msg += (f"。⚠️ 本輪**讀不到這張單的描述**（{unreadable}），宣告在不在"
                "其實沒判成——宣告若已經寫好，重跑一次這則就會消失，不必再加一行")
    return msg


def toplevel_exception_note(exempt: list) -> str:
    """summary 尾巴那句「有幾張走了頂層單例外、是哪幾張」；沒人用時回空字串。

    **這一條預期為空**（protocol `I3`：2026-09-07 實查，agent 開的 97 張沒有一張
    是頂層單，原因是結構性的——agent 是在系統裡面對既有的單作反應）。所以印得
    出東西來，本身就是那個「要被問一句」的訊號。

    單號**全列不截斷**：截掉尾巴會讓「被看見」退化成「知道有人用了但不知道是
    誰」，而要去覆核的正是那幾張。真的多到一行放不下，那件事本身就該被問。
    """
    if not exempt:
        return ""
    return (f"——其中 {len(exempt)} 張走頂層單例外："
            + "、".join(it.ref for it in exempt)
            + "。這一條預期為空，請覆核它們真的各自是一條工作線的起點"
              "（宣告寫在描述裡、開單者自己改得動，機械只驗形狀不驗理由）")


def has_toplevel_declaration(description: str) -> bool:
    """描述裡有沒有一則成立的頂層單宣告（`I3` 的例外出口）。

    只看形狀（`ISSUE_TOPLEVEL_RE`），**不看誰寫的**——這一點與 `I1` 的覆核完成
    標記刻意不同：那裡聲明的是「**另一個人**覆核過了」，所以非限作者不可（不限
    的話違規者自己補一行就自我特赦）；這裡聲明的是「這張單的位置在哪」，那是
    開單者本來就該回答的事，誰寫的都一樣可查、也一樣可被推翻。
    ⚠️ 弱點同 `UPSTREAM_LINE_RE`：形狀寫死、措辭一改就靜默失效，而**內容是否
    成立機械驗不了**（寫「因為我不想掛」它也擋不住）——那一半靠自律與審查。
    """
    return bool(ISSUE_TOPLEVEL_RE.search(description or ""))


def fetch_toplevel_declaration(base: str, token: str, issue_id: str) -> tuple:
    """單筆端點撈該單描述、判頂層單宣告在不在；回傳 `(宣告在不在, 讀不到的原因)`。

    **非得走單筆端點不可**：清單端點的 `description` 截在 1200 字（2026-09-07
    實測 MYL-124：清單 1200／單筆 3046），宣告若寫在後半，拿清單那份會讀成
    不存在＝假紅，而且是**愈長的單愈容易誤判**——那正是最需要宣告的那種單。
    （清單端點另有 `descriptionTruncated` 旗標，`false` 時本來可以省下這一次
    呼叫；只對違規單觸發、量小，先不用它，寫在這裡是為了下一個人不必再查一次。）

    讀不到時回 `False`（＝照樣報出來）：漏報看不見，誤報看得見。第二格帶回
    原因**只餵訊息不餵判準**——見 `issue_parent_failure()` 的 `unreadable`。
    """
    data, why = api_get(base, f"/api/issues/{issue_id}", token)
    if data is None:
        return False, why or "讀不到該單描述"
    issue = data.get("issue", data) if isinstance(data, dict) else {}
    return has_toplevel_declaration(issue.get("description") or ""), ""


def has_author_review_mark(comments: list, reviewer_ids) -> bool:
    """留言裡有沒有一則成立的「覆核完成標記」（`I1` 的收斂出口）。

    兩個條件都要成立：**形狀對**（`ISSUE_AUTHOR_CLEARED_RE`），而且**是覆核者留
    的**——使用者，或 `reviewer_ids` 裡的 agent（＝Product Manager）。限作者的
    理由見 `ISSUE_AUTHOR_REVIEWER_ROLE_IDS`。

    ⚠️ 判「使用者留的」只能看 `authorUserId`／`authorType`，**不能看
    `onBehalfOfUserId`**——agent 留的留言那一格也有值（實測本單的留言全數如此），
    拿它判等於任何 agent 都能自我特赦。已刪除的留言（`deletedAt` 有值）不算。
    """
    for c in comments or []:
        if not isinstance(c, dict) or c.get("deletedAt"):
            continue
        if not ISSUE_AUTHOR_CLEARED_RE.search(c.get("body") or ""):
            continue
        if c.get("authorUserId") or c.get("authorType") == "user":
            return True
        if c.get("authorAgentId") in reviewer_ids:
            return True
    return False


def fetch_author_review_mark(base: str, token: str, issue_id: str,
                             reviewer_ids) -> bool:
    """撈單張單的留言，判有沒有覆核完成標記。

    撈不到就當作沒有——**失效方向是安全的**：紅字留著（看得見），不是靜靜轉綠。
    """
    comments, _ = api_get(base, f"/api/issues/{issue_id}/comments", token)
    return has_author_review_mark(comments, reviewer_ids)


def audit_pm_issue_fields(issues: list) -> list:
    """純函式：`I2` 欄位對帳，回傳 failure 訊息清單。

    傳進來的**已經只剩 Product Manager 開的單**（誰開的在上一支判完了）：本支
    只回答「這幾欄對不對」，兩件事分開才不會在射程與判準之間互相蓋掉。

    兩族守衛：`PM_REQUIRED_FIELDS` 是「沒填就報」，`PM_FORBIDDEN_FIELDS` 是
    「填了就報」。同一張單兩族都犯規時**合成一則訊息**，理由同下面那句註解：
    一張單一則，接單者不必在紅字裡把同一個 ref 拼回去。
    """
    failures = []
    for it in issues:
        missing = [(attr, label) for attr, label in PM_REQUIRED_FIELDS
                   if not getattr(it, attr)]
        wrong = [label for attr, label in PM_FORBIDDEN_FIELDS if getattr(it, attr)]
        if not missing and not wrong:
            continue
        parts = []
        if missing:
            parts.append(
                f"缺了：{'、'.join(label for _, label in missing)}"
                "——每缺一欄，接單者開工後就要多問一次，"
                "那正是這條規則要收掉的來回（MYL-96 裁定 #6）"
            )
        if any(attr == UPSTREAM_FIELD for attr, _ in missing):
            parts.append(
                "上游欄有第二條路：前置在開單當下已經結案、或上游就是母單而填不得時，"
                "在描述裡寫一行 `**上游**：前置 MYL-97 已結案，本單可獨立開工`"
                "（要寫得出單號）就算交代"
            )
        if any(attr == AC_FIELD for attr, _ in missing):
            parts.append(
                "驗收標準那一欄認的形狀是描述裡**一行粗體 `**驗收標準**`**"
                "（第 1 節四段骨架的第三段）——寫成 `## AC1` 這類標題、或在散文裡"
                "提到「驗收標準」四個字都不算"
            )
        if wrong:
            parts.append(
                f"填錯了：{'、'.join(wrong)}——母單要等子單做完才結，"
                "而 blocker 只有停在 `done` 才算解除，兩邊互等就是一張醒不來的單。"
                "母單已經用上位單欄表達了，不要再掛一條 blocker 邊"
            )
        failures.append(
            f"{it.ref} 由 Product Manager 開出，但 `I2` 的欄位判準沒過："
            + "；".join(parts)
            + "。認為這張單本來就不該這樣填，走第 1 節修訂條文，"
            "不要在個案裡放寬"
        )
    return failures


def resolve_allowed_authors(root: Path, agents: list) -> tuple:
    """把 `ISSUE_AUTHOR_ALLOWED_ROLE_IDS` 解成
    `({角色 id: (平台 agent id, 顯示名)}, {全編制 agent id: 顯示名}, 錯誤)`。

    第一格以**角色 id** 為鍵而不是 agent id：兩項檢查裡有一項（`I2`）的射程是
    「其中一個角色」，用角色當鍵才不必在呼叫端再從顯示名倒推回角色。

    對照鍵是 **org.yml 的 `title` ↔ 平台 agent 的 `name`**。用宣告面當來源而不是
    在這裡再寫死一次角色名，是為了讓正名自動跟上：MYL-115 把 `PM` 正名成
    `Product Manager` 時，只要 org.yml 改了，本檢查就跟著改對象。
    反過來，**平台上找不到對應 agent 時回錯誤而不是靜靜略過**——那正是「宣告面
    改了、平台面沒跟」的漂移，靜靜略過會讓白名單少一格而沒有人發現。
    """
    org_path = root / ORG_REL
    if not org_path.exists():
        return {}, {}, f"{ORG_REL} 不存在，解不出白名單對應到平台上的哪幾名"
    try:
        org = parse_org(read_text(org_path))
    except LintError as e:
        return {}, {}, str(e)

    titles = {r.get("id"): r.get("title") for r in org.get("roles", [])}
    names = {a.get("id"): a.get("name") for a in agents if a.get("id")}
    by_name = {a.get("name"): a.get("id") for a in agents if a.get("id")}
    allowed = {}
    for rid in ISSUE_AUTHOR_ALLOWED_ROLE_IDS:
        title = titles.get(rid)
        if not title:
            return {}, {}, (f"{ORG_REL} 沒有宣告角色 `{rid}`，而 `I1` 的白名單以它為成員"
                            "——組織宣告與白名單常數對不上，先確認哪一邊該改")
        if title not in by_name:
            return {}, {}, (f"平台編制裡找不到顯示名為「{title}」的 agent"
                            f"（{ORG_REL} 宣告角色 `{rid}` 的 `title`）"
                            "——正名沒同步到平台，或該角色還沒建置")
        allowed[rid] = (by_name[title], title)
    return allowed, names, ""


def fetch_company_agents(base: str, token: str, company_id: str):
    """撈平台編制。回傳 `(list, 錯誤)`；端點形狀見 known-drift `L6`。"""
    data, why = api_get(base, f"/api/companies/{company_id}/agents", token)
    if data is None:
        return None, why
    agents = data.get("agents") if isinstance(data, dict) else data
    if not isinstance(agents, list):
        return None, "編制端點沒有回陣列"
    return agents, ""


def fetch_authored_issues(base: str, token: str, company_id: str, project_id: str):
    """撈來源端每張單的「誰開的」。分頁前提同 `fetch_source_issues()`（沒有分頁）。

    **兩項檢查共用這一支**（`I1` 判白名單、`I2` 用它篩出 PM 開的單）：清單撈取
    ＋三道過濾（`projectId`／`hiddenAt`／空 `identifier`）各寫一次的話，哪天多一道
    過濾就會有一處被漏掉——這正是抽 `paperclip_source_endpoint()` 時寫的那把尺
    （MYL-116 CR 第 1 輪次要建議 #2：當時 `I2` 那份就漏了空 `identifier` 那道，
    一張沒有編號的單會吐出開頭是空白的紅字）。
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
        if not ref:
            continue
        out.append(AuthoredIssue(ref=ref,
                                 author_agent=it.get("createdByAgentId") or "",
                                 author_user=it.get("createdByUserId") or "",
                                 issue_id=it.get("id") or "",
                                 parent=it.get("parentId") or ""))
    return out, ""


def fetch_pm_issue_fields(base: str, token: str, issue_id: str, ref: str):
    """撈單張單的 `I2` 欄位。回傳 `(PmIssueFields, 錯誤)`。

    **必須逐張打單筆端點**，不能沿用清單端點的欄位：清單回的每一筆**沒有**依賴
    關係（`blockedBy` 這一鍵缺席），描述欄還可能被截斷（`descriptionTruncated`）
    ——拿清單那份去判，依賴欄會恆為空，而 AC 與上游那一行都在描述裡，被截掉就
    會誤報成漏寫（上游欄兩條路同時失真，等於整格恆紅）。
    代價是每張 PM 開的單多一次呼叫，而射程只有 PM 開的單，量級不成問題。

    `parent_is_blocker` 比對的是 **`blockedBy[].id` 與 `parentId`**（都是 uuid），
    不是看得懂的 `identifier`——後者只在少數回應裡出現，拿它比會靜默漏判。
    """
    data, why = api_get(base, f"/api/issues/{issue_id}", token)
    if data is None:
        return None, why
    it = data.get("issue", data) if isinstance(data, dict) else {}
    if not isinstance(it, dict):
        return None, f"{ref} 的單筆端點沒有回物件"
    parent = it.get("parentId") or ""
    blocked_by = it.get("blockedBy") or []
    blocker_ids = {b.get("id") for b in blocked_by if isinstance(b, dict)}
    description = it.get("description") or ""
    return PmIssueFields(
        ref=ref,
        assignee=it.get("assigneeAgentId") or it.get("assigneeUserId") or "",
        parent=parent,
        blocked_by=len(blocked_by),
        upstream_line=bool(UPSTREAM_LINE_RE.search(description)),
        has_ac=bool(AC_SECTION_RE.search(description)),
        parent_is_blocker=bool(parent) and parent in blocker_ids,
    ), ""


def issue_rules_precondition(root: Path):
    """兩項共用的前置：平台、離線旗標、憑證。回傳 `(連線四件套, 跳過理由)`。"""
    cfg = read_config(root)
    if cfg.get("devtools_platform", "") != "paperclip":
        return None, ("本項讀的是來源端「誰開的單」，目前只有 paperclip adapter 有"
                      f"對應欄位（`devtools_platform: {cfg.get('devtools_platform') or '未設定'}`）")
    if os.environ.get(MIRROR_OFFLINE_ENV):
        return None, f"{MIRROR_OFFLINE_ENV} 已設，本次不連線"
    endpoint, why = paperclip_source_endpoint(cfg)
    if endpoint is None:
        return None, why
    return endpoint, ""


def check_issue_authors(root: Path) -> SelfcheckResult:
    """開單者要落在 `I1` 的白名單內：使用者、CEO、Product Manager（MYL-116）。

    起算點是 `ISSUE_RULES_SINCE`，理由寫在該常數的註解。
    """
    res = SelfcheckResult("issue-authors", "開單者落在 `I1` 白名單內")
    endpoint, why = issue_rules_precondition(root)
    if endpoint is None:
        res.skipped = why
        return res
    base, token, company_id, project_id = endpoint

    agents, why = fetch_company_agents(base, token, company_id)
    if agents is None:
        res.skipped = f"讀不到平台編制：{why}"
        return res
    allowed, names, err = resolve_allowed_authors(root, agents)
    if err:
        res.failures.append(err)
        return res

    issues, why = fetch_authored_issues(base, token, company_id, project_id)
    if issues is None:
        res.skipped = f"讀不到來源端：{why}"
        return res

    reviewer_ids = {allowed[rid][0] for rid in ISSUE_AUTHOR_REVIEWER_ROLE_IDS
                    if rid in allowed}
    res.failures.extend(audit_issue_authors(
        issues, dict(allowed.values()), names, ISSUE_RULES_SINCE,
        cleared=lambda it: bool(it.issue_id) and fetch_author_review_mark(
            base, token, it.issue_id, reviewer_ids)))
    in_scope = [i for i in issues if ref_at_or_after(i.ref, ISSUE_RULES_SINCE)]
    res.summary += (f"（{ISSUE_RULES_SINCE} 起 {len(in_scope)} 張，"
                    f"全部 {len(issues)} 張）")
    return res


def check_pm_issue_fields(root: Path) -> SelfcheckResult:
    """Product Manager 開的單，必備欄位要齊、上位單不得同時當 blocker（`I2`，MYL-116）。

    射程只有 PM 開的單，且同樣從 `ISSUE_RULES_SINCE` 起算。
    """
    res = SelfcheckResult("pm-issue-fields", "Product Manager 開的單欄位齊備且沒填錯")
    endpoint, why = issue_rules_precondition(root)
    if endpoint is None:
        res.skipped = why
        return res
    base, token, company_id, project_id = endpoint

    agents, why = fetch_company_agents(base, token, company_id)
    if agents is None:
        res.skipped = f"讀不到平台編制：{why}"
        return res
    allowed, _, err = resolve_allowed_authors(root, agents)
    if err:
        res.failures.append(err)
        return res
    pm_id = allowed[PM_ROLE_ID][0]

    issues, why = fetch_authored_issues(base, token, company_id, project_id)
    if issues is None:
        res.skipped = f"讀不到來源端：{why}"
        return res

    fields, unreadable = [], []
    for it in issues:
        if it.author_agent != pm_id or not ref_at_or_after(it.ref, ISSUE_RULES_SINCE):
            continue
        one, why = fetch_pm_issue_fields(base, token, it.issue_id, it.ref)
        if one is None:
            # **不中斷、也不整項轉 skipped**：整項跳過等於 `passed`，那幾張真的
            # 缺欄位的紅字這一輪就不見了（MYL-116 CR 第 1 輪次要建議 #1）。
            # 記成 failure 的代價是暫時性錯誤會擋一次 commit——但它下一輪自己會
            # 消，而漏報不會。
            unreadable.append(f"{it.ref} 的欄位讀不到，本輪判不了：{why}"
                              "（其餘幾張的結果照常在下面；這一則下一輪會自己消失）")
            continue
        fields.append(one)

    res.failures.extend(audit_pm_issue_fields(fields))
    res.failures.extend(unreadable)
    res.summary += f"（{ISSUE_RULES_SINCE} 起 PM 開了 {len(fields) + len(unreadable)} 張）"
    return res


# ── `model-routing-sync`：`model_routing` 段的內部自洽性（MYL-130，MYL-125 的 C3）──
#: 供應商 id 的值域來源。**不 import 這個模組、改用 `ast` 靜態取值**：foundry-lint
#: 跑在 pre-commit 裡，import 一個平行工具等於把它的 import 副作用也綁進閘門。
PROVIDERS_REL = "tools/model-routing/probe_providers.py"
PROVIDERS_SYMBOL = "PROVIDERS"
#: `model_routing` 段的合法欄位，權威在 `config-schema.md` 的同名節。
#: 認得的鍵寫成白名單而不是「檢查幾個已知欄位」——多打一個 `waiver_resaon`
#: 在後者底下會靜靜地變成「沒寫理由」以外的第三種狀態：既不擋、也沒生效。
MR_PROFILE_FIELDS = frozenset({
    "default_provider", "roles", "review_provider_distinct", "emergency",
    "waives_m4", "waiver_reason",
})
#: 布林欄位。值只認 `true`／`false` 兩個字面——`yes`／`True` 一律報錯而不是猜，
#: 猜錯的方向永遠是「當成 false」，也就是靜靜地把一項豁免或一道強制取消掉。
MR_BOOL_FIELDS = ("review_provider_distinct", "emergency", "waives_m4")
#: `M4` 拘束的那兩個角色，以 `.foundry/org.yml` 的 `roles[].id` 表示。
MR_IMPL_ROLE = "developer"
MR_REVIEW_ROLE = "code-reviewer"
#: profile 名的形狀（同 config-schema「名字形狀 `[a-z][a-z0-9-]*`」）。
MR_PROFILE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def provider_ids(text: str) -> list:
    """`probe_providers.py` 的 `PROVIDERS` 登記表裡的 `id`，依原順序。

    用 `ast` 而不是正規表達式：`id` 這兩個字母在那份檔案裡到處都是，
    regex 版本會把註解和別的 dict 一起撈進來，於是值域悄悄變大——
    而值域一變大，本檢查(c) 就開始放行它本來該擋的東西。

    取不到（符號不在、不是常值序列）時**回空 list，由呼叫端報錯**，
    不要退回一份寫死的值域：那份寫死的會漂，而漂掉的那天沒有人會收到通知。
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == PROVIDERS_SYMBOL
                   for t in node.targets):
            continue
        if not isinstance(node.value, (ast.Tuple, ast.List)):
            return []
        ids = []
        for item in node.value.elts:
            if not isinstance(item, ast.Dict):
                continue
            for k, v in zip(item.keys, item.values):
                if (isinstance(k, ast.Constant) and k.value == "id"
                        and isinstance(v, ast.Constant) and isinstance(v.value, str)):
                    ids.append(v.value)
        return ids
    return []


def audit_model_routing(routing: dict, role_ids, providers) -> list:
    """`model_routing` 段對照 `org.yml` 角色與供應商登記表，回傳失敗訊息。

    合法性逐條照 `config-schema.md`「`model_routing`」一節末的清單，**每個 profile
    都驗，不只 active 那個**——非 active 的 profile 存在的理由就是「隨時可以切過去」，
    等切過去那一刻才發現它非法，正好卡在最不能停下來的時候（額度牆下）。
    """
    failures = []
    role_ids, providers = set(role_ids), set(providers)
    profiles = routing.get("profiles")
    active = routing.get("active")

    if not isinstance(profiles, dict) or not profiles:
        failures.append(
            f"{CONFIG_REL} 的 `model_routing.profiles` 缺席或為空——"
            "有 `model_routing` 段就代表路由已啟用，至少要有一個 profile"
        )
        profiles = {}
    if isinstance(active, dict):
        # 這條擺在成員判定之前：`active` 寫成區塊時 `active not in profiles`
        # 是 `dict in dict`，拋 `TypeError` 而不是回 False。`run_selfcheck`
        # 沒有逐項例外隔離，那個 traceback 會讓**整份 `--selfcheck` 中止**，
        # 排在本項後面的自檢一項都不跑——設定寫錯一格，換來的是所有閘門一起失效。
        failures.append(
            f"{CONFIG_REL} 的 `model_routing.active` 是一個區塊——"
            "它要填的是「目前生效的是哪一個 profile」，值只能是單一 profile 的鍵"
            "（`active: normal-mixed`），不是一份 profile 的內容"
        )
    elif not active:
        failures.append(
            f"{CONFIG_REL} 的 `model_routing.active` 缺席——"
            "有本段時它必填，指出目前生效的是哪一個 profile"
        )
    elif profiles and active not in profiles:
        failures.append(
            f"{CONFIG_REL} 的 `model_routing.active` 是 `{active}`，"
            f"但 `profiles` 裡沒有這個鍵（有的是 {'、'.join(sorted(profiles))}）"
            "——不得退回「就用第一個 profile」之類的猜測：猜錯的那一次，"
            "全隊會跑在一套沒有人選過的配置上，而每一份輸出看起來都正常"
        )

    for name, profile in sorted(profiles.items()):
        at = f"{CONFIG_REL} 的 profile `{name}`"
        if not isinstance(profile, dict):
            failures.append(f"{at} 不是一個物件——每個 profile 底下至少要有 `default_provider`")
            continue
        if not MR_PROFILE_NAME_RE.match(name):
            failures.append(
                f"{at} 的名字不合形狀 `[a-z][a-z0-9-]*`，"
                "且名字要說得出「什麼情況下用它」（`codex-emergency`、`normal-mixed`）"
            )
        for field_name in sorted(set(profile) - MR_PROFILE_FIELDS):
            failures.append(
                f"{at} 有不認得的欄位 `{field_name}`——"
                f"合法欄位見 config-schema「model_routing」一節（{'、'.join(sorted(MR_PROFILE_FIELDS))}）"
            )
        bools = {}
        for field_name in MR_BOOL_FIELDS:
            raw = profile.get(field_name)
            if raw is None:
                continue
            if raw not in ("true", "false"):
                failures.append(
                    f"{at} 的 `{field_name}` 是 `{raw}`，布林欄位只認 `true`／`false`"
                )
            bools[field_name] = raw == "true"

        default_provider = profile.get("default_provider")
        if not default_provider or isinstance(default_provider, dict):
            failures.append(f"{at} 缺必填欄位 `default_provider`")
        elif default_provider not in providers:
            failures.append(
                f"{at} 的 `default_provider` 是 `{default_provider}`，"
                f"不在 {PROVIDERS_REL} 的登記表裡（登記的是 {'、'.join(sorted(providers))}）"
                "——不得自動 fallback 到別家：靜默換一家跑，產出風格會變而沒有人知道為什麼"
            )

        roles = profile.get("roles") or {}
        if not isinstance(roles, dict):
            failures.append(f"{at} 的 `roles` 不是「角色 → 供應商 id」的映射")
            roles = {}
        for role, provider in sorted(roles.items()):
            if role not in role_ids:
                failures.append(
                    f"{at} 的 `roles` 指到 `{role}`，但 {ORG_REL} 的 `roles[].id` 裡沒有這個角色"
                    "——那一列永遠不會被套用，而設定檔看起來完全正常"
                )
            if isinstance(provider, dict) or provider not in providers:
                failures.append(
                    f"{at} 把 `{role}` 指到 `{provider}`，"
                    f"不在 {PROVIDERS_REL} 的登記表裡（登記的是 {'、'.join(sorted(providers))}）"
                )

        waives_m4 = bools.get("waives_m4", False)
        if waives_m4:
            if not bools.get("emergency", False):
                failures.append(
                    f"{at} 掛了 `waives_m4: true` 卻沒有 `emergency: true`——"
                    "豁免只在「知道自己在應急」的前提下才成立，"
                    "掛在常態 profile 上就只是把應急豁免當成一般選項用"
                )
            reason = profile.get("waiver_reason")
            if isinstance(reason, dict) or not (reason or "").strip():
                failures.append(
                    f"{at} 掛了 `waives_m4: true` 卻沒有非空的 `waiver_reason`——"
                    "理由必須寫明改回的條件（`M5`(d)：臨時值不寫改回條件就會變成新預設）"
                )

        # `M4`：實作與審查異廠。兩個角色都要在 org.yml 上真的存在本條才有對象——
        # 組織裡沒有 Code Reviewer 時談不上「與審查同廠」，那是 org-sync 的事。
        if {MR_IMPL_ROLE, MR_REVIEW_ROLE} <= role_ids and default_provider:
            impl = roles.get(MR_IMPL_ROLE, default_provider)
            review = roles.get(MR_REVIEW_ROLE, default_provider)
            enforced = bools.get("review_provider_distinct", True)
            if enforced and impl == review and not waives_m4:
                failures.append(
                    f"{at} 把 `{MR_IMPL_ROLE}` 與 `{MR_REVIEW_ROLE}` 都指到 `{impl}`"
                    "（未在 `roles` 覆寫的那個吃 `default_provider`），"
                    "而本 profile 沒有 `waives_m4: true` ⇒ 與 `M4` 自相矛盾。"
                    "要嘛換一家、要嘛補上 `emergency` + `waives_m4` + `waiver_reason` 三件"
                )
    return failures


def check_model_routing_sync(root: Path) -> SelfcheckResult:
    """`.foundry/config.yml` 的 `model_routing` 段要與 `org.yml`、供應商登記表自洽。

    **本項綠不代表平台對得上。** 它只驗 repo 內宣告的自洽性——同 `org-sync` 那條
    刻意界線：`model_routing` 是規則層的**應然**宣告，不是平台狀態的鏡子。
    平台對帳歸 `tools/model-routing/apply_profile.py --check`，那個要 API 金鑰，
    進不了 pre-commit。**不要在這裡「補上」一個比對平台的檢查**，也不要把本項的
    ✅ 讀成「每個 agent 的 adapter 都已經是 active profile 說的那一家」。

    驗的是四件事（清單權威在 `config-schema.md`「`model_routing`」一節末）：
    `active` 指得到 profile、`roles` 的鍵在 `org.yml` 上存在、供應商 id 在
    `probe_providers.py` 的登記表裡、以及 `M4`（實作與審查異廠）成立或有合法 waiver。

    **整段缺席＝路由未啟用**，是預設狀態不是設定缺漏，本項印 ✅ 並在摘要說明。
    """
    res = SelfcheckResult("model-routing-sync",
                          "模型路由宣告自洽（不含平台對帳）")
    config_path = root / CONFIG_REL
    if not config_path.exists():
        res.failures.append(f"{CONFIG_REL} 不存在——本專案的平台與關卡設定缺席")
        return res
    routing = parse_config(read_text(config_path)).get("model_routing")
    if routing is None:
        res.summary += "（`model_routing` 段缺席＝路由未啟用，全隊用執行環境預設供應商）"
        return res
    if not isinstance(routing, dict):
        res.failures.append(f"{CONFIG_REL} 的 `model_routing` 不是一個物件")
        return res

    org_path = root / ORG_REL
    if not org_path.exists():
        res.failures.append(
            f"{ORG_REL} 不存在——`roles` 的鍵要比對它，缺了它角色名就等於沒驗"
        )
        return res
    try:
        role_ids = [r.get("id") for r in (parse_org(read_text(org_path)).get("roles") or [])]
    except LintError as exc:
        res.failures.append(str(exc))
        return res

    providers_path = root / PROVIDERS_REL
    if not providers_path.exists():
        res.failures.append(
            f"{PROVIDERS_REL} 不存在——供應商 id 的值域缺席，本項無從判定。"
            "啟用了路由就必須有這份登記表（foundry-init 的複製清單含 `tools/model-routing/`）"
        )
        return res
    providers = provider_ids(read_text(providers_path))
    if not providers:
        res.failures.append(
            f"{PROVIDERS_REL} 取不到 `{PROVIDERS_SYMBOL}` 登記表的 `id`——"
            "值域取不到時停下報錯，不退回寫死的一份（寫死的會漂，而漂掉沒人會收到通知）"
        )
        return res

    res.failures.extend(audit_model_routing(routing, role_ids, providers))
    res.summary += (f"（active `{routing.get('active')}`、"
                    f"{len(routing.get('profiles') or {})} 個 profile、"
                    f"{len(providers)} 家登記供應商；平台對帳歸 `apply_profile.py --check`）")
    return res


def check_issue_parent(root: Path) -> SelfcheckResult:
    """agent 開的單都要掛得到樹上（`I3`，MYL-117，依 MYL-96 裁定 #18／核可卡 B1）。

    與 `I2` 的「上位單」那一格**射程不同、不會互相誤殺**：`I2` 只看 Product
    Manager 開的單、四欄一起判；本項看**所有 agent 開的單**、只判上位單這一格。
    重疊處（PM 開的、沒有上位單的單）兩項都會報，這是刻意的——同一張單缺同一格，
    兩條紅字講的是同一件事、也指向同一個處置（把上位單補上），不會一綠一紅。

    起算點同 `I1`／`I2`（`ISSUE_RULES_SINCE`）：規則生效前開的單不回溯。回溯那
    一半是**一次性的資料補掛**，已於 2026-09-07 做完（29 張），清單與逐張依據見
    `docs/standards/issue-parent-backfill.md`。

    走了頂層單例外的單**放行但不靜默**：張數與單號印在 summary 尾巴（理由見
    `partition_issue_parents()`／`toplevel_exception_note()`）。
    """
    res = SelfcheckResult("issue-parent", "agent 開的單掛得到樹上（`I3`）")
    endpoint, why = issue_rules_precondition(root)
    if endpoint is None:
        res.skipped = why
        return res
    base, token, company_id, project_id = endpoint

    issues, why = fetch_authored_issues(base, token, company_id, project_id)
    if issues is None:
        res.skipped = f"讀不到來源端：{why}"
        return res

    # 讀不到描述的那幾張記在旁邊（ref → 原因）：判準不吃它（讀不到照樣報），
    # 只有訊息吃。收在這一層而不是塞進 `declared` 的回傳型別裡，是為了讓純函式
    # 那一側的契約維持單純的 bool——測試才不必為了一句訊息去假造連線失敗。
    unreadable = {}

    def declared(it) -> bool:
        if not it.issue_id:
            return False
        found, why = fetch_toplevel_declaration(base, token, it.issue_id)
        if why:
            unreadable[it.ref] = why
        return found

    missing, exempt = partition_issue_parents(issues, ISSUE_RULES_SINCE, declared)
    res.failures.extend(issue_parent_failure(it, unreadable.get(it.ref, ""))
                        for it in missing)
    in_scope = [i for i in issues
                if ref_at_or_after(i.ref, ISSUE_RULES_SINCE)
                and i.author_agent and not i.author_user]
    res.summary += (f"（{ISSUE_RULES_SINCE} 起 agent 開了 {len(in_scope)} 張，"
                    f"全部 {len(issues)} 張）" + toplevel_exception_note(exempt))
    return res


# ── `init-copy-list`：Makefile 引用的 tools/ ↔ foundry-init 複製清單（MYL-86）──
INIT_SKILL_REL = "skills/foundry-init/SKILL.md"
MAKEFILE_REL = "Makefile"
#: 複製清單的位置：`## 2.` 那一節裡以 `3. ` 起頭的編號項。
#: 這裡刻意**不用** `BIG_BEGIN` 那種 HTML 標記：標記得插在編號項之間，會把
#: markdown 的有序清單切成兩段（渲染時後半從 1 重新編號）。代價是節號或項號
#: 漂掉時本檢查會紅——那是要的姿態，找不到清單就報錯，不能靜默放行。
INIT_SECTION_RE = re.compile(r"^## 2\. ", re.M)
INIT_ITEM_RE = re.compile(r"^3\. ", re.M)
INIT_NEXT_ITEM_RE = re.compile(r"^\d+\. ", re.M)
#: 清單的最後一條是反向的 `- 不複製：…`，那行以後列的是**不會**被複製的路徑。
#: 不截斷的話，把某個目錄從複製項移到那一行仍舊算「清單有列」＝假綠，而目標
#: 專案的 `make check` 就掛在那個目錄上（MYL-86 CR R2，有實測反證）。截斷的
#: 失效方向是安全的：真有複製項排到那行之後，結果是紅（看得見），不是綠。
INIT_EXCLUDE_RE = re.compile(r"^\s*-\s*不複製[：:]", re.M)
#: 清單裡的寫法一律是 `` `tools/<X>/`（全目錄） ``。單獨的 `` `tools/` `` 不命中。
INIT_LISTED_RE = re.compile(r"`tools/([A-Za-z0-9._-]+)/?`")
#: Makefile 裡的 `tools/<X>` 引用；`unittest discover tools/foundry-lint` 與
#: `python3 tools/model-routing/probe_providers.py` 兩種形狀都吃。
MAKEFILE_TOOLS_RE = re.compile(r"\btools/([A-Za-z0-9._-]+)")


def makefile_tools_dirs(text: str) -> list:
    """`Makefile` 真的會去跑到的 `tools/<X>` 目錄名，去重後排序。

    整行註解先丟掉：註解裡提到某個目錄不代表 Makefile 會用它，而本檢查的前提
    是「這份 Makefile 被整份複製過去、跑起來會用到」。行內註解不特別處理——
    本檔沒有，真出現了寧可多管一個目錄（誤報看得見），也不要少管（漏報看不見）。
    """
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    return sorted(set(MAKEFILE_TOOLS_RE.findall(body)))


def init_copy_list_block(text: str) -> tuple:
    """取出 foundry-init §2 第 3 點**要複製**的那段原文，回傳 `(區塊, 錯誤原因)`。

    終點取兩個條件裡先出現的那一個：下一個編號項（`^\\d+\\. `），或那條反向的
    `- 不複製：`。後者是 MYL-86 CR 的 R2——少了它，把某個目錄從複製項改寫到
    「不複製」那行，本檢查照樣印綠，而那正是本檢查存在的理由那個情境。
    """
    sec = INIT_SECTION_RE.search(text)
    if not sec:
        return "", "找不到 `## 2.` 這一節"
    tail = text[sec.end():]
    nxt = re.search(r"^## ", tail, re.M)
    section = tail[: nxt.start()] if nxt else tail
    item = INIT_ITEM_RE.search(section)
    if not item:
        return "", "`## 2.` 這一節裡找不到以 `3. ` 起頭的編號項"
    rest = section[item.end():]
    ends = [m.start() for m in (INIT_NEXT_ITEM_RE.search(rest),
                                INIT_EXCLUDE_RE.search(rest)) if m]
    return (rest[: min(ends)] if ends else rest), ""


def check_init_copy_list(root: Path) -> SelfcheckResult:
    """`Makefile` 引用到的每個 `tools/<X>/` 都要在 foundry-init 的複製清單裡。

    init 步驟 2.5 會把 `Makefile` **整份**複製到目標專案，而 `make check` 正是
    入口檔叫每個新 session 跑的那一行。Makefile 用得到、複製清單沒列到的
    `tools/` 目錄，會讓那個專案第一次跑 `make check` 就掛（`.pre-commit-config.yaml`
    的 `foundry-tests` 走的也是 `make test`，同一個坑）。已經漂過兩次——
    `tools/browser-probe/`（MYL-37）與 `tools/publish-docs/`（MYL-52），
    兩次都是往 Makefile 加了一行、沒回頭改清單，直到 MYL-78 才被發現。

    **範圍是整份 `Makefile`，不只 `test:`**（MYL-86 AC3）：`providers`／`browser`
    指到的目錄同樣是「複製過去卻跑不起來」，判準一樣，而不必切出 target 邊界的
    程式反而更短。反方向不管——清單列得比 Makefile 多是合理的（`templates/`
    那些跟 Makefile 無關），本檢查只擋「Makefile 有、清單沒有」這一個方向。

    **目標專案跳過本項**（MYL-87，接續 MYL-86 CR R1 的交接）：複製清單自己寫著
    「不複製：`skills/foundry-init/`」，所以照它初始化出來的專案一定沒有對照端。
    這裡跳過的判準只有一層——`is_rule_repo()`，不像手冊三項要再問一次
    「東西在不在」，因為對照端與判準旗標**是同一個目錄**：不是規則本體就必然沒有
    對照端，沒有第二種情形要分。相對地，規則本體自己少了那份 SKILL.md 仍舊是紅。
    """
    res = SelfcheckResult(
        "init-copy-list", "`Makefile` 引用到的 `tools/` 目錄都在 foundry-init 複製清單裡")
    mk, skill = root / MAKEFILE_REL, root / INIT_SKILL_REL
    if not is_rule_repo(root):
        res.skipped = (
            f"本專案不是 Foundry 規則本體（沒有 `{RULE_REPO_MARKER_REL}/`），"
            "複製清單這個對照端在目標專案依規格就不存在"
        )
        return res
    if not mk.exists():
        res.failures.append(f"{MAKEFILE_REL} 不存在——本檢查的來源端沒了")
        return res
    if not skill.exists():
        res.failures.append(f"{INIT_SKILL_REL} 不存在——本檢查的對照端沒了")
        return res

    block, why = init_copy_list_block(read_text(skill))
    if why:
        res.failures.append(
            f"{INIT_SKILL_REL}：{why}——複製清單的錨點漂了，本檢查無從比對。"
            "清單換了位置就要一起改 `init_copy_list_block()` 的錨點"
        )
        return res

    listed = set(INIT_LISTED_RE.findall(block))
    needed = makefile_tools_dirs(read_text(mk))
    for name in needed:
        if name not in listed:
            res.failures.append(
                f"`Makefile` 用到 tools/{name}/，但 {INIT_SKILL_REL} §2 第 3 點的複製"
                f"清單沒有列它——init 會把 Makefile 整份複製過去，目標專案第一次跑 "
                f"`make check` 就掛在這個目錄上。把 `tools/{name}/`（全目錄）補進清單"
            )
    res.summary += f"（Makefile 引用 {len(needed)} 個、清單列 {len(listed)} 個）"
    return res


# ── `selfcheck-names`：四處手抄的自檢名稱清單 ↔ `SELFCHECKS`（MYL-89）──
#: 從原始碼靜態取檢查名，而不是把 `SELFCHECKS` 跑一遍再問 `res.name`：
#: `mirror-recon` 會連線、`big-files` 會掃整個 repo，光為了問名字不值得。
#: 每個 check 函式都以字面量建 `SelfcheckResult("<機器名>", …)`，取不到就報錯
#: 不放行——靜默略過一項，等於那一項的四處抄寫從此沒人管。
SELFCHECK_NAME_RE = re.compile(r'SelfcheckResult\(\s*"([a-z0-9-]+)"')
#: 機器名 → 四處抄寫點共用的標籤。
#:
#: 四處寫的是中文散文標籤而不是機器名，**而且措辭互不相同**：`entry-sync` 在
#: `Makefile` 是「雙入口同步」、在 hook 名是「雙入口」；`nav-sync` 在入口檔多了
#: 「一致性」、`rule-ids` 多了「引用」。所以本表一律取**最短形**，比對走包含關係
#: （`"雙入口" in "雙入口同步"`），三種措辭都涵蓋得到。統一四處措辭也是一種解法，
#: 但那是替四處各挑一次用詞，改不動的那天本檢查就得跟著鬆——最短形不必談判。
#:
#: ⚠️ 本表自己就是第五份手抄——**唯一讓它不腐爛的是「鍵必須與 `SELFCHECKS` 完全
#: 相等」那一條**（缺／多／錯字都紅）。要改本表的內容之前先確認那條還在。
#: `staged-handbook-sync` 刻意不在這裡：它不在 `SELFCHECKS`（只在 pre-commit 跑），
#: 列進來會逼四處寫上一項 `--selfcheck` 根本不跑的東西。
SELFCHECK_LABELS = {
    "entry-sync": "雙入口",
    "nav-sync": "手冊 nav",
    "anchors": "錨點",
    "rule-ids": "規則 ID",
    "rule-marks": "規則標記",
    "big-files": "大檔清單",
    "internal-links": "相對連結",
    "version-shape": "版本號形狀",
    "table-shape": "表格形狀",
    "config-schema": "設定欄位",
    "org-sync": "組織宣告",
    "model-routing-sync": "模型路由宣告",
    "handbook-stamp": "手冊戳記",
    "init-copy-list": "init 複製清單",
    "selfcheck-names": "自檢名稱清單",
    "mirror-recon": "鏡像對帳",
    "issue-authors": "開單者白名單",
    "pm-issue-fields": "開單必備欄位",
    "issue-parent": "上位單",
}
#: 四個抄寫點：`(檔案, 那一行是什麼, 抓出列舉內容的錨點)`。
#: 錨點只吃**那一行**、不吃整份檔案——整份 `CLAUDE.md` 本來就到處提到「錨點」
#: 「大檔清單」，拿整份做包含比對會讓漏抄靜默通過。
#: 錨點漂掉時報錯不放行（同 `init_copy_list_block()` 的姿態）：找不到清單就等於
#: 沒比對，這種時候印 ✅ 比印 ❌ 危險得多。
SELFCHECK_COPY_SITES = (
    ("Makefile", "`selfcheck` target 的 `##` 說明",
     re.compile(r"^selfcheck:\s*##\s*repo 規範自檢：(.+)$", re.M)),
    (".pre-commit-config.yaml", "`foundry-selfcheck` hook 的 `name`",
     re.compile(r"^\s*name:\s*foundry-lint --selfcheck（(.+)）\s*$", re.M)),
    ("CLAUDE.md", "§6 指令速查的自檢註解行",
     re.compile(r"^# repo 規範自檢（(.+)）$", re.M)),
    ("AGENTS.md", "§6 指令速查的自檢註解行",
     re.compile(r"^# repo 規範自檢（(.+)）$", re.M)),
)
#: 四處用的分隔符不一致（`Makefile` 與入口檔是「、」，hook 名是「／」）。
SELFCHECK_LABEL_SEP_RE = re.compile(r"[、／/，,]")


def selfcheck_registered_names() -> tuple:
    """`SELFCHECKS` 每個成員的檢查名，回傳 `((函式名, 檢查名), …)`；取不到的回空字串。"""
    out = []
    for fn in SELFCHECKS:
        m = SELFCHECK_NAME_RE.search(inspect.getsource(fn))
        out.append((fn.__name__, m.group(1) if m else ""))
    return tuple(out)


def check_selfcheck_names(root: Path) -> SelfcheckResult:
    """四個抄寫點列到的檢查名，要與 `SELFCHECKS` 註冊的那組對得上（MYL-89）。

    `--selfcheck` 有哪幾項，被手抄在四個地方：`Makefile` 的 `selfcheck` target
    說明、`.pre-commit-config.yaml` 的 `foundry-selfcheck` hook 名，以及兩份入口檔
    §6 的自檢註解行。四處與 `SELFCHECKS` 之間原本零機械對應——MYL-86 新增
    `init-copy-list` 時得手改四處，漏改沒有任何東西擋得住，而讀到舊清單的人會以為
    某項檢查不存在（於是不去修它該擋的漂移），或以為某項存在（於是不另外把關）。
    這與 `init-copy-list` 是同一型漂移，只是換了對象。

    **管得到的只有這一組對應關係**：四處列到的名稱集合 ↔ `SELFCHECKS` 註冊的名稱
    集合。不管順序、不管措辭、也不管四處以外任何提到檢查名的散文——`--selfcheck`
    的 argparse `--help` 刻意不列舉就是為了不成為第五個抄寫點（見那段註解）。
    想擴大成「所有反引號路徑都要驗存在」是另一回事（MYL-41 判例，要做另開單）。

    **四處一律維持列舉、不得改成計數**：換成「共 N 項」會讓本檢查無事可做，而那個
    N 一定會過期（MYL-41）。

    **目標專案跳過本項**（判準同 `init-copy-list`）：`Makefile` 與
    `.pre-commit-config.yaml` 是整份複製過去的、對得上，但兩份入口檔是照
    `templates/entry-file.md` 產的，該模板的 §6 明寫「列出這個專案實際會用到的
    指令」＝自由格式，沒有本檢查要的那一行。對照端在目標專案依規格就不存在。
    """
    res = SelfcheckResult("selfcheck-names",
                          "四處手抄的自檢名稱清單與 `SELFCHECKS` 一致")
    if not is_rule_repo(root):
        res.skipped = (
            f"本專案不是 Foundry 規則本體（沒有 `{RULE_REPO_MARKER_REL}/`），"
            "兩份入口檔的 §6 依 `templates/entry-file.md` 是自由格式，"
            "本檢查的對照端在目標專案依規格就不存在"
        )
        return res

    unnamed = [fn for fn, name in selfcheck_registered_names() if not name]
    if unnamed:
        res.failures.append(
            f"讀不出 {'、'.join(unnamed)} 的檢查名——本檢查靠原始碼裡的 "
            '`SelfcheckResult("<名稱>"` 字面量取名，那個函式改了寫法就等於'
            "從此沒人管它的四處抄寫。把名稱寫回建構子的第一個位置引數，"
            "或改 `SELFCHECK_NAME_RE`"
        )
        return res
    registered = [name for _, name in selfcheck_registered_names()]

    # 護欄：包含關係要能判定，標籤就不能互相包含。
    # 少了這一條，未來新增一項標籤叫「手冊」時，四處只要寫了「手冊戳記」就會把
    # 它餵飽——漏抄「手冊」也照樣綠。失效方向是**靜默綠**，不是看得見的紅。
    for name, label in SELFCHECK_LABELS.items():
        for other, other_label in SELFCHECK_LABELS.items():
            if name != other and label in other_label:
                res.failures.append(
                    f"`{name}` 的標籤「{label}」是 `{other}` 的標籤「{other_label}」"
                    "的子字串——四處是散文，比對只能用包含關係，這種情形下前者會被"
                    "後者的字樣餵飽而**靜默通過**（漏抄看不出來）。"
                    "把其中一個標籤改長到互不包含，四處也跟著改"
                )
    if res.failures:
        return res

    # 把登記表綁死在 `SELFCHECKS` 上：少了這一段，登記表就只是第五份手抄。
    for name in registered:
        if name not in SELFCHECK_LABELS:
            res.failures.append(
                f"`SELFCHECKS` 註冊了 `{name}`，但 `SELFCHECK_LABELS` 沒有它——"
                "登記表是本檢查唯一的名稱來源，缺一項就等於那一項的四處抄寫沒人管。"
                f'把 `"{name}": "<四處用的標籤>"` 補進 `SELFCHECK_LABELS`（位置照 '
                "`SELFCHECKS` 的順序），四處也各補一項"
            )
    for name in SELFCHECK_LABELS:
        if name not in registered:
            res.failures.append(
                f"`SELFCHECK_LABELS` 列了 `{name}`，但 `SELFCHECKS` 沒有註冊它——"
                "四處會被逼著寫上一項 `--selfcheck` 根本不跑的東西"
                "（`staged-handbook-sync` 正是這種：它只在 pre-commit 跑）。"
                "把它從登記表與四處一起刪掉，或把它加回 `SELFCHECKS`"
            )
    if res.failures:
        return res

    for rel, where, anchor in SELFCHECK_COPY_SITES:
        path = root / rel
        if not path.exists():
            res.failures.append(
                f"{rel} 不存在——本檢查的四個抄寫點少了一個，那一處的漂移從此沒人管。"
                f"把檔案補回來，或把它從 `SELFCHECK_COPY_SITES` 移除"
            )
            continue
        m = anchor.search(read_text(path))
        if not m:
            res.failures.append(
                f"{rel}：找不到{where}那一行——錨點漂了，本檢查無從比對這一處。"
                "那一行換了寫法就要一起改 `SELFCHECK_COPY_SITES` 的錨點"
            )
            continue
        listed = [s.strip() for s in SELFCHECK_LABEL_SEP_RE.split(m.group(1))]
        listed = [s for s in listed if s]
        for name, label in SELFCHECK_LABELS.items():
            if not any(label in frag for frag in listed):
                res.failures.append(
                    f"{rel} 的{where}漏了 `{name}`（標籤「{label}」）——"
                    "讀到那一行的人會以為 `--selfcheck` 不查這一項，於是另外去補一套"
                    f"把關，或乾脆不管。把「{label}」補進那一行（順序照 `SELFCHECKS`）"
                )
        for frag in listed:
            if not any(label in frag for label in SELFCHECK_LABELS.values()):
                res.failures.append(
                    f"{rel} 的{where}多了一項「{frag}」，對不到任何一項 `SELFCHECKS`"
                    "——多寫或寫錯字的那一項，會讓人去找一個不存在的檢查。"
                    "改成 `SELFCHECK_LABELS` 裡的標籤，或從那一行刪掉"
                )
    res.summary += f"（{len(SELFCHECK_LABELS)} 項 × {len(SELFCHECK_COPY_SITES)} 處）"
    return res


SELFCHECKS = (check_entry_sync, check_nav_sync, check_handbook_anchors, check_rule_ids,
              check_rule_marks, check_big_files, check_internal_links,
              check_version_shape, check_table_shape, check_config_schema,
              check_org_sync, check_model_routing_sync,
              check_handbook_stamp, check_init_copy_list,
              check_selfcheck_names, check_mirror_recon,
              check_issue_authors, check_pm_issue_fields,
              check_issue_parent)


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
        # ⚠️ 這裡刻意**不列舉**有哪幾項（MYL-89）。原本列的是一份節錄，四項一過期
        # 就成了另一個沒人管的抄寫點——而 `selfcheck-names` 管的是 `Makefile`／
        # `.pre-commit-config.yaml`／兩份入口檔那四處，不含本行。跑一次就印得出
        # 逐項名稱，這行沒有再抄一遍的價值。要在這裡列，就得先把本行加進
        # `SELFCHECK_COPY_SITES`。
        help="跑 repo 規範自檢（逐項名稱見輸出的 `[名稱]`），不需 --type／file",
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
    parser.add_argument(
        "--big-files-list",
        action="store_true",
        help="印出入口檔 §4 大檔清單的表格列（foundry-init 步驟 2.5 產生入口檔時用）",
    )
    parser.add_argument("--repo-root", default=None, help="自檢的 repo 根目錄，預設為本檔上溯兩層")
    parser.add_argument("file", nargs="?")
    args = parser.parse_args(argv)
    other_modes = (args.selfcheck or args.staged_handbook_sync
                   or args.stamp_only_since or args.big_files_list)
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

    if args.big_files_list:
        print(render_big_files_list(repo_root_of(args)))
        sys.exit(0)

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
