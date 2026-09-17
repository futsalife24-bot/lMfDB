# 共通管理画面への計測（2026-09-17）

本運用入口 `ux/index.html` の表示回数を既存Swarm Workerの共通管理画面へ集計する。能力・育成データは不変。IDはアプリ別のランダム値、Cookie/URL/Referer/保存内容は送らない。保存不可ならアクセスのみ集計。DNT/GPC/developer=1/analytics=offを除外。通信失敗は画面を止めない。

`ux/sw.js`はPOSTと別originをキャッシュ対象外にする（計測POSTをCache.putへ渡さない）。PWAのGET/オフラインは従来どおり。

既存check.sh全項目成功。Windows CRLFがJSON同期の厳密文字列比較に影響するため、検証時のみdata/abilities.jsonの改行をLFへ正規化。内容差分なし。ブラウザでは実スニペットの送信・同ブラウザの重複排除・開発者除外・通信失敗継続をローカルWorkerで確認。本番へのテスト送信なし。独立監査・公開前。
