#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lMfDB index.html を安全に読み書きするための共通ロジック。

index.html は単一ファイル製 PWA なので、能力データ(ABILITIES)を
書き換えるときは「配列リテラルの中身だけ」を差し替え、それ以外の
バイトには一切触れないこと。ABILITIES の閉じ括弧の直後には歴史的な
経緯で余分な `;` が大量に並んでいるが、これも保持する。
"""

import html as html_lib
import json
import re
import sys

# ABILITIES 配列リテラルを取り出す正規表現。group(1) が配列本体。
ABILITIES_RE = re.compile(r"const ABILITIES\s*=\s*(\[.*?\]);", re.DOTALL)

# 更新日と件数を表示している <div>。両方を書き換える。
UPDATE_INFO_RE = re.compile(
    r'(<div id="db-update-info"[^>]*>)更新:\s*([0-9/]+)\s*／\s*([0-9]+)件(</div>)'
)

# UX改善版は件数を ${abilities.length} で動的表示する。
UPDATE_INFO_JS_RE = re.compile(
    r"(document\.getElementById\('db-update-info'\)\.innerHTML=`更新:\s*)([0-9/]+)(\s*／\s*\$\{abilities\.length\}件)"
)

# カード名リスト（レアリティごと）。新カード追加時はここにも足す。
CARD_LIST_RE = {
    "SSR": re.compile(r"(const SSR_CARDS\s*=\s*\[)(.*?)(\];)", re.DOTALL),
    "MR": re.compile(r"(const MR_CARDS\s*=\s*\[)(.*?)(\];)", re.DOTALL),
    "SR": re.compile(r"(const SR_CARDS\s*=\s*\[)(.*?)(\];)", re.DOTALL),
}

REQUIRED_KEYS = ("id", "name", "desc", "card", "tags", "source")
KEY_ORDER = ("id", "name", "desc", "card", "tags", "source", "rarity")

VALID_SOURCES = ("イベント", "閃き", "EXトレ", "伝授")
VALID_RARITIES = ("SSR", "MR", "SR", "その他")

# 既存データで実際に使われているタグ。ここに無いタグは「新規タグ」として
# 警告を出す（禁止ではないが、表記ゆれの検出が目的）。
KNOWN_TAGS = (
    "オーラ", "オーラ白", "オーラ黒", "オーラ赤", "オーラ青", "オーラ黄", "オーラ緑",
    "オーラ変化", "自身白", "自身黄",
    "序盤", "中盤", "終盤", "前半", "後半",
    "攻撃強化", "命中強化", "命中", "丈夫さ強化", "全技強化", "かしこさ技",
    "クリティカル", "追撃", "連撃", "追撃連撃", "貫通",
    "回避", "完全回避", "シールド", "装甲", "被ダメ軽減", "無効化", "必中",
    "ガッツ回復", "ガッツ変化系", "充填", "デバフ", "忠誠度", "移動速度",
    "ライフ低下時", "有利時", "不利以外", "地形適応", "エーテル",
    "魔族", "獣族", "怪物", "幻霊", "無機", "創造",
    "ニャー種", "ピクシー種",
    "雪山", "森林", "砂漠",
)

# rarity 欠落を許す既知の例外。id=1120/1128/1144 は補完済みなので現在は空。
# 新たに例外を足さないこと（欠落すると SR タブに誤って出る）。
KNOWN_MISSING_RARITY_IDS = ()


class LmfdbError(Exception):
    pass


def read_html(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_html(path, html):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(html)


def extract_match(html):
    m = ABILITIES_RE.search(html)
    if not m:
        raise LmfdbError("index.html から const ABILITIES = [...]; を検出できませんでした")
    return m


def load_abilities(html):
    """(abilities, match) を返す。"""
    m = extract_match(html)
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise LmfdbError("ABILITIES のJSONパースに失敗しました: %s" % e)
    if not isinstance(data, list):
        raise LmfdbError("ABILITIES が配列ではありません")
    return data, m


def dump_abilities(data):
    """既存ファイルと同じ書式（1行・空白なし・日本語そのまま）で直列化する。"""
    ordered = []
    for a in data:
        o = {}
        for k in KEY_ORDER:
            if k in a:
                o[k] = a[k]
        # KEY_ORDER に無いキーがあれば末尾に温存する
        for k in a:
            if k not in o:
                o[k] = a[k]
        ordered.append(o)
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))


def replace_abilities(html, data):
    """配列リテラルの中身だけを差し替える。前後のバイトは保持。"""
    m = extract_match(html)
    return html[: m.start(1)] + dump_abilities(data) + html[m.end(1) :]


def get_update_info(html):
    """(日付文字列, 件数intまたはNone) を返す。見つからなければ (None, None)。"""
    m = UPDATE_INFO_RE.search(html)
    if m:
        return m.group(2), int(m.group(3))
    m = UPDATE_INFO_JS_RE.search(html)
    if m:
        return m.group(2), None  # UX改善版は件数を実行時に算出する
    return None, None


def set_update_info(html, date_str, count):
    m = UPDATE_INFO_RE.search(html)
    if m:
        new = "%s更新: %s ／ %d件%s" % (m.group(1), date_str, count, m.group(4))
        return html[: m.start()] + new + html[m.end() :]
    m = UPDATE_INFO_JS_RE.search(html)
    if m:
        new = "%s%s%s" % (m.group(1), date_str, m.group(3))
        return html[: m.start()] + new + html[m.end() :]
    raise LmfdbError('id="db-update-info" の更新表示を検出できませんでした')


# 改善版の「能力更新」タブ。新しい履歴を先頭へ積む。
UPDATE_HISTORY_ABILITIES_RE = re.compile(
    r'(<section class="update-history-panel" id="history-abilities"[^>]*>)(.*?)(\s*</section>)',
    re.DOTALL,
)


def add_update_history(html, date_str, title, description):
    """能力更新履歴に1件追加する。表示文字列はHTMLエスケープして安全に保持する。"""
    m = UPDATE_HISTORY_ABILITIES_RE.search(html)
    if not m:
        raise LmfdbError('id="history-abilities" の能力更新履歴を検出できませんでした')
    date_display = html_lib.escape(date_str, quote=True)
    date_attr = html_lib.escape(date_str.replace("/", "-"), quote=True)
    safe_title = html_lib.escape(title, quote=False)
    safe_description = html_lib.escape(description, quote=False)
    entry = (
        '\n      <article class="update-history-entry"><time datetime="%s">%s</time>'
        '<strong>%s</strong><p>%s</p></article>'
        % (date_attr, date_display, safe_title, safe_description)
    )
    return html[:m.start()] + m.group(1) + entry + m.group(2) + m.group(3) + html[m.end():]

DATA_FIXES_RE = re.compile(r"const DATA_FIXES\s*=\s*\{(.*?)\n\};", re.DOTALL)


def get_data_fixes(html):
    """DATA_FIXES（誤記補正パッチ）を {id: {key: value}} として読む。

    UI 側は ABILITIES にこれをマージしてから描画するので、カード名の
    照合はマージ後の値で行う必要がある。
    """
    m = DATA_FIXES_RE.search(html)
    if not m:
        return {}
    fixes = {}
    for entry in re.finditer(r"(\d+)\s*:\s*\{([^}]*)\}", m.group(1)):
        aid = int(entry.group(1))
        props = {}
        for prop in re.finditer(r"(\w+)\s*:\s*'((?:[^'\\]|\\.)*)'", entry.group(2)):
            props[prop.group(1)] = prop.group(2).replace("\\'", "'")
        if props:
            fixes[aid] = props
    return fixes


def apply_data_fixes(data, html):
    """DATA_FIXES をマージした能力リストを返す（元のリストは変更しない）。"""
    fixes = get_data_fixes(html)
    if not fixes:
        return data
    return [{**a, **fixes.get(a.get("id"), {})} for a in data]


def get_card_list(html, rarity):
    rx = CARD_LIST_RE.get(rarity)
    if rx is None:
        return None
    m = rx.search(html)
    if not m:
        return None
    return re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(2))


def add_card_to_list(html, rarity, card):
    """カード名を *_CARDS リストの末尾に追加する（既にあれば何もしない）。"""
    rx = CARD_LIST_RE.get(rarity)
    if rx is None:
        raise LmfdbError("カードリストのレアリティが不正です: %s" % rarity)
    m = rx.search(html)
    if not m:
        raise LmfdbError("const %s_CARDS = [...]; を検出できませんでした" % rarity)
    existing = get_card_list(html, rarity) or []
    if card in existing:
        return html, False
    body = m.group(2).rstrip()
    quoted = "'" + card.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if body.endswith(","):
        new_body = m.group(2).rstrip() + "\n  " + quoted
    elif body == "":
        new_body = quoted
    else:
        # 元の末尾要素のインデントに合わせる
        sep = ",\n  " if "\n" in m.group(2) else ","
        new_body = m.group(2).rstrip() + sep + quoted
    return html[: m.start()] + m.group(1) + new_body + m.group(3) + html[m.end() :], True


def eprint(*args):
    print(*args, file=sys.stderr)
