---
name: lmfdb-ability-add
description: lMfDB（LINEモンスターファーム能力DB）の index.html に能力データを追加・修正する。能力の追加、カードの追加、能力DBの更新、タグやレアリティの修正を頼まれたときに使う。データ検証とcommit/pushまでを含む。
---

# lMfDB 能力追加

`index.html` 一枚に全機能が入った PWA の能力データベースを更新する。
**作業ルールの正典は `tools/lmfdb-ability-add/reference/rules.md`。着手前に必ず読むこと。**

## 使うスクリプト

`tools/lmfdb-ability-add/scripts/` 配下（Codex の `AGENTS.md` と共通）:

| スクリプト | 役割 |
|---|---|
| `add_ability.py` | 能力の追加。ID採番・書式検証・更新表示の同期・カードリスト追加まで自動 |
| `check.sh` | エラーチェック。「✅ 全項目クリア」が出れば合格 |
| `git_commit_push.sh` | **ユーザー承認後の** commit + push |
| `validate.py` | `check.sh` が内部で呼ぶ検証本体（単体でも実行可） |
| `lmfdb_common.py` | 共通ロジック。`KNOWN_TAGS` の追加はここ |

## 手順

1. **最新化** — `git pull --rebase origin main`
2. **ルール確認** — `tools/lmfdb-ability-add/reference/rules.md` を読む
3. **入力を JSON 化** — `name` / `desc` / `card` / `tags` / `source` / `rarity` を用意。
   `id` は書かない（自動採番）
4. **dry-run** — `python3 tools/lmfdb-ability-add/scripts/add_ability.py --json <file> --dry-run`
5. **書き込み** — 上記から `--dry-run` を外して実行
6. **チェック** — `bash tools/lmfdb-ability-add/scripts/check.sh index.html`
   「✅ 全項目クリア」が出るまで直す
7. **承認を取る** — 追加内容・総件数・最大ID・更新日をユーザーに提示して待つ
8. **push** — 承認後のみ
   `bash tools/lmfdb-ability-add/scripts/git_commit_push.sh "add: 〇〇の能力を追加"`

## 画像（スクショ）を渡された場合

スクリプトは画像を扱わない。画像を読むのは**自分の仕事**で、読み取り結果を
JSON に書き起こしてから `add_ability.py` に渡す。

`check.sh` は JSON として正しければ通るため、誤字・数値の取り違え・全角半角の
ズレ・カードの版違い・タグの選択ミスは**検出できない**。したがって手順3の前に:

- 読み取り結果を表で提示する（能力名 / 効果 / カード名 / レアリティ / 入手先 / タグとその理由）
- ユーザーが画像と突き合わせて承認するまで書き込まない

承認ポイントは2回（読み取り確認・push前）になる。
読み取り時の注意（全角数値、`I`/`II` は半角ラテン文字、`<br>` 改行、
画像に無い情報は推測しない）は `reference/rules.md` を参照。

## 絶対に守ること

- `index.html` の `ABILITIES` を**手で編集しない**。必ず `add_ability.py` を通す。
- 既存能力の `id` を変えない・欠番を再利用しない（localStorage が参照している）。
- `ABILITIES` の閉じ括弧直後に並ぶ大量の `;` を消さない。
- `desc` の改行は `<br>`。数値は全角＋`＜ ＞` 囲み。
- タグは既存語彙（`lmfdb_common.py` の `KNOWN_TAGS`）から選ぶ。新語は要相談。
- **チェックが通る前・ユーザー承認が出る前に push しない。**
- 壊したら `git checkout -- index.html` で戻してやり直す。

## 補足

- push / PR ごとに `.github/workflows/check.yml` が `check.sh` を実行する。
  CI は最後の砦なので、ローカルで通してからコミットすること。
- `rarity` は省略不可。無いと SR タブに紛れ込み本来のタブから消える。
  原則としてカードのレアリティをそのまま入れる。
- `source` は `イベント` / `閃き` / `EXトレ` / `伝授` の4種のみ。
- `rarity` は `SSR` / `MR` / `SR` / `その他` の4種のみ。
- 別カードで同名の能力があるのは正常。一意なのは `id` だけ。
- 詳細な表記ルール・トラブル対応表は `reference/rules.md` を参照。
