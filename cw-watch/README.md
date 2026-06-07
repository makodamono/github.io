# CrowdWorks Watcher

クラウドワークスの公開検索ページを10分おきに確認し、応募候補をSlackへ通知します。

## できること

- キーワードごとに新着順で検索
- 案件URL単位で重複通知を防止
- 低優先度/怪しい案件を除外
- Slackへタイトル、URL、報酬、優先度、応募理由、注意点を通知

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

`SLACK_WEBHOOK_URL` が未設定の場合は、Slack通知せずに通知内容を標準出力に表示します。

## 注意

ログイン後ページの自動操作や応募の自動送信はしません。  
通知された案件を見て、応募するかどうかは人間が判断します。

