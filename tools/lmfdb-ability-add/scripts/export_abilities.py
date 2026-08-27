#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ux/index.html の実効能力データを決定的なJSONとして出力する。"""

import argparse
import collections
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lmfdb_common import (  # noqa: E402
    KEY_ORDER,
    LmfdbError,
    apply_data_fixes,
    load_abilities,
    read_html,
)

SCHEMA_VERSION = 1
DEFAULT_HTML = "ux/index.html"
DEFAULT_OUTPUT = "data/abilities.json"
DOCUMENT_KEYS = ("schemaVersion", "generatedFrom", "counts", "abilities")


def build_document(html, generated_from=DEFAULT_HTML):
    """公開画面と同じ DATA_FIXES 適用後のエクスポート文書を返す。"""
    abilities, _ = load_abilities(html)
    effective = apply_data_fixes(abilities, html)
    exported = []
    for index, ability in enumerate(effective):
        if not isinstance(ability, dict):
            raise LmfdbError("ABILITIES の%d件目がオブジェクトではありません" % (index + 1))
        missing = [key for key in KEY_ORDER if key not in ability]
        if missing:
            raise LmfdbError(
                "id=%s: エクスポート必須キーがありません: %s"
                % (ability.get("id", "?"), ", ".join(missing))
            )
        exported.append({key: ability[key] for key in KEY_ORDER})
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedFrom": generated_from,
        "counts": {"abilities": len(exported)},
        "abilities": exported,
    }
    validate_document(document)
    return document


def validate_document(document):
    """公開JSONのスキーマ、件数、ID、レコード型を検証する。"""
    if not isinstance(document, dict) or tuple(document) != DOCUMENT_KEYS:
        raise LmfdbError("エクスポートJSONのトップレベル構造が不正です")
    if document["schemaVersion"] != SCHEMA_VERSION:
        raise LmfdbError("schemaVersion が不正です")
    if not isinstance(document["generatedFrom"], str):
        raise LmfdbError("generatedFrom が文字列ではありません")
    counts = document["counts"]
    if not isinstance(counts, dict) or tuple(counts) != ("abilities",):
        raise LmfdbError("counts の構造が不正です")
    abilities = document["abilities"]
    if not isinstance(abilities, list):
        raise LmfdbError("abilities が配列ではありません")
    if counts["abilities"] != len(abilities):
        raise LmfdbError("counts.abilities と abilities の件数が一致しません")

    ids = []
    for index, ability in enumerate(abilities):
        if not isinstance(ability, dict) or tuple(ability) != KEY_ORDER:
            raise LmfdbError("abilities の%d件目の構造が不正です" % (index + 1))
        if not isinstance(ability["id"], int) or isinstance(ability["id"], bool):
            raise LmfdbError("abilities の%d件目の id が整数ではありません" % (index + 1))
        for key in ("name", "desc", "card", "source", "rarity"):
            if not isinstance(ability[key], str):
                raise LmfdbError("id=%s: %s が文字列ではありません" % (ability["id"], key))
        if not isinstance(ability["tags"], list) or not all(
            isinstance(tag, str) for tag in ability["tags"]
        ):
            raise LmfdbError("id=%s: tags が文字列配列ではありません" % ability["id"])
        ids.append(ability["id"])
    duplicates = [aid for aid, count in collections.Counter(ids).items() if count > 1]
    if duplicates:
        raise LmfdbError("ID が重複しています: %s" % sorted(duplicates))


def render_export(html, generated_from=DEFAULT_HTML):
    """末尾改行1つ、日本語を保持した決定的JSON文字列を返す。"""
    return json.dumps(
        build_document(html, generated_from),
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def write_export_atomic(path, content):
    """完全なJSONを同一ディレクトリの一時ファイルへ書いてから置換する。"""
    parsed = json.loads(content)
    validate_document(parsed)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=directory, delete=False
        ) as temp:
            temp.write(content)
            temp.flush()
            os.fsync(temp.fileno())
            temp_path = temp.name
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", default=DEFAULT_HTML, help="入力HTML")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="出力JSON")
    parser.add_argument(
        "--check",
        action="store_true",
        help="再生成内容と既存JSONを比較し、差があれば終了コード1にする",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        html = read_html(args.html)
        content = render_export(html, DEFAULT_HTML)
        if args.check:
            with open(args.output, "r", encoding="utf-8", newline="") as stream:
                current = stream.read()
            try:
                validate_document(json.loads(current))
            except (json.JSONDecodeError, LmfdbError) as exc:
                raise LmfdbError("既存JSONが不正です: %s" % exc)
            if current != content:
                print("❌ %s は %s の実効能力データと同期していません" % (args.output, args.html))
                return 1
            print("✅ %s は %s と同期しています（%d件）" % (
                args.output, args.html, build_document(html)["counts"]["abilities"]
            ))
            return 0
        write_export_atomic(args.output, content)
        print("✅ %s を生成しました（%d件）" % (
            args.output, build_document(html)["counts"]["abilities"]
        ))
        return 0
    except (OSError, json.JSONDecodeError, LmfdbError) as exc:
        print("❌ %s" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
