#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""攻略サイトと比較し、UX改善版の育成モンスターマスターを同期する。"""

import argparse
import datetime as dt
import html as html_lib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_HTML = Path("ux/index.html")
DEFAULT_SOURCE = "https://line-monster-farm-tetteikouryaku.com/monsters.html"
AURAS = {"赤", "青", "黄", "黒", "白", "緑"}
MON_TYPES = {"創造", "幻霊", "魔族", "獣族", "怪物", "無機"}
MASTER_RE = re.compile(r"const MONSTER_MASTER=(\[.*?\]);", re.DOTALL)


def fetch(url: str, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 lMfDB-monster-sync/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"取得に失敗しました: {url} ({exc})") from exc


def parse_listing(page: str, source_url: str) -> list[dict]:
    results = []
    seen = set()
    cards = re.findall(r'<a\s+class="monster-card"[^>]*>.*?</a>', page, re.DOTALL | re.IGNORECASE)
    for card in cards:
        href = re.search(r'\bhref="([^"]+)"', card)
        aura = re.search(r'\bdata-aura="([^"]+)"', card)
        mon_type = re.search(r'\bdata-mon="([^"]+)"', card)
        name = re.search(r'<div\s+class="monster-name">\s*(.*?)\s*</div>', card, re.DOTALL)
        if not (href and aura and mon_type and name):
            continue
        clean_name = html_lib.unescape(re.sub(r"<[^>]+>", "", name.group(1))).strip()
        if not clean_name or clean_name in seen:
            continue
        seen.add(clean_name)
        results.append({
            "name": clean_name,
            "aura": aura.group(1).strip(),
            "type": mon_type.group(1).strip(),
            "url": urllib.parse.urljoin(source_url, href.group(1)),
        })
    if not results:
        raise RuntimeError("一覧ページからモンスターを検出できませんでした（ページ構造変更の可能性）")
    return results


def parse_primary(detail_page: str, name: str) -> str:
    match = re.search(
        r'<span\s+class="bloodline-label">\s*主血統\s*</span>\s*'
        r'<span\s+class="bloodline-value">\s*([^<]+?)\s*</span>',
        detail_page,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"{name}: 詳細ページから主血統を取得できませんでした")
    return html_lib.unescape(match.group(1)).strip()


def load_master(text: str) -> tuple[re.Match, list[dict]]:
    match = MASTER_RE.search(text)
    if not match:
        raise RuntimeError("MONSTER_MASTER を検出できませんでした")
    try:
        master = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"MONSTER_MASTER のJSONが壊れています: {exc}") from exc
    return match, master


def validate(entries: list[dict]) -> None:
    names = set()
    for entry in entries:
        missing = {"name", "aura", "type", "primary"} - set(entry)
        if missing:
            raise RuntimeError(f"必須項目がありません: {sorted(missing)} / {entry}")
        if entry["aura"] not in AURAS:
            raise RuntimeError(f"{entry['name']}: 未知のオーラ {entry['aura']}")
        if entry["type"] not in MON_TYPES:
            raise RuntimeError(f"{entry['name']}: 未知のモン類 {entry['type']}")
        if not entry["primary"]:
            raise RuntimeError(f"{entry['name']}: 主血統が空です")
        if entry["name"] in names:
            raise RuntimeError(f"モンスター名が重複しています: {entry['name']}")
        names.add(entry["name"])


def add_system_history(text: str, additions: list[dict], date_slash: str) -> str:
    date_iso = date_slash.replace("/", "-")
    names = "・".join(entry["name"] for entry in additions)
    article = (
        f'      <article class="update-history-entry"><time datetime="{date_iso}">{date_slash}</time>'
        f'<strong>育成モンスター{len(additions)}体を追加</strong><p>{names}を育成モンスター一覧へ追加しました。</p></article>\n'
    )
    marker = (
        '    <section class="update-history-panel" id="history-system" '
        'role="tabpanel" aria-labelledby="history-tab-system">\n'
    )
    if marker not in text:
        raise RuntimeError("システム更新履歴の挿入位置を検出できませんでした")
    return text.replace(marker, marker + article, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--source-url", default=DEFAULT_SOURCE)
    parser.add_argument("--date", default=dt.date.today().strftime("%Y/%m/%d"))
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = args.html.read_text(encoding="utf-8")
    match, master = load_master(text)
    validate(master)
    existing = {entry["name"] for entry in master}

    listing = parse_listing(fetch(args.source_url, args.timeout), args.source_url)
    candidates = [entry for entry in listing if entry["name"] not in existing]
    if not candidates:
        print(f"✅ 育成モンスター更新なし（登録済み {len(master)}体）")
        return 0

    additions = []
    for candidate in candidates:
        primary = parse_primary(fetch(candidate["url"], args.timeout), candidate["name"])
        additions.append({
            "name": candidate["name"],
            "aura": candidate["aura"],
            "type": candidate["type"],
            "primary": primary,
        })
    validate(master + additions)

    print(f"新規育成モンスター: {len(additions)}体（{len(master)}体 → {len(master) + len(additions)}体）")
    for entry in additions:
        print(f"  + {entry['name']} / {entry['aura']} / {entry['type']} / 主血統 {entry['primary']}")
    if args.dry_run:
        print("\n--- dry-run（書き込みなし）---")
        print(json.dumps(additions, ensure_ascii=False, indent=2))
        return 0

    new_master = master + additions
    encoded = json.dumps(new_master, ensure_ascii=False, separators=(",", ":"))
    text = text[:match.start(1)] + encoded + text[match.end(1):]
    text = add_system_history(text, additions, args.date)
    text = re.sub(
        r'(document\.getElementById\(\'db-update-info\'\)\.innerHTML=`更新: )\d{4}/\d{2}/\d{2}',
        rf'\g<1>{args.date}',
        text,
        count=1,
    )
    args.html.write_text(text, encoding="utf-8", newline="\n")
    print(f"✅ {args.html} に書き込みました")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)
