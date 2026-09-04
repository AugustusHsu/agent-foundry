#!/usr/bin/env bash
# `publish_docs` 動詞的 **mkdocs-mirror 目標面**（skills/foundry-platform/SKILL.md §3.9）：
# 把 docs/handbook/ 的可公開內容同步到 public repo（AugustusHsu/foundry-handbook）並發佈 GitHub Pages。
#
# ⚠️ 這支腳本會 git push 到公開 repo（兩處：公開鏡像 main、gh-pages）。
#    依 MYL-23 分級表屬 P2「既有公開管道發佈」，執行者自檢前提成立後可自行執行，
#    但必須先通過發佈審查證據閘門（MYL-24）——沒有對應的 APPROVED 審查記錄就拒跑。
#    閘門本體自 MYL-52 起住在 scripts/lib/publish-gate.sh，與 wiki 目標面共用同一份。
#
# 過濾規則：指向私有 repo 內部路徑（skills/、templates/、docs/pilot/、私有 README）的
# 超連結一律拆為純文字，內容照抄不改。來源真相永遠是私有 repo 的 docs/handbook/。
#
# 用法：bash scripts/publish-handbook.sh
set -euo pipefail

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUB_REPO="AugustusHsu/foundry-handbook"
SITE_URL="https://augustushsu.github.io/foundry-handbook/"

# ── 發佈審查證據閘門（MYL-24 ＋ MYL-44 戳記旁路）───────────────────────────
# 擋在任何 clone／push 之前。閘門綁的是「手冊內容的 commit sha」而不是工單號——
# 綁工單號的話，「審查通過後又改手冊再發佈」會從閘門下面溜過去。
# shellcheck source=scripts/lib/publish-gate.sh
source "$SRC_ROOT/scripts/lib/publish-gate.sh"
publish_gate_check "$SRC_ROOT"
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
