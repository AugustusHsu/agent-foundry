#!/usr/bin/env bash
# 把 docs/handbook/ 的可公開內容同步到 public repo（AugustusHsu/foundry-handbook）並發佈 GitHub Pages。
#
# ⚠️ 這支腳本會 git push 到公開 repo（兩處：公開鏡像 main、gh-pages）。
#    依 MYL-23 分級表屬 P2「既有公開管道發佈」，執行者自檢前提成立後可自行執行，
#    但必須先通過下方的發佈審查證據閘門（MYL-24）——沒有對應的 APPROVED 審查記錄就拒跑。
#
# 過濾規則：指向私有 repo 內部路徑（skills/、templates/、docs/pilot/、私有 README）的
# 超連結一律拆為純文字，內容照抄不改。來源真相永遠是私有 repo 的 docs/handbook/。
#
# 用法：bash scripts/publish-handbook.sh
set -euo pipefail

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUB_REPO="AugustusHsu/foundry-handbook"
SITE_URL="https://augustushsu.github.io/foundry-handbook/"
REVIEW_DIR="$SRC_ROOT/docs/publish-reviews"

# ── 發佈審查證據閘門（MYL-24）─────────────────────────────────────────────
# 擋在任何 clone／push 之前。閘門綁的是「手冊內容的 commit sha」而不是工單號——
# 綁工單號的話，「審查通過後又改手冊再發佈」會從閘門下面溜過去。
gate_fail() {
  echo "❌ 發佈被擋下（MYL-24 發佈審查證據閘門）：$1" >&2
  echo "   處理方式：$2" >&2
  exit 1
}

echo "==> 檢查發佈審查證據"

git -C "$SRC_ROOT" rev-parse --git-dir >/dev/null 2>&1 ||
  gate_fail "$SRC_ROOT 不是 git repo，無法核對審查證據。" \
            "在私有 repo agent-foundry 內執行本腳本。"

DIRTY="$(git -C "$SRC_ROOT" status --porcelain -- docs/handbook docs/publish-reviews)"
[ -z "$DIRTY" ] ||
  gate_fail "docs/handbook/ 或 docs/publish-reviews/ 有未 commit 的變更，審查證據無法對應實際內容：
$DIRTY" \
            "先把變更 commit（並依審查結果更新審查記錄），再重跑。"

HANDBOOK_SHA="$(git -C "$SRC_ROOT" log -1 --format=%H -- docs/handbook)"
[ -n "$HANDBOOK_SHA" ] ||
  gate_fail "找不到任何動到 docs/handbook/ 的 commit。" "確認 repo 內容完整。"

# P2 前提 (1)：來源變更已合併進私有 main（本地 main 與 origin/main 都要涵蓋，
# 否則會把只存在於工作分支的內容推上公開站）。
for ref in main origin/main; do
  git -C "$SRC_ROOT" rev-parse --verify --quiet "$ref" >/dev/null || continue
  git -C "$SRC_ROOT" merge-base --is-ancestor "$HANDBOOK_SHA" "$ref" ||
    gate_fail "手冊最新變更 ${HANDBOOK_SHA:0:8} 尚未合併進 $ref（P2 前提 1 不成立）。" \
              "先把工作分支合併進 main 並推送，再重跑。"
done

REVIEWS="$(python3 - "$REVIEW_DIR" <<'PYEOF'
import re, sys, pathlib
d = pathlib.Path(sys.argv[1])
def field(head, key):
    m = re.search(rf'^{key}:\s*(.+?)\s*$', head, re.M)
    return m.group(1).strip('"\'') if m else ''
for p in sorted(d.glob('*.md')) if d.is_dir() else []:
    m = re.match(r'---\n(.*?)\n---', p.read_text(encoding='utf-8'), re.S)
    if not m:
        continue
    head, commit = m.group(1), field(m.group(1), 'handbook_commit')
    # 允許短 sha，但至少 7 碼，避免空值或過短前綴誤中
    if field(head, 'verdict') == 'APPROVED' and len(commit) >= 7:
        print(f"{p.name}|{field(head, 'issue')}|{field(head, 'reviewer')}|{commit}")
PYEOF
)"

# (a) 精確匹配：有一份 APPROVED 記錄的 handbook_commit 正是這版手冊。
APPROVAL=""
while IFS='|' read -r R_FILE R_ISSUE R_REVIEWER R_COMMIT; do
  [ -n "$R_COMMIT" ] || continue
  case "$HANDBOOK_SHA" in
    "$R_COMMIT"*) APPROVAL="$R_FILE|$R_ISSUE|$R_REVIEWER"; break ;;
  esac
