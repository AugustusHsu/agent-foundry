#!/usr/bin/env bash
# 手冊發佈的**證據閘門**：MYL-24 的發佈審查核對 ＋ MYL-44 的戳記旁路。
#
# 為什麼獨立成一支（MYL-52）：這段邏輯原本長在 `publish-handbook.sh` 裡，
# 而 `publish_docs` 成為抽象動詞之後有**兩個目標面**（wiki 主閱讀面、mkdocs 精裝面），
# 兩邊都要過同一道閘門。抄兩份就是這個 repo 反覆記錄的漂移來源（見 known-drift
# 「兩份 nav 的結構性漂移」），所以抽出來共用。
#
# 順帶把 MYL-50 併入本單的那件事變得做得到：閘門現在可以**單獨執行**
#   bash scripts/lib/publish-gate.sh <repo 根>
# 不 clone、不 push、只跑判斷，退出碼 0＝放行、1＝擋下。
# `tools/publish-docs/test_publish_gate.py` 就是靠這個介面用臨時 repo 測它。
#
# 用法（被 source 時）：
#   source scripts/lib/publish-gate.sh
#   publish_gate_check "$SRC_ROOT"      # 不通過會 exit 1
# 通過後可讀的變數：
#   HANDBOOK_SHA      這版手冊的 commit sha（完整）
#   GATE_FILE / GATE_ISSUE / GATE_REVIEWER   對應的審查記錄
#   GATE_BASE         走戳記旁路時的基準 commit（沒走旁路則為空）
#   GATE_STAMP_SKIPPED   被略過審查的戳記 commit 清單（沒走旁路則為空）

gate_fail() {
  echo "❌ 發佈被擋下（MYL-24 發佈審查證據閘門）：$1" >&2
  echo "   處理方式：$2" >&2
  exit 1
}

publish_gate_check() {
  local SRC_ROOT="$1"
  local REVIEW_DIR="$SRC_ROOT/docs/publish-reviews"

  echo "==> 檢查發佈審查證據"

  git -C "$SRC_ROOT" rev-parse --git-dir >/dev/null 2>&1 ||
    gate_fail "$SRC_ROOT 不是 git repo，無法核對審查證據。" \
              "在私有 repo agent-foundry 內執行本腳本。"

  local DIRTY
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
  local ref
  for ref in main origin/main; do
    git -C "$SRC_ROOT" rev-parse --verify --quiet "$ref" >/dev/null || continue
    git -C "$SRC_ROOT" merge-base --is-ancestor "$HANDBOOK_SHA" "$ref" ||
      gate_fail "手冊最新變更 ${HANDBOOK_SHA:0:8} 尚未合併進 $ref（P2 前提 1 不成立）。" \
                "先把工作分支合併進 main 並推送，再重跑。"
  done

  local REVIEWS
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
  local APPROVAL="" R_FILE R_ISSUE R_REVIEWER R_COMMIT
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
  GATE_BASE=""
  GATE_STAMP_SKIPPED=""
  if [ -z "$APPROVAL" ]; then
    local BASE="" BASE_DIST="" BASE_INFO="" dist
    while IFS='|' read -r R_FILE R_ISSUE R_REVIEWER R_COMMIT; do
      [ -n "$R_COMMIT" ] || continue
      git -C "$SRC_ROOT" rev-parse --verify --quiet "${R_COMMIT}^{commit}" >/dev/null || continue
      git -C "$SRC_ROOT" merge-base --is-ancestor "$R_COMMIT" HEAD || continue
      dist="$(git -C "$SRC_ROOT" rev-list --count "$R_COMMIT..HEAD")"
      if [ -z "$BASE_DIST" ] || [ "$dist" -lt "$BASE_DIST" ]; then
        BASE="$R_COMMIT"; BASE_DIST="$dist"; BASE_INFO="$R_FILE|$R_ISSUE|$R_REVIEWER"
      fi
    done <<<"$REVIEWS"

    if [ -n "$BASE" ] && GATE_STAMP_SKIPPED="$(python3 "$SRC_ROOT/tools/foundry-lint/foundry_lint.py" \
          --stamp-only-since "$BASE" --repo-root "$SRC_ROOT")"; then
      APPROVAL="$BASE_INFO"
      GATE_BASE="$BASE"
    else
      GATE_STAMP_SKIPPED=""
    fi
  fi

  [ -n "$APPROVAL" ] ||
    gate_fail "手冊最新變更 ${HANDBOOK_SHA:0:8} 沒有對應的 APPROVED 發佈審查記錄，且與最近一份已核可版本之間的差異不只有同步戳記。" \
              "依 templates/publish-review.md 建立 docs/publish-reviews/<工單號>.md（verdict: APPROVED、handbook_commit: $HANDBOOK_SHA），commit 後重跑。"

  IFS='|' read -r GATE_FILE GATE_ISSUE GATE_REVIEWER <<<"$APPROVAL"
  echo "   ✅ 審查記錄：docs/publish-reviews/$GATE_FILE（工單 $GATE_ISSUE，審查者 $GATE_REVIEWER）"
  if [ -n "$GATE_STAMP_SKIPPED" ]; then
    echo "   ↷ 戳記旁路（MYL-44）：以上記錄核可的是 ${GATE_BASE:0:8}，其後這些 commit 只改了同步戳記，未另做審查："
    local line
    while IFS= read -r line; do
      [ -n "$line" ] && echo "      · $line"
    done <<<"$GATE_STAMP_SKIPPED"
  fi
  echo "   ✅ 手冊 commit：$HANDBOOK_SHA"
}

# 直接執行＝只跑閘門不做任何發佈動作。測試與人工排查都走這條。
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  set -euo pipefail
  if [ $# -ne 1 ]; then
    echo "用法：bash scripts/lib/publish-gate.sh <repo 根>" >&2
    exit 2
  fi
  publish_gate_check "$1"
  echo "==> 閘門通過（未執行任何發佈動作）"
fi
