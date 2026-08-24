#!/usr/bin/env bash
# 承認後の commit + push。ユーザーの承認が取れてから実行すること。
#
#   bash tools/lmfdb-ability-add/scripts/git_commit_push.sh "add: 〇〇の能力を追加" [file ...]
#
# ファイルを省略した場合は ux/index.html（本運用）だけをステージする。
# push は失敗時に 2s / 4s / 8s / 16s のバックオフで最大4回リトライする。
set -uo pipefail

MSG="${1:-}"
if [ -z "$MSG" ]; then
  echo "❌ コミットメッセージを第1引数で渡してください"
  echo "   例: bash $0 \"add: ロクショウの能力を追加\""
  exit 1
fi
shift || true

FILES=("$@")
if [ ${#FILES[@]} -eq 0 ]; then
  FILES=("ux/index.html")
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "❌ gitリポジトリではありません"; exit 1; }
cd "$REPO_ROOT" || exit 1

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "リポジトリ: $REPO_ROOT"
echo "ブランチ  : $BRANCH"

# コミット前チェック（ux/index.html が対象に含まれるときのみ）
for f in "${FILES[@]}"; do
  if [ "$f" = "ux/index.html" ]; then
    echo
    echo "── コミット前チェック ──"
    if ! bash "$(dirname "${BASH_SOURCE[0]}")/check.sh" "$f"; then
      echo "❌ チェックに失敗したのでコミットを中止します"
      exit 1
    fi
    break
  fi
done

echo
git add -- "${FILES[@]}" || exit 1

if git diff --cached --quiet; then
  echo "⚠️  ステージされた変更がありません。何もせず終了します。"
  exit 0
fi

echo "── コミット対象 ──"
git diff --cached --stat
echo

git commit -m "$MSG" || exit 1

delay=2
for attempt in 1 2 3 4 5; do
  if git push -u origin "$BRANCH"; then
    echo
    echo "✅ push 完了: $BRANCH"
    exit 0
  fi
  if [ "$attempt" -eq 5 ]; then
    break
  fi
  echo "⚠️  push 失敗（${attempt}回目）。${delay}秒待って再試行します..."
  sleep "$delay"
  delay=$((delay * 2))
done

echo "❌ push に4回リトライしても失敗しました。コミットはローカルに残っています。"
exit 1