done <<<"$REVIEWS"

# (b) 戳記旁路（MYL-44）：沒有精確匹配時，找出最近一份仍在 HEAD 歷史上的 APPROVED
#     記錄當基準，若它到 HEAD 之間的手冊變更**每一行都是同步戳記**，就放行。
#     為什麼要這條：戳記-only 的 commit 會換掉手冊 sha，於是找不到對應記錄、
#     發佈直接失敗——公開站會被自己的閘門鎖在舊版，而那正是戳記要避免的事。
#     判定條件全由 `git diff` 決定（見 foundry_lint.handbook_diff_is_stamp_only），
#     是封閉的洞不是人治例外：夾帶任何一行實質內容就落回 (a) 的閘門。
STAMP_SKIPPED=""
if [ -z "$APPROVAL" ]; then
  BASE=""; BASE_DIST=""; BASE_INFO=""
  while IFS='|' read -r R_FILE R_ISSUE R_REVIEWER R_COMMIT; do
    [ -n "$R_COMMIT" ] || continue
    git -C "$SRC_ROOT" rev-parse --verify --quiet "${R_COMMIT}^{commit}" >/dev/null || continue
    git -C "$SRC_ROOT" merge-base --is-ancestor "$R_COMMIT" HEAD || continue
    dist="$(git -C "$SRC_ROOT" rev-list --count "$R_COMMIT..HEAD")"
    if [ -z "$BASE_DIST" ] || [ "$dist" -lt "$BASE_DIST" ]; then
      BASE="$R_COMMIT"; BASE_DIST="$dist"; BASE_INFO="$R_FILE|$R_ISSUE|$R_REVIEWER"
    fi
  done <<<"$REVIEWS"

  if [ -n "$BASE" ] && STAMP_SKIPPED="$(python3 "$SRC_ROOT/tools/foundry-lint/foundry_lint.py" \
        --stamp-only-since "$BASE" --repo-root "$SRC_ROOT")"; then
    APPROVAL="$BASE_INFO"
  else
    STAMP_SKIPPED=""
  fi
fi

[ -n "$APPROVAL" ] ||
  gate_fail "手冊最新變更 ${HANDBOOK_SHA:0:8} 沒有對應的 APPROVED 發佈審查記錄，且與最近一份已核可版本之間的差異不只有同步戳記。" \
            "依 templates/publish-review.md 建立 docs/publish-reviews/<工單號>.md（verdict: APPROVED、handbook_commit: $HANDBOOK_SHA），commit 後重跑。"

IFS='|' read -r A_FILE A_ISSUE A_REVIEWER <<<"$APPROVAL"
echo "   ✅ 審查記錄：docs/publish-reviews/$A_FILE（工單 $A_ISSUE，審查者 $A_REVIEWER）"
if [ -n "$STAMP_SKIPPED" ]; then
  echo "   ↷ 戳記旁路（MYL-44）：以上記錄核可的是 ${BASE:0:8}，其後這些 commit 只改了同步戳記，未另做審查："
  while IFS= read -r line; do
    [ -n "$line" ] && echo "      · $line"
  done <<<"$STAMP_SKIPPED"
fi
echo "   ✅ 手冊 commit：$HANDBOOK_SHA"
# ──────────────────────────────────────────────────────────────────────────

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> clone $PUB_REPO"
git clone --quiet "https://github.com/${PUB_REPO}.git" "$WORK/repo"

