#!/usr/bin/env bash
# 一次性：把舊公開鏡像站 foundry-handbook 換成指向新家的 redirect。MYL-55。
#
# 為什麼需要它：手冊站從 `foundry-handbook` 搬回 `agent-foundry` 之後，舊網址
# <https://augustushsu.github.io/foundry-handbook/> 已經被引用出去（`foundry-init`
# 的下一步指引、README、過去的工單留言）。直接封存舊 repo 會讓那些連結變 404，
# 而 404 不會告訴讀者新家在哪。
#
# ⚠️ **這支不是例行同步，是 P3**：它改變的是「公開發佈範圍」本身（把一個公開站
#    換成 redirect），依 protocol 第 7、9 節分級表要使用者當下同意才能跑。
#    跑之前也要確認新站真的活著——先把讀者導去一個還沒開的 Pages 更糟。
#
# ⚠️ **順序**：必須在 `foundry-handbook` 被封存**之前**跑。封存後 repo 唯讀，push 會被拒。
#
# 用法：
#   bash scripts/redirect-old-mirror.sh --check      # 只驗新站活著，不寫入
#   bash scripts/redirect-old-mirror.sh              # 產生 redirect 並 push gh-pages
set -euo pipefail

OLD_REPO="AugustusHsu/foundry-handbook"
NEW_SITE="https://augustushsu.github.io/agent-foundry/latest/"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

# 舊站有哪幾頁 → 一頁一個 redirect。只有首頁的話，深連結會全部落到首頁，
# 讀者得自己再找一次章節；一頁一頁對過去才是真的沒斷。
PAGES=(
  ""                       # 首頁
  "01-first-run"
  "02-commands"
  "03-workflow"
  "04-decision-points"
  "05-troubleshooting"
  "06-org-structure"
  "07-workflows"
  "08-cross-platform"
)

echo "==> 確認新站已經活著（導去一個還沒開的站比 404 更糟）"
CODE="$(curl -s -o /dev/null -w '%{http_code}' -L "$NEW_SITE" || true)"
if [ "$CODE" != "200" ]; then
  echo "❌ $NEW_SITE 回 HTTP $CODE——新站還沒發佈或 Pages 還沒開。" >&2
  echo "   先讓使用者開 Pages、打第一個 handbook-v* tag，站台 200 之後再跑本腳本。" >&2
  exit 1
fi
echo "   ✅ $NEW_SITE → HTTP 200"

if [ "$CHECK_ONLY" = "1" ]; then
  echo "==> --check：未做任何寫入"
  exit 0
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> clone $OLD_REPO 的 gh-pages"
git clone --quiet --branch gh-pages --depth 1 "https://github.com/${OLD_REPO}.git" "$WORK/repo"

echo "==> 清掉舊站內容，換成 redirect"
find "$WORK/repo" -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +

for page in "${PAGES[@]}"; do
  if [ -z "$page" ]; then
    dir="$WORK/repo"; target="$NEW_SITE"
  else
    dir="$WORK/repo/$page"; target="${NEW_SITE}${page}/"
    mkdir -p "$dir"
  fi
  cat > "$dir/index.html" <<HTMLEOF
<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>已搬家 — Foundry Handbook</title>
<link rel="canonical" href="${target}">
<meta http-equiv="refresh" content="0; url=${target}">
</head>
<body>
<p>Foundry 使用手冊已搬到 <a href="${target}">${target}</a>，正在為你轉址。</p>
<p>新站由內部 repo <code>agent-foundry</code> 的 <code>docs/handbook/</code> 產生，
並以 <code>mike</code> 版本化：網址裡的 <code>latest</code> 可換成 <code>v1</code>、
<code>v2</code> 等版本號。</p>
</body>
</html>
HTMLEOF
done

# Jekyll 會吃掉底線開頭的檔案並自作主張處理版面；純靜態站一律關掉。
touch "$WORK/repo/.nojekyll"

echo "==> commit 並 push"
git -C "$WORK/repo" add -A
if git -C "$WORK/repo" diff --cached --quiet; then
  echo "   內容無變更，跳過 push"
else
  git -C "$WORK/repo" commit --quiet -m "🚚 手冊站搬家：全站轉址到 agent-foundry Pages（MYL-55）"
  git -C "$WORK/repo" push --quiet origin HEAD:gh-pages
  echo "   ✅ 已推送"
fi

echo "==> 完成。下一步（使用者專屬）：封存 $OLD_REPO"
echo "   封存後 repo 唯讀，本腳本就不能再跑了——順序不可顛倒。"
