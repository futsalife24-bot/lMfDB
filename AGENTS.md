# AGENTS.md — lMfDB

LINEモンスターファーム能力DB。**`index.html` 一枚に全機能が入った PWA**
（HTML + CSS + JS + データが全部この中）。ビルド工程は無く、`main` に push した
ものがそのまま GitHub Pages で公開される。

## リポジトリ構成

```
index.html                  公開本体。能力データ ABILITIES もここ
manifest.json / sw.js       PWA 用
icon-192.png / icon-512.png アイコン
lom-hiden-guide.html        秘伝ガイド
lom-hiden-infographic.html  秘伝ガイド（インフォグラフィック版）
AGENTS.md                   このファイル（Codex 用）
.claude/skills/             ClaudeCode 用 Skill
tools/lmfdb-ability-add/    能力追加ツール一式（ClaudeCode / Codex 共通）
```

## 能力追加をするとき

**作業ルールの正典は `tools/lmfdb-ability-add/reference/rules.md`。
着手前に必ず読むこと。** このファイルは入口の要約にすぎない。

`tools/lmfdb-ability-add/scripts/` のスクリプトを使う
（`.claude/skills/lmfdb-ability-add/SKILL.md` と同じものを参照している）:

| スクリプト | 役割 |
|---|---|
| `add_ability.py` | 能力の追加。ID採番・書式検証・更新表示の同期・カードリスト追加まで自動 |
| `check.sh` | エラーチェック。「✅ 全項目クリア」が出れば合格 |
| `git_commit_push.sh` | **ユーザー承認後の** commit + push |
| `validate.py` | `check.sh` が内部で呼ぶ検証本体 |
| `lmfdb_common.py` | 共通ロジック。`KNOWN_TAGS` の追加はここ |

### 手順

```bash
git pull --rebase origin main

# 追加内容を JSON にまとめて dry-run
python3 tools/lmfdb-ability-add/scripts/add_ability.py --json /tmp/new.json --dry-run

# 問題なければ書き込み
python3 tools/lmfdb-ability-add/scripts/add_ability.py --json /tmp/new.json

# チェック（「✅ 全項目クリア」が出るまで直す）
bash tools/lmfdb-ability-add/scripts/check.sh index.html

# ★ここでユーザーに内容を提示して承認を取る★

# 承認後のみ
bash tools/lmfdb-ability-add/scripts/git_commit_push.sh "add: 〇〇の能力を追加"
```

入力 JSON の1件の形（`id` は書かない。自動採番される）:

```json
{
  "name": "横一閃 III",
  "desc": "[前半]＜白＞技発動時、ちからステ＜＋４０％＞",
  "card": "ロクショウ",
  "tags": ["前半", "オーラ白", "攻撃強化"],
  "source": "イベント",
  "rarity": "SSR"
}
```

## 絶対に守ること

- `index.html` の `ABILITIES`（1行の巨大 JSON 配列）を**手で編集しない**。
  必ず `add_ability.py` を通す。
- 既存能力の `id` を変えない・欠番を再利用しない（localStorage が参照している）。
- `ABILITIES` の閉じ括弧直後に並ぶ大量の `;` を消さない。
- `desc` の改行は `<br>`。数値は全角＋`＜ ＞` 囲み（例: `＜＋３０％＞`）。
- `desc` / `name` / `card` に `</script` を入れない（ページが壊れる）。
- タグは既存語彙（`lmfdb_common.py` の `KNOWN_TAGS`、現在55種）から選ぶ。
- `source` は `イベント` / `閃き` / `EXトレ` / `伝授` のみ。
- `rarity` は `SSR` / `MR` / `SR` / `その他` のみ。
- **チェックが通る前・ユーザー承認が出る前に push しない。**
- 壊したら `git checkout -- index.html` で戻してやり直す。

## コミット規約

`add:` 能力・ページの追加 / `fix:` データ誤りの修正 / `chore:` ツール・設定の変更。
push 先は `main`。能力追加のコミットに `tools/` や `.claude/` の変更を混ぜない。
