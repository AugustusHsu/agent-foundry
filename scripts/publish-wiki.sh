#!/usr/bin/env bash
# `publish_docs` 動詞的 **github-wiki 目標面**（skills/foundry-platform/SKILL.md §3.9）：
# 把 docs/handbook/ 機械投影到 agent-foundry 的 GitHub wiki，wiki 是主閱讀面。
#
# 三件事按順序發生，任一步紅就不 push：
#   1. **證據閘門**（與 mkdocs 目標面共用 scripts/lib/publish-gate.sh）：MYL-24 審查記錄 ＋ MYL-44 戳記旁路。
#   2. **防手改偵測**：wiki 誰都能編。同步前確認 wiki 的 HEAD 正是上次本腳本推的那一顆，
#      而且工作區內容與那顆記錄的摘要相符。不符就**拒絕覆蓋並報錯**——
#      沒有這一條，「投影」的說法站不住：腳本會靜靜蓋掉別人的編輯。
#   3. **逐章比對**：標題文字／章節數／內部連結目標／MYL-44 戳記行，缺一章就是紅燈。
#
# ⚠️ 這支會 push 到 wiki。repo 目前是 public，wiki 隨之公開可讀，
#    依 MYL-23 分級表屬 P2「既有公開管道發佈」——但**前提是這條管道已經由使用者
#    依 `G-C` 核可開通**（開 wiki 本身是 P3／關卡 C，不在本腳本的授權範圍內）。
#
# 用法：
#   bash scripts/publish-wiki.sh                 # 完整同步
#   bash scripts/publish-wiki.sh --dry-run       # 投影＋比對，不 clone 遠端、不 push
#   bash scripts/publish-wiki.sh --bootstrap     # 首次投影：接受尚未帶投影 trailer 的 wiki
#   bash scripts/publish-wiki.sh --link-policy plain
set -euo pipefail

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="AugustusHsu/agent-foundry"
# 測試接縫：`tools/publish-docs/test_publish_gate.py` 的 `WikiTamperTest` 用本機
# bare repo 假扮 wiki，才有辦法在不碰網路的情況下證明防手改偵測真的擋得住。
WIKI_URL="${FOUNDRY_WIKI_URL:-https://github.com/${REPO}.wiki.git}"
WIKI_HTML="${FOUNDRY_WIKI_HTML:-https://github.com/${REPO}/wiki}"
DRY_RUN=0
BOOTSTRAP=0

# `docs` 段的欄位由 .foundry/config.yml 決定，腳本不另設預設值：設定檔宣告一套、
# 腳本寫死另一套，就是這個 repo 反覆記錄的兩份真相。讀不到就停，不猜。
read_docs_field() {
  python3 - "$SRC_ROOT" "$1" "$2" <<'PYEOF'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / "tools" / "foundry-lint"))
from foundry_lint import read_config
docs = read_config(pathlib.Path(sys.argv[1])).get("docs") or {}
print(docs.get(sys.argv[2], sys.argv[3]))
PYEOF
}

# 缺欄位時落回 schema 寫的預設（`link_policy` 預設 absolute、`source` 預設手冊目錄），
# 而不是落回腳本自己的意見——兩者的差別在於前者查得到權威來源。
LINK_POLICY="$(read_docs_field link_policy absolute)"
DOCS_SOURCE="$(read_docs_field source docs/handbook/)"
LINK_POLICY_FROM='.foundry/config.yml 的 docs.link_policy'

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --bootstrap) BOOTSTRAP=1 ;;
    --link-policy) LINK_POLICY="${2:?--link-policy 要帶值}"; LINK_POLICY_FROM="指令列覆寫"; shift ;;
    --link-policy=*) LINK_POLICY="${1#*=}"; LINK_POLICY_FROM="指令列覆寫" ;;
    -h|--help) sed -n '1,25p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "未知參數：$1" >&2; exit 2 ;;
  esac
  shift
done

