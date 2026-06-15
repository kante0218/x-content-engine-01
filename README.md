# x-automation-kante

@kante0123(髙橋敢輝 / clear AI株式会社 代表)向け X投稿自動化。
AI・テクノロジー・API・ヒューマノイドなどについて**長文の思考ツイート**を自動生成→推敲→投稿する。

- 認証: OAuth 1.0a User Context(投稿)
- 生成・推敲モデル: Claude Opus 4.8
- 実行: **GitHub Actions cron**(Mac非依存のクラウド実行 / 既定 JST 08:00・20:00)
- ローカル手動実行も可(`scripts/auto_tweet.sh`)

## 仕組み

```
GitHub Actions (cron)  ← Mac が落ちていても動く
  └─ generate_draft.py   # pending が空ならテーマプールから新規ドラフト生成
  └─ pipeline.py         # 最古ドラフトを推敲 → 投稿 → posted/ に移動
       ├─ polish_draft.py  # ペルソナ準拠で長文に推敲
       └─ post_tweet.py    # X API v2 POST /2/tweets
  └─ posted/pending/logs を commit back(重複投稿防止の状態保存)
```

## 投稿軸(6カテゴリ / persona_axis.md と同期)

| ID | テーマ | 比率 |
| --- | --- | --- |
| A | ヒューマノイド/ロボティクス最前線 | 25% |
| B | AIエージェント・自動化の実践 | 20% |
| C | API・開発の手触り | 15% |
| D | 起業家/経営のリアル(clearAI・茨城・資金) | 15% |
| E | 社会課題(人手不足・地方・危険現場) | 15% |
| F | 未来予測・思想 | 10% |

ポジショニング: **ロボットで人手不足×危険現場を解決する起業家**(AIコンサルではない)。一人称「僕」。詳細は `analysis/persona_axis.md`。

## セットアップ

1. `.env.example` を `.env` にコピーし、X Developer App(@kante0123 専用)のキーと `ANTHROPIC_API_KEY` を記入
2. GitHub に private リポジトリ `kante0218/x-automation-kante` を作成して push
3. GitHub の **Settings → Secrets and variables → Actions** に以下を登録:
   - Secrets: `X_CONSUMER_KEY` `X_CONSUMER_SECRET` `X_ACCESS_TOKEN` `X_ACCESS_TOKEN_SECRET` `ANTHROPIC_API_KEY`
   - Variables(任意): `X_MAX_CHARS`(X Premium長文を使うなら `900` など。未設定なら 280)
4. Actions タブ → auto-post → **Run workflow** で dry_run=true を選び動作確認

## 運用コマンド(ローカル)

```bash
# 1本だけドラフト生成
./venv/bin/python3 scripts/generate_draft.py            # --theme A / --force

# 推敲だけ試す(投稿しない)
./venv/bin/python3 scripts/pipeline.py --dry-run

# 生成→推敲→投稿(本番)。.env で X_LIVE_POST=true にしてから
./scripts/auto_tweet.sh
```

## 長文ポストについて

- 通常(無料)アカウントは 1ツイート 280 文字まで → `X_MAX_CHARS=280`(既定)で 275 字前後の密度ある長文を書く。
- **X Premium** 契約なら長文ポストが可能 → `X_MAX_CHARS=900` 等に上げると、推敲も自動でしっかりした長文になる。

## 安全装置

- `.env`/Secrets の `X_LIVE_POST=false`(または dry_run)の間は **投稿されない**(推敲結果をログに書くだけ)
- pending に未投稿が残っていれば `generate_draft.py` はスキップ(投稿待ち列が伸びない)
- 推敲結果が上限文字数を超えたら failed/ に退避して停止
- `concurrency` で多重起動による二重投稿を防止
```
