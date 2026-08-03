#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""index.html の能力データを検証する。check.sh から呼ばれる。

終了コード: 0 = エラーなし / 1 = エラーあり
警告(WARN)は終了コードに影響しない。
"""

import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lmfdb_common import (  # noqa: E402
    KNOWN_MISSING_RARITY_IDS,
    KNOWN_TAGS,
    REQUIRED_KEYS,
    VALID_RARITIES,
    VALID_SOURCES,
    LmfdbError,
    apply_data_fixes,
    get_card_list,
    get_update_info,
    load_abilities,
    read_html,
)

errors = []
warns = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warns.append(msg)


def check_structure(data):
    """必須キー・型の検証。"""
    for a in data:
        aid = a.get("id", "?")
        for k in REQUIRED_KEYS:
            if k not in a:
                err("id=%s: 必須キー '%s' がありません" % (aid, k))
        if not isinstance(a.get("id"), int):
            err("id=%s: id が整数ではありません" % aid)
        for k in ("name", "desc", "card", "source"):
            if k in a and not isinstance(a[k], str):
                err("id=%s: '%s' が文字列ではありません" % (aid, k))
        if "tags" in a:
            if not isinstance(a["tags"], list) or not all(
                isinstance(t, str) for t in a["tags"]
            ):
                err("id=%s: tags が文字列配列ではありません" % aid)
        for k in ("name", "card"):
            if isinstance(a.get(k), str) and not a[k].strip():
                err("id=%s: '%s' が空です" % (aid, k))


def check_ids(data):
    """ID の重複・欠番・順序。"""
    ids = [a["id"] for a in data if isinstance(a.get("id"), int)]
    dups = [i for i, c in collections.Counter(ids).items() if c > 1]
    if dups:
        err("ID が重複しています: %s" % sorted(dups))
    if ids and ids != sorted(ids):
        out = [
            (ids[i - 1], ids[i]) for i in range(1, len(ids)) if ids[i] < ids[i - 1]
        ]
        warn("ID が昇順ではない箇所があります（既存データ由来なら無視可）: %s" % out)
    if ids:
        gaps = sorted(set(range(1, max(ids) + 1)) - set(ids))
        if gaps:
            warn("欠番ID %d件（削除済み能力なら正常）: %s%s"
                 % (len(gaps), gaps[:10], " ..." if len(gaps) > 10 else ""))


def check_enums(data):
    """source / rarity の値。"""
    for a in data:
        aid = a.get("id", "?")
        if a.get("source") not in VALID_SOURCES:
            err("id=%s: source が不正です: %r（許可: %s）"
                % (aid, a.get("source"), "/".join(VALID_SOURCES)))
        if "rarity" not in a:
            if aid in KNOWN_MISSING_RARITY_IDS:
                warn("id=%s: rarity 欠落（既知の既存データ）" % aid)
            else:
                err("id=%s: rarity がありません" % aid)
        elif a["rarity"] not in VALID_RARITIES:
            err("id=%s: rarity が不正です: %r（許可: %s）"
                % (aid, a["rarity"], "/".join(VALID_RARITIES)))


def check_tags(data):
    """タグの表記ゆれ・重複・空。"""
    unknown = collections.defaultdict(list)
    for a in data:
        aid = a.get("id", "?")
        tags = a.get("tags")
        if not isinstance(tags, list):
            continue
        if len(tags) != len(set(tags)):
            err("id=%s: tags に重複があります: %s" % (aid, tags))
        for t in tags:
            if not isinstance(t, str):
                continue
            if not t.strip():
                err("id=%s: 空のタグがあります" % aid)
            elif t not in KNOWN_TAGS:
                unknown[t].append(aid)
    for t, ids in sorted(unknown.items()):
        warn("未知のタグ %r が %d件で使われています（表記ゆれでなければ "
             "lmfdb_common.py の KNOWN_TAGS に追加すること）: id=%s"
             % (t, len(ids), ids[:5]))


def check_desc(data):
    """desc の書式。改行は <br>、生の改行やタブは不可。"""
    for a in data:
        aid = a.get("id", "?")
        desc = a.get("desc")
        if not isinstance(desc, str):
            continue
        if "\n" in desc or "\r" in desc or "\t" in desc:
            err("id=%s: desc に生の改行/タブが含まれています（<br> を使うこと）" % aid)
        if re.search(r"<br\s*/>|<BR", desc):
            warn("id=%s: desc の改行タグは <br>（小文字・スラッシュなし）に統一してください" % aid)
        if "</script" in desc.lower() or "</script" in str(a.get("name", "")).lower():
            err("id=%s: </script を含む文字列は HTML を壊します" % aid)


def check_script_safety(data, html):
    """インライン <script> を壊す文字列が混入していないか。"""
    for a in data:
        for k, v in a.items():
            if isinstance(v, str) and "</script" in v.lower():
                err("id=%s: '%s' に </script が含まれています" % (a.get("id", "?"), k))
    m = re.search(r"const ABILITIES\s*=\s*\[.*?\];", html, re.DOTALL)
    if m and "\n" in m.group(0):
        warn("ABILITIES 配列に改行が含まれています（従来は1行）")


def check_update_info(data, html):
    """更新表示の件数がデータ件数と一致しているか。"""
    date_str, count = get_update_info(html)
    if date_str is None:
        err('id="db-update-info" の更新表示が見つかりません')
        return
    if count != len(data):
        err("更新表示の件数(%d件)がデータ件数(%d件)と一致しません" % (count, len(data)))
    if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", date_str):
        warn("更新日の書式が YYYY/MM/DD ではありません: %r" % date_str)


def check_cards(data, html):
    """カード名がレアリティ別リストに載っているか（載っていないと所持画面に出ない）。

    UI は DATA_FIXES をマージしてから描画するので、こちらも合わせる。
    """
    cards_by_rarity = collections.defaultdict(set)
    for a in apply_data_fixes(data, html):
        if a.get("source") in ("EXトレ", "伝授"):
            continue  # EX/伝授カードはリスト管理対象外
        r = a.get("rarity")
        if r in ("SSR", "MR", "SR"):
            cards_by_rarity[r].add(a.get("card"))
    for rarity, cards in sorted(cards_by_rarity.items()):
        listed = get_card_list(html, rarity)
        if listed is None:
            err("const %s_CARDS = [...]; を検出できませんでした" % rarity)
            continue
        missing = sorted(c for c in cards if c not in listed)
        if missing:
            warn("%s_CARDS に未登録のカードが %d件あります: %s%s"
                 % (rarity, len(missing), missing[:10],
                    " ..." if len(missing) > 10 else ""))


def main():
    ap = argparse.ArgumentParser(description="lMfDB index.html の整合性チェック")
    ap.add_argument("html", nargs="?", default="index.html")
    ap.add_argument("--quiet", action="store_true", help="警告を表示しない")
    args = ap.parse_args()

    try:
        html = read_html(args.html)
        data, _ = load_abilities(html)
    except (OSError, LmfdbError) as e:
        print("❌ %s" % e)
        return 1

    check_structure(data)
    check_ids(data)
    check_enums(data)
    check_tags(data)
    check_desc(data)
    check_script_safety(data, html)
    check_update_info(data, html)
    check_cards(data, html)

    ids = [a["id"] for a in data if isinstance(a.get("id"), int)]
    print("対象ファイル: %s" % args.html)
    print("総件数: %d ／ 最大ID: %s" % (len(data), max(ids) if ids else "-"))
    date_str, count = get_update_info(html)
    print("更新表示: %s ／ %s件" % (date_str, count))

    if warns and not args.quiet:
        print()
        for w in warns:
            print("⚠️  WARN: %s" % w)
    if errors:
        print()
        for e in errors:
            print("❌ ERROR: %s" % e)
        print()
        print("❌ エラー %d件（警告 %d件）" % (len(errors), len(warns)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
