#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lMfDB のUX改善版（ux/index.html）に能力を追加する。

使い方:
    # JSONファイルから追加（配列でも単体オブジェクトでも可）
    python3 tools/lmfdb-ability-add/scripts/add_ability.py --json new.json

    # 標準入力から
    cat new.json | python3 .../add_ability.py --json -

    # 1件だけコマンドラインで
    python3 .../add_ability.py \
        --name "横一閃 III" \
        --desc "[前半]＜白＞技発動時、ちからステ＜＋４０％＞" \
        --card "ロクショウ" \
        --tags "前半,オーラ白,攻撃強化" \
        --source イベント --rarity SSR

    # 実際に書き込まず差分だけ見る
    python3 .../add_ability.py --json new.json --dry-run

入力JSONの1件の形:
    {
      "name": "能力名 I",
      "desc": "説明（改行は <br>）",
      "card": "カード名",
      "tags": ["タグ1", "タグ2"],
      "source": "イベント",     // イベント / 閃き / EXトレ / 伝授
      "rarity": "SSR"           // SSR / MR / SR / その他
    }
id は省略すると「既存の最大ID + 1」から自動採番する。
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lmfdb_common import (  # noqa: E402
    KEY_ORDER,
    KNOWN_TAGS,
    REQUIRED_KEYS,
    VALID_RARITIES,
    VALID_SOURCES,
    LmfdbError,
    add_card_to_list,
    dump_abilities,
    get_card_list,
    get_update_info,
    load_abilities,
    read_html,
    replace_abilities,
    set_update_info,
    write_html,
)


def parse_args():
    ap = argparse.ArgumentParser(
        description="UX改善版（ux/index.html）に能力を追加する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--html", default="ux/index.html", help="対象HTML（既定: ux/index.html）")
    ap.add_argument("--json", help="追加する能力のJSON。'-' で標準入力")
    ap.add_argument("--name")
    ap.add_argument("--desc")
    ap.add_argument("--card")
    ap.add_argument("--tags", help="カンマ区切り")
    ap.add_argument("--source", choices=VALID_SOURCES)
    ap.add_argument("--rarity", choices=VALID_RARITIES)
    ap.add_argument("--id", type=int, help="IDを明示指定（既定は自動採番）")
    ap.add_argument("--date", help="更新日 YYYY/MM/DD（既定: 今日）")
    ap.add_argument("--no-date-update", action="store_true",
                    help="更新日を書き換えない（件数のみ更新）")
    ap.add_argument("--no-card-list", action="store_true",
                    help="SSR_CARDS等への新カード追加を行わない")
    ap.add_argument("--allow-new-tags", action="store_true",
                    help="未知のタグをエラーにしない")
    ap.add_argument("--dry-run", action="store_true", help="書き込まずに差分を表示")
    return ap.parse_args()


def collect_entries(args):
    """--json と個別オプションから追加対象のリストを組み立てる。"""
    if args.json:
        raw = sys.stdin.read() if args.json == "-" else read_html(args.json)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            raise LmfdbError("入力JSONのパースに失敗しました: %s" % e)
        entries = payload if isinstance(payload, list) else [payload]
    else:
        if not (args.name and args.desc and args.card):
            raise LmfdbError(
                "--json を使わない場合は --name --desc --card が必須です"
            )
        entries = [{
            "name": args.name,
            "desc": args.desc,
            "card": args.card,
            "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()],
            "source": args.source or "イベント",
            "rarity": args.rarity or "SSR",
        }]
        if args.id is not None:
            entries[0]["id"] = args.id
    if not entries:
        raise LmfdbError("追加する能力が0件です")
    return [dict(e) for e in entries]


