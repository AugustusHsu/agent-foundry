#!/usr/bin/env bash
# `publish_docs` 動詞的 **mkdocs 精裝面**（skills/foundry-platform/SKILL.md §3.9）：
# 把 docs/handbook/ 建成版本化的 GitHub Pages 站，發到**本 repo** 的 gh-pages。
#
# MYL-55 取代 scripts/publish-handbook.sh。三件事跟著換掉：
#   1. **家搬回本 repo**：不再推公開鏡像 repo（foundry-handbook 由使用者封存保留，
#      舊網址不轉址、直接斷——使用者裁定，見 known-drift `R7`），
#      站台由本 repo 的 gh-pages 分支出。跨 repo PAT 因此不再需要。
#   2. **版本化**：用 mike，站上同時留 v1／v2／…／latest 與版本選擇器。
#      讀者第一次答得出「我讀的是哪一版規則」。
#   3. **不在本機建站**：正常路徑是 CI（打 handbook-v* tag 觸發）。
#      舊腳本的 `python3 -m venv` ＋ `pip install mkdocs-material` 現裝沒了。
#
# ⚠️ 這支會 push 到公開站（gh-pages）。依 MYL-23 分級表屬 P2「既有公開管道發佈」，
#    但**發佈範圍改變**（換 repo、開 Pages、封存舊鏡像）是 P3，那些不由本腳本做。
#    本腳本只做已開通管道的例行同步，且必須先過發佈審查證據閘門（MYL-24）。
#
# 用法：
#   bash scripts/publish-site.sh --tag handbook-v1          # 完整發佈
#   bash scripts/publish-site.sh --tag handbook-v1 --dry-run # 只判斷＋建置，不 push
#
# 前提（CI 已備妥；本機跑要自己裝）：python3、mkdocs-material、mike。
set -euo pipefail

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$SRC_ROOT/.site-build"
SITE_URL="https://augustushsu.github.io/agent-foundry/"
ALIAS="latest"

TAG=""
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "未知參數：$1" >&2; exit 2 ;;
  esac
done
[ -n "$TAG" ] || { echo "用法：bash scripts/publish-site.sh --tag <handbook-vN> [--dry-run]" >&2; exit 2; }

# ── 步驟 1：設定閘門（AC2 的執行點）───────────────────────────────────────
# `.foundry/config.yml` 的 `docs.mirror_site` 說了算。workflow 的
# `on: push: tags:` 只是粗篩——那是寫死的靜態字串，改 tag_pattern 不會讓它跟著變。
echo "==> 讀 .foundry/config.yml 判斷本次 tag 要不要發佈"
DECISION="$(python3 "$SRC_ROOT/tools/publish-docs/site_docs.py" decide \
  --config "$SRC_ROOT/.foundry/config.yml" --tag "$TAG")"
echo "$DECISION" | sed 's/^/   /'
PUBLISH="$(echo "$DECISION" | sed -n 's/^publish=//p')"
VERSION="$(echo "$DECISION" | sed -n 's/^version=//p')"

if [ "$PUBLISH" != "true" ]; then
  echo "==> 精裝站未啟用或本次 tag 不觸發：不建置、不推送（這不是錯誤）"
  exit 0
fi

# ── 步驟 2：發佈審查證據閘門（MYL-24 ＋ MYL-44 戳記旁路）─────────────────
# 與 wiki 面共用同一份。順序刻意排在任何寫入之前（§3.9 行為 1：閘門不過就不寫）。
# shellcheck source=scripts/lib/publish-gate.sh
source "$SRC_ROOT/scripts/lib/publish-gate.sh"
publish_gate_check "$SRC_ROOT"

# ── 步驟 3：投影＋逐章比對（§3.9 行為 3、4）──────────────────────────────
echo "==> 投影 docs/handbook/ → $BUILD_DIR"
python3 "$SRC_ROOT/tools/publish-docs/site_docs.py" build \
  --src "$SRC_ROOT/docs/handbook" \
  --mkdocs "$SRC_ROOT/mkdocs.yml" \
  --config "$SRC_ROOT/.foundry/config.yml" \
  --out "$BUILD_DIR" \
  --site-url "$SITE_URL"

# ── 步驟 4：建站並以 mike 部署 ────────────────────────────────────────────
# 產出的 mkdocs.yml 帶 `strict: true`，連結解不開就在這裡紅，不會靜靜發出去。
# mike 的 git 操作跑在 repo 根（gh-pages 是本 repo 的分支），所以 build 目錄
# 刻意放在 repo 內（已列入 .gitignore）而不是 /tmp。
cd "$SRC_ROOT"
if [ "$DRY_RUN" = "1" ]; then
  echo "==> --dry-run：只建置不部署"
  mkdocs build --strict --config-file "$BUILD_DIR/mkdocs.yml" --site-dir "$BUILD_DIR/site"
  echo "==> 完成（未推送）：$BUILD_DIR/site"
  exit 0
fi

echo "==> mike deploy $VERSION（別名 $ALIAS）"
mike deploy --config-file "$BUILD_DIR/mkdocs.yml" --push --update-aliases "$VERSION" "$ALIAS"
mike set-default --config-file "$BUILD_DIR/mkdocs.yml" --push "$ALIAS"

echo "==> 完成：${SITE_URL}（版本 $VERSION，Pages 部署可能需要 1–2 分鐘生效）"
echo "   查證（§3.9 成功判準，腳本自己回報成功不算數）："
echo "   · 版本清單：curl -s ${SITE_URL}versions.json"
echo "   · 章節齊全：逐章開一遍，或看上面「逐章比對全綠」那行的章數"
