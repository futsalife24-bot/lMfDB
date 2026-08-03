#!/usr/bin/env bash
# lMfDB index.html のエラーチェック。
#
#   bash tools/lmfdb-ability-add/scripts/check.sh [index.html]
#
# 全項目通れば「✅ 全項目クリア」を出して終了コード 0、
# ひとつでも落ちれば終了コード 1。
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HTML="${1:-index.html}"

if [ ! -f "$HTML" ]; then
  echo "❌ ファイルが見つかりません: $HTML"
  exit 1
fi

fail=0

echo "── [1/4] データ整合性チェック ──"
if python3 "$SCRIPT_DIR/validate.py" "$HTML"; then
  echo "  ✅ データ整合性 OK"
else
  fail=1
fi

echo
echo "── [2/4] HTML 構造チェック ──"
python3 - "$HTML" <<'PY'
import re, sys
html = open(sys.argv[1], encoding="utf-8").read()
ok = True
if not re.search(r"<html[\s>]", html, re.I) or "</html>" not in html.lower():
    print("  ❌ <html> ... </html> が揃っていません"); ok = False
opens = len(re.findall(r"<script\b", html, re.I))
closes = len(re.findall(r"</script\s*>", html, re.I))
if opens != closes:
    print("  ❌ <script> %d個 / </script> %d個 で不一致" % (opens, closes)); ok = False
for el in ("div", "span", "button"):
    o = len(re.findall(r"<%s\b" % el, html, re.I))
    c = len(re.findall(r"</%s\s*>" % el, html, re.I))
    if o != c:
        print("  ⚠️  <%s> %d個 / </%s> %d個 で不一致" % (el, o, el, c))
if ok:
    print("  ✅ HTML 構造 OK")
sys.exit(0 if ok else 1)
PY
[ $? -ne 0 ] && fail=1

echo
echo "── [3/4] JavaScript 構文チェック ──"
if command -v node >/dev/null 2>&1; then
  python3 - "$HTML" <<'PY' > /tmp/lmfdb_check_$$.js
import re, sys
html = open(sys.argv[1], encoding="utf-8").read()
# 外部srcのない <script> の中身だけを連結して構文チェックにかける
parts = []
for m in re.finditer(r"<script\b([^>]*)>(.*?)</script\s*>", html, re.DOTALL | re.I):
    if re.search(r"\bsrc\s*=", m.group(1), re.I):
        continue
    if re.search(r'\btype\s*=\s*["\'](?!text/javascript|module)', m.group(1), re.I):
        continue
    parts.append(m.group(2))
sys.stdout.write("\n;\n".join(parts))
PY
  # ABILITIES は1行が数十万文字あるので、エラー時に該当行を丸ごと出さないよう
  # 各行を先頭200文字までに切り詰めてから表示する
  if node --check "/tmp/lmfdb_check_$$.js" > "/tmp/lmfdb_check_$$.log" 2>&1; then
    echo "  ✅ JS 構文 OK"
  else
    echo "  ❌ JS 構文エラー"
    cut -c1-200 "/tmp/lmfdb_check_$$.log" | head -20 | sed 's/^/     /'
    fail=1
  fi
  rm -f "/tmp/lmfdb_check_$$.log"
  rm -f "/tmp/lmfdb_check_$$.js"
else
  echo "  ⏭️  node が無いためスキップ"
fi

echo
echo "── [4/4] PWA 付帯ファイルチェック ──"
dir="$(dirname "$HTML")"
pwa_ok=1
for f in manifest.json sw.js; do
  if [ -f "$dir/$f" ]; then
    echo "  ✅ $f あり"
  else
    echo "  ⚠️  $f が見つかりません"
  fi
done
if [ -f "$dir/manifest.json" ]; then
  if python3 -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8'))" "$dir/manifest.json" 2>/dev/null; then
    echo "  ✅ manifest.json は正しいJSON"
  else
    echo "  ❌ manifest.json のJSONが壊れています"
    pwa_ok=0
  fi
fi
[ $pwa_ok -eq 0 ] && fail=1

echo
if [ $fail -eq 0 ]; then
  echo "✅ 全項目クリア"
  exit 0
else
  echo "❌ チェック失敗（上のエラーを修正してください）"
  exit 1
fi