case "$LINK_POLICY" in
  absolute|plain) ;;
  *) echo "❌ link_policy 只能是 absolute 或 plain，收到「$LINK_POLICY」（來源：$LINK_POLICY_FROM）" >&2; exit 2 ;;
esac

# ── 步驟 1：發佈審查證據閘門（MYL-24 ＋ MYL-44）────────────────────────────
# shellcheck source=scripts/lib/publish-gate.sh
source "$SRC_ROOT/scripts/lib/publish-gate.sh"
publish_gate_check "$SRC_ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
WIKI="$WORK/wiki"

tamper_fail() {
  echo "❌ 同步被擋下（MYL-52 防手改偵測）：$1" >&2
  cat >&2 <<EOF
   為什麼擋：wiki 是**機械投影**，不是第二份真相。偵測到 wiki 上有非本腳本產生的
   內容時直接停手，而不是覆蓋過去——覆蓋等於把別人寫的東西靜靜刪掉。
   處理方式（三選一，都要人決定，腳本不自作主張）：
     1. 那筆編輯應該進手冊 → 把內容搬回 $SRC_ROOT/$DOCS_SOURCE，走正常工單與閘門，再重跑本腳本。
     2. 那筆編輯不要了 → 在 wiki 上還原成上一次投影的狀態，或加 --bootstrap 明確表示放棄它。
     3. 這是第一次投影（wiki 還沒有任何投影 commit）→ 加 --bootstrap。
   wiki：$WIKI_HTML
EOF
  exit 1
}

# ── 步驟 2：取得 wiki 現況並做防手改偵測 ──────────────────────────────────
if [ "$DRY_RUN" -eq 1 ]; then
  echo "==> [dry-run] 略過 clone wiki，只做投影與逐章比對"
  mkdir -p "$WIKI"
else
  echo "==> clone wiki（$WIKI_URL）"
  # wiki repo 要有第一頁才成形：has_wiki 剛開啟、一頁都還沒建時 clone 會失敗。
  # 這是本單指名要實測的未驗證項，所以錯誤訊息直接把替代路徑寫出來，不硬推。
  if ! git clone --quiet "$WIKI_URL" "$WIKI" 2>"$WORK/clone.err"; then
    echo "❌ clone 不到 wiki repo。" >&2
    sed 's/^/   /' "$WORK/clone.err" >&2
    cat >&2 <<EOF
   最可能的原因：wiki 已啟用但**還沒有任何一頁**，wiki repo 尚未成形。
   處理方式：先在 $WIKI_HTML 用 UI 建立第一頁（內容隨意，下次同步會被投影覆蓋），
   再重跑本腳本並加 --bootstrap。
   若 has_wiki 仍為 false，那是關卡 C（gates.external_actions: user），發卡請使用者開啟。
EOF
    exit 1
  fi

  HEAD_MSG="$(git -C "$WIKI" log -1 --format=%B 2>/dev/null || true)"
  PREV_DIGEST="$(printf '%s\n' "$HEAD_MSG" | sed -n 's/^Foundry-Projection-Digest:[[:space:]]*//p' | tail -1)"
  PREV_SOURCE="$(printf '%s\n' "$HEAD_MSG" | sed -n 's/^Foundry-Projection:[[:space:]]*//p' | tail -1)"

  if [ -z "$PREV_DIGEST" ]; then
    [ "$BOOTSTRAP" -eq 1 ] || tamper_fail \
      "wiki 的 HEAD 不是本腳本推的投影 commit（訊息裡沒有 Foundry-Projection-Digest trailer）。
   HEAD：$(git -C "$WIKI" log -1 --format='%h %an %s' 2>/dev/null || echo '（沒有任何 commit）')"
    echo "   ↷ --bootstrap：接受目前的 wiki 內容，本次視為首次投影"
  else
    ACTUAL_DIGEST="$(python3 -c "
