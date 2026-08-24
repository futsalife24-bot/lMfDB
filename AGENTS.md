# AGENTS.md — lMfDB

> ## UX改善版本運用（2026/08/24〜）
>
> 能力データの唯一の正本は **`ux/index.html`**。能力の追加・修正・検証・CI・commit対象はすべてこのファイルに限定する。
> ルートの `index.html` はUX改善版へ案内する公開入口であり、能力データは更新しない。
> 以下の旧記述にある `index.html` は、能力データ作業では `ux/index.html` と読み替える。

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
.github/workflows/check.yml push / PR ごとに check.sh を実行する CI
```

CI があるので壊れたまま main に入ることは無いが、**ローカルで check.sh を
通してからコミットする**のが原則（CI は最後の砦）。

## 能力追加をするとき

**作業ルールの正典は `tools/lmfdb-ability-add/reference/rules.md`。
着手前に必ず読むこと。** このファイルは入口の要約にすぎない。

`tools/lmfdb-ability-add/scripts/` のスクリプトを使う
（`.claude/skills/lmfdb-ability-add/SKILL.md` と同じものを参照している）:

| スクリプト | 役割 |
|---|---|
| `add_ability.py` | 能力の追加。ID採番・書式検証・更新表示・能力更新履歴・カードリストの同期まで自動 |
| `check.sh` | エラーチェック。「✅ 全項目クリア」が出れば合格 |
| `git_commit_push.sh` | **チェック成功後に自動実行する** commit + push |
| `validate.py` | `check.sh` が内部で呼ぶ検証本体 |
| `lmfdb_common.py` | 共通ロジック。`KNOWN_TAGS` の追加はここ |

### 更新履歴（能力更新タブ）

- **能力を追加するたび、改善版の「能力更新」履歴にも必ず1件追加する。**
  `add_ability.py` がカード名・入手先・追加件数から、見出しと説明を自動生成して先頭へ記録する。
- 特別な表現が必要な場合のみ、`--history-title` と `--history-desc` で上書きする。
  履歴を省略するオプションは設けない。
### 手順

```bash
git pull --rebase origin main

# 追加内容を JSON にまとめて dry-run
python3 tools/lmfdb-ability-add/scripts/add_ability.py --json /tmp/new.json --dry-run

# 問題なければ書き込み
python3 tools/lmfdb-ability-add/scripts/add_ability.py --json /tmp/new.json

# チェック（「✅ 全項目クリア」が出るまで直す）
bash tools/lmfdb-ability-add/scripts/check.sh ux/index.html

# チェック成功後は自動で commit + push
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

### 画像（スクショ）を渡された場合

スクリプトは画像を扱わない。**画像を読むのはこちらの仕事**で、読み取り結果を
JSON に書き起こしてから `add_ability.py` に渡す。

`check.sh` は JSON として正しければ通ってしまい、誤字・数値の取り違え・
全角半角のズレ・カードの版違い・タグの選択ミスは**検出できない**。
そのため、通常は xhigh 相当の読み取りを前提に自動処理する。ただし、画像が
不鮮明・情報が欠落・タグ/レアリティ/入手先の判断に迷う場合は、勝手に進めず
ユーザーに質問する。明確に読み取れる場合は:

1. 読み取り結果を JSON 化する（表提示・確認は省略可）
2. 通常手順（dry-run → 書き込み → check.sh）を実行する
3. チェック成功後、内容を簡潔に報告して自動で commit + push する

この自動承認は、メロニキから明示的に許可された lMfDB の能力追加作業に限る。
詳細と読み取り時の注意は `reference/rules.md` の「画像から追加する場合」を参照。

## 絶対に守ること

- `ux/index.html` の `ABILITIES`（1行の巨大 JSON 配列）を**手で編集しない**。
  必ず `add_ability.py` を通す。
- 既存能力の `id` を変えない・欠番を再利用しない（localStorage が参照している）。
- `ABILITIES` の閉じ括弧直後に並ぶ大量の `;` を消さない。
- `desc` の改行は `<br>`。数値は全角＋`＜ ＞` 囲み（例: `＜＋３０％＞`）。
- `desc` / `name` / `card` に `</script` を入れない（ページが壊れる）。
- タグは既存語彙（`lmfdb_common.py` の `KNOWN_TAGS`、現在55種）から選ぶ。
- `source` は `イベント` / `閃き` / `EXトレ` / `伝授` のみ。
- `rarity` は `SSR` / `MR` / `SR` / `その他` のみ。
- **`check.sh` が通る前に push しない。** チェック成功後は、明示的な追加承認なしで
  `git_commit_push.sh` を実行する。
- 壊したら `git checkout -- ux/index.html` で戻してやり直す。

## コミット規約

`add:` 能力・ページの追加 / `fix:` データ誤りの修正 / `chore:` ツール・設定の変更。
push 先は `main`。能力追加のコミットに `tools/` や `.claude/` の変更を混ぜない。
