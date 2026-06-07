# CrowdWorks Watcher

クラウドワークスの公開検索ページを10分おきに確認し、応募候補をSlackへ通知します。

## できること

- キーワードごとに新着順で検索
- ジャンルごとに関連キーワードとカテゴリURLをまとめて検索
- Web制作などのカテゴリ/グループ一覧も巡回
- クラウドワークス内検索で拾えない公開案件はBing RSS検索で補助取得
- 案件URL単位で重複通知を防止
- 募集終了/時給案件以外の新着案件をSlackへ通知
- Slackへタイトル、URL、報酬、優先度、応募理由、注意点を通知
- 現在は `CW_NOTIFY_PRIORITIES=高` で高優先度のみ通知

## GitHub Secrets

リポジトリの `Settings > Secrets and variables > Actions` に以下を登録します。

```txt
SLACK_WEBHOOK_URL
```

## 手動実行

```bash
cd cw-watch
python3 watch_crowdworks.py
```

## 設定ファイル

- `keywords.json`: キーワード検索用
- `sources.json`: カテゴリ/グループ一覧ページ用
- `genres.json`: ジャンル別の検索キーワード/カテゴリURL用
- `seen_jobs.json`: 通知済みURLの保存用

`SLACK_WEBHOOK_URL` が未設定の場合は、Slack通知せずに通知内容を標準出力に表示します。

`CW_WEB_FALLBACK=false` を設定すると、Bing RSS検索による補助取得を停止できます。

`CW_NOTIFY_PRIORITIES=高,中` のように設定すると、通知する優先度を変更できます。

## 注意

ログイン後ページの自動操作や応募の自動送信はしません。  
通知された案件を見て、応募するかどうかは人間が判断します。