echo "==> 複製手冊內容（handbook/index.md → docs/index.md，各章平移）"
mkdir -p "$WORK/repo/docs"
rm -f "$WORK/repo/docs/"*.md
for f in "$SRC_ROOT"/docs/handbook/*.md; do
  base="$(basename "$f")"
  cp "$f" "$WORK/repo/docs/$base"
done

echo "==> 過濾私有連結"
python3 - "$WORK/repo/docs" <<'PYEOF'
import re, sys, pathlib
docs = pathlib.Path(sys.argv[1])
# 把指向私有 repo 的 markdown 連結 [text](target) 拆為純文字 text
PRIVATE_TARGETS = re.compile(
    r'\[([^\]]+)\]\((?:\.\./)+(?:skills/|templates/|pilot/)[^)]*\)'
    r'|\[([^\]]+)\]\(https://github\.com/AugustusHsu/agent-foundry[^)]*\)'
)
def strip_link(m):
    return m.group(1) or m.group(2)
for p in sorted(docs.glob('*.md')):
    text = p.read_text(encoding='utf-8')
    new = PRIVATE_TARGETS.sub(strip_link, text)
    if new != text:
        print(f'   filtered: {p.name}')
        p.write_text(new, encoding='utf-8')
PYEOF

echo "==> 產生站台首頁提示與設定"
python3 - "$WORK/repo/docs/index.md" <<'PYEOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
text = p.read_text(encoding='utf-8')
NOTE = ('\n!!! note "公開鏡像"\n'
        '    本站是內部 repo `agent-foundry` 中 `docs/handbook/` 的公開鏡像，'
        '由 `scripts/publish-handbook.sh` 同步。'
        '文中提到的 `skills/`、`templates/`、`docs/pilot/` 等路徑位於內部 repo，'
        '不在本站範圍內。\n')
if '公開鏡像' not in text:
    lines = text.split('\n')
    lines.insert(1, NOTE)
    p.write_text('\n'.join(lines), encoding='utf-8')
PYEOF

cat > "$WORK/repo/mkdocs.yml" <<YMLEOF
site_name: Foundry Handbook
site_description: Foundry — 跑在 Paperclip 上的 AI 開發團隊使用手冊（公開鏡像）
site_url: ${SITE_URL}

repo_name: ${PUB_REPO}
repo_url: https://github.com/${PUB_REPO}
edit_uri: ""

docs_dir: docs

theme:
  name: material
  language: zh-TW
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: deep orange
      accent: deep orange
      toggle:
        icon: material/brightness-7
        name: 切換至深色模式
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: deep orange
      accent: deep orange
      toggle:
        icon: material/brightness-4
        name: 切換至淺色模式
  features:
    - navigation.instant
    - navigation.tracking
    - navigation.sections
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.highlight
  - pymdownx.tabbed:
      alternate_style: true
  - tables
  - toc:
      permalink: true

nav:
  - 首頁: index.md
  - 1. 第一次使用走查: 01-first-run.md
  - 2. 我該下什麼指令？: 02-commands.md
  - 3. 流程會怎麼跑？: 03-workflow.md
  - 4. 我要在哪幾個點做決定？: 04-decision-points.md
  - 5. 故障排除: 05-troubleshooting.md
  - 6. 團隊是怎麼編制的？: 06-org-structure.md
  - 7. 團隊有哪些固定 workflow？: 07-workflows.md
  - 8. 怎麼把這套流程帶到其他專案？: 08-cross-platform.md

plugins:
  - search:
      lang: zh
YMLEOF

cat > "$WORK/repo/README.md" <<'MDEOF'
# Foundry Handbook（公開鏡像）

Foundry——跑在 Paperclip 上的 AI 開發團隊——的使用手冊公開鏡像。

- **線上閱讀**：<https://augustushsu.github.io/foundry-handbook/>
- **來源真相**：內部 repo `agent-foundry` 的 `docs/handbook/`。本 repo 內容由
  `scripts/publish-handbook.sh` 單向同步產生，**請勿直接在本 repo 編輯內容**。
- 指向內部 repo 的連結（`skills/`、`templates/`、`docs/pilot/`）在同步時已拆為純文字。

## 重新發佈

在內部 repo 執行：

```bash
bash scripts/publish-handbook.sh
```

腳本會：核對發佈審查證據 → 過濾內容 → 更新本 repo main → `mkdocs gh-deploy` 重建站台。
第一步的證據閘門找不到對應這版手冊的 APPROVED 審查記錄時會直接拒跑。
MDEOF

rm -f "$WORK/repo/docs/.gitkeep"

echo "==> commit 並 push main"
git -C "$WORK/repo" add -A
if git -C "$WORK/repo" diff --cached --quiet; then
  echo "   內容無變更，跳過 main push"
else
  git -C "$WORK/repo" commit --quiet -m "📝 同步手冊內容（自 agent-foundry docs/handbook/）"
  git -C "$WORK/repo" push --quiet origin HEAD:main
fi

echo "==> 準備 mkdocs 環境"
VENV="${MKDOCS_VENV:-$WORK/venv}"
if [ ! -x "$VENV/bin/mkdocs" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet mkdocs-material
fi

echo "==> 建置並部署 gh-pages"
cd "$WORK/repo"
"$VENV/bin/mkdocs" build --strict
"$VENV/bin/mkdocs" gh-deploy --force --no-history --quiet 2>&1 | tail -1 || true

echo "==> 完成：$SITE_URL（Pages 部署可能需要 1–2 分鐘生效）"