def validate_entry(e, index, existing_ids, allow_new_tags):
    """1件分の入力を検証する。問題があれば例外。"""
    where = "入力%d件目" % (index + 1)
    for k in REQUIRED_KEYS:
        if k == "id":
            continue
        if k not in e:
            raise LmfdbError("%s: '%s' がありません" % (where, k))
    for k in ("name", "desc", "card", "source"):
        if not isinstance(e[k], str) or not e[k].strip():
            raise LmfdbError("%s: '%s' は空でない文字列である必要があります" % (where, k))
    if not isinstance(e["tags"], list) or not all(isinstance(t, str) for t in e["tags"]):
        raise LmfdbError("%s: tags は文字列の配列である必要があります" % where)
    if len(e["tags"]) != len(set(e["tags"])):
        raise LmfdbError("%s: tags が重複しています: %s" % (where, e["tags"]))
    if e["source"] not in VALID_SOURCES:
        raise LmfdbError("%s: source が不正です: %r（許可: %s）"
                         % (where, e["source"], "/".join(VALID_SOURCES)))
    if "rarity" in e and e["rarity"] not in VALID_RARITIES:
        raise LmfdbError("%s: rarity が不正です: %r（許可: %s）"
                         % (where, e["rarity"], "/".join(VALID_RARITIES)))
    for k in ("name", "desc", "card"):
        if any(c in e[k] for c in "\n\r\t"):
            raise LmfdbError("%s: '%s' に生の改行/タブが含まれています（desc の改行は <br>）"
                             % (where, k))
        if "</script" in e[k].lower():
            raise LmfdbError("%s: '%s' に </script が含まれています" % (where, k))
    if "id" in e:
        if not isinstance(e["id"], int):
            raise LmfdbError("%s: id が整数ではありません" % where)
        if e["id"] in existing_ids:
            raise LmfdbError("%s: id=%d は既に存在します" % (where, e["id"]))
    unknown = [t for t in e["tags"] if t not in KNOWN_TAGS]
    if unknown:
        msg = "%s: 未知のタグ %s" % (where, unknown)
        if allow_new_tags:
            print("⚠️  %s（--allow-new-tags 指定のため続行）" % msg)
        else:
            raise LmfdbError(
                msg + "\n    表記ゆれでなければ --allow-new-tags を付けるか、"
                "lmfdb_common.py の KNOWN_TAGS に追加してください。"
            )


def main():
    args = parse_args()
    try:
        html = read_html(args.html)
        data, _ = load_abilities(html)
    except (OSError, LmfdbError) as e:
        print("❌ %s" % e)
        return 1

    existing_ids = {a["id"] for a in data if isinstance(a.get("id"), int)}
    existing_pairs = {(a.get("name"), a.get("card")) for a in data}
    next_id = (max(existing_ids) if existing_ids else 0) + 1

    try:
        entries = collect_entries(args)
        for i, e in enumerate(entries):
            validate_entry(e, i, existing_ids, args.allow_new_tags)
    except (OSError, LmfdbError) as e:
        print("❌ %s" % e)
        return 1

    added = []
    for e in entries:
        if "id" not in e:
            e["id"] = next_id
            next_id += 1
        existing_ids.add(e["id"])
        if (e.get("name"), e.get("card")) in existing_pairs:
            print("⚠️  同じ 名前×カード の組が既にあります: %s / %s"
                  % (e.get("name"), e.get("card")))
        existing_pairs.add((e.get("name"), e.get("card")))
        added.append({k: e[k] for k in KEY_ORDER if k in e})

    # ID順を保つため、追加後に安定ソートはせず末尾に追加する
    # （既存データの並びはID昇順が原則で、新規は常に最大ID超なので末尾でよい）
    new_data = data + added

    new_html = replace_abilities(html, new_data)

    # 更新表示（日付・件数）
    old_date, _ = get_update_info(html)
    if args.no_date_update:
        date_str = old_date
    else:
        date_str = args.date or datetime.date.today().strftime("%Y/%m/%d")
    new_html = set_update_info(new_html, date_str, len(new_data))

    # 新カードをレアリティ別リストへ
    card_added = []
    if not args.no_card_list:
        for e in added:
            rarity = e.get("rarity")
            if rarity not in ("SSR", "MR", "SR"):
                continue
            if e.get("source") in ("EXトレ", "伝授"):
                continue  # EX/伝授カードはリスト管理対象外
            listed = get_card_list(new_html, rarity) or []
            if e["card"] in listed:
                continue
            new_html, ok = add_card_to_list(new_html, rarity, e["card"])
            if ok:
                card_added.append((rarity, e["card"]))

    print("追加件数: %d（%d件 → %d件）" % (len(added), len(data), len(new_data)))
    for e in added:
        print("  + id=%d  %s  [%s]  %s" % (e["id"], e["name"], e.get("rarity", "-"), e["card"]))
    if card_added:
        for rarity, card in card_added:
            print("  + %s_CARDS に '%s' を追加" % (rarity, card))
    print("更新表示: %s ／ %d件" % (date_str, len(new_data)))

    if args.dry_run:
        print("\n--- dry-run（書き込みなし）差分プレビュー ---")
        # 巨大な1行同士のdiffは読めないので、追加分のJSONだけ見せる
        print(dump_abilities(added))
        return 0

    write_html(args.html, new_html)
    print("\n✅ %s に書き込みました。次に check.sh を実行してください。" % args.html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