import sys, pathlib
sys.path.insert(0, '$SRC_ROOT/tools/publish-docs')
from project_docs import digest_of_dir
print(digest_of_dir(pathlib.Path('$WIKI')))
")"
    if [ "$ACTUAL_DIGEST" != "$PREV_DIGEST" ]; then
      [ "$BOOTSTRAP" -eq 1 ] || tamper_fail \
        "wiki 現在的內容跟上次投影推上去的不一樣——有人直接在 wiki 上編輯過。
   上次投影：${PREV_SOURCE:0:12}（摘要 ${PREV_DIGEST:0:12}）
   目前內容摘要：${ACTUAL_DIGEST:0:12}
   有差異的頁面：$(git -C "$WIKI" log -1 --format='%h %an %ad %s' --date=short)"
      echo "   ↷ --bootstrap：已偵測到手改，依指示放棄該筆編輯"
    else
      echo "   ✅ 防手改偵測：wiki HEAD 正是上次投影（${PREV_SOURCE:0:12}），內容未被手改"
    fi
  fi
fi

# ── 步驟 3：投影 ──────────────────────────────────────────────────────────
echo "==> 投影 $DOCS_SOURCE → wiki 頁面（link-policy=$LINK_POLICY，來源：$LINK_POLICY_FROM）"
find "$WIKI" -maxdepth 1 -name '*.md' -delete 2>/dev/null || true
python3 "$SRC_ROOT/tools/publish-docs/project_docs.py" \
  --src "$SRC_ROOT/${DOCS_SOURCE%/}" \
  --out "$WIKI" \
  --mkdocs "$SRC_ROOT/mkdocs.yml" \
  --handbook-commit "$HANDBOOK_SHA" \
  --link-policy "$LINK_POLICY"

NEW_DIGEST="$(python3 -c "
import sys, pathlib
sys.path.insert(0, '$SRC_ROOT/tools/publish-docs')
from project_docs import digest_of_dir
print(digest_of_dir(pathlib.Path('$WIKI')))
")"

# ── 步驟 4：逐章比對（MYL-52 驗收條件 4）──────────────────────────────────
echo "==> 逐章比對（缺一章就是紅燈）"
REPORT="$WORK/compare.md"
if ! python3 "$SRC_ROOT/tools/publish-docs/compare_projection.py" \
      --src "$SRC_ROOT/${DOCS_SOURCE%/}" --wiki "$WIKI" | tee "$REPORT"; then
  echo "❌ 逐章比對未全綠，停止同步。上表就是證據，貼進工單再處理。" >&2
  exit 1
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "==> [dry-run] 完成：投影 ＋ 比對皆通過，未 push。摘要 ${NEW_DIGEST:0:12}"
  exit 0
fi

# ── 步驟 5：commit ＋ push ────────────────────────────────────────────────
# trailer 是下一次防手改偵測的憑證：記錄「來源哪一顆」與「推上去的內容摘要」。
# 沒有 trailer、或摘要對不上，下次同步就會停手。
echo "==> commit 並 push wiki"
git -C "$WIKI" add -A
if git -C "$WIKI" diff --cached --quiet; then
  echo "   內容無變更，跳過 push"
else
  git -C "$WIKI" \
    -c user.name="${GIT_AUTHOR_NAME:-Foundry publish_docs}" \
    -c user.email="${GIT_AUTHOR_EMAIL:-foundry-publish-docs@users.noreply.github.com}" \
    commit --quiet -m "📝 投影手冊到 wiki（自 agent-foundry $DOCS_SOURCE）

本頁面集由 scripts/publish-wiki.sh 機械產生，請勿直接編輯。

Foundry-Projection: $HANDBOOK_SHA
Foundry-Projection-Digest: $NEW_DIGEST"
  git -C "$WIKI" push --quiet origin HEAD:master 2>/dev/null ||
    git -C "$WIKI" push --quiet origin HEAD:main
fi

echo "==> 完成：$WIKI_HTML"
echo "   來源手冊 commit：$HANDBOOK_SHA"
echo "   投影摘要：$NEW_DIGEST"
echo "   逐章比對表：$REPORT（內容已印在上方，貼進工單當證據）"
