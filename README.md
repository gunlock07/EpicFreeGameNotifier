# Epic Free Game Notifier — GitHub Actions + Discord BOT

**PCを起動しなくても**新規無料配布・次回無料配布予告・配布終了前の通知をDiscordに投稿するクラウド構成です。

- 通知：GitHub Actions（30分ごとの実行、遅延する場合あり）→ Discord Bot API
- スラッシュコマンド：Cloudflare Workers（HTTP Interactions）→ Epic Games情報
- 通知履歴：`state.json` をGitHubリポジトリへ自動コミットして保存（重複防止）
- 言語・対象地域：日本語 / 日本（日時もJST）
- 初回起動時：配布中・予告済みの情報も送信。既存配布の新規通知のみ省略したい場合、`notify.yml` 内の `SKIP_EXISTING_ON_FIRST_RUN` を `true` にしてください。

**重要：GitHub Actionsだけでは常時Discordコマンドを受信できません。** このためコマンド受付にはCloudflare Workers（無料枠利用可能）を組み合わせています。Workersはコマンド実行時だけ起動し、常時稼働PCやVPSは不要です。

## 1. Discord BOTを作る

1. https://discord.com/developers/applications で **New Application** → 任意の名前（例：Epic Free Game Notifier）。
2. **General Information** の `APPLICATION ID` と `PUBLIC KEY` を控える。
3. **Bot** → Bot Token を生成/再発行して控える（**他人に渡さない**）。
4. **Installation** で `Guild Install` を有効にし、`bot` と `applications.commands` を利用できるようにする。BOTの権限は `View Channels` / `Send Messages` / `Embed Links` を選択。
5. DiscordのBOTを入れるサーバーにインストールする（Developer Portalのインストールリンクを使用）。
6. Discordの **開発者モード** を有効にし、通知先テキストチャンネルを右クリック→**チャンネルIDをコピー**。ロール宛てに通知する場合はロールIDも控える（任意）。

## 2. GitHubにアップロードして定期通知を設定

1. https://github.com/new で**Private**リポジトリを作成（公開する場合は `state.json` の通知履歴も閲覧可能）。
2. このZIPを展開し、**`EpicFreeGameNotifier_Cloud` 内のファイルと `.github` フォルダを含めて**リポジトリの最上位へアップロード。`.github/workflows/notify.yml` が正しい位置にあることを確認。
3. `Settings → Secrets and variables → Actions` に進む。
4. **Repository secrets** に `DISCORD_BOT_TOKEN`（トークン）。
5. **Repository variables** に `DISCORD_CHANNEL_ID` と `DISCORD_APPLICATION_ID` を登録。ロール通知したければ `DISCORD_ROLE_ID` も設定。
6. `Settings → Actions → General → Workflow permissions` で **Read and write permissions** を選択（`state.json` をコミットするため）。デフォルトブランチのブランチ保護でpushできない設定は避ける。
7. `Actions → Epic free game notifications → Run workflow` で手動実行し、通知が来ることと `state.json` が更新されたことを確認。
8. 以降は30分ごと（UTC各時17分・47分）にチェック。**GitHub Actionsの混雑時には遅延・実行欠落があり、厳密な通知時刻は保証されません。** GitHubの仕様により長期間非アクティブな公開リポジトリのスケジュールが無効化される場合があります。

## 3. Cloudflare Workersでコマンド受付を設定

1. https://dash.cloudflare.com/ でCloudflareアカウントを作成（無料枠で使用可能）。
2. PCにNode.js（LTS版）をインストール。
3. 端末で次のように実行：

```bash
cd worker
npm install
npx wrangler login
npx wrangler secret put DISCORD_PUBLIC_KEY
```

4. 最後のコマンドでDiscord Developer Portalの **Public Key** を入力する。`DISCORD_BOT_TOKEN` ではありません。
5. `npx wrangler deploy` を実行して表示された `https://epic-free-game-interactions.<subdomain>.workers.dev` を控える。
6. Discord Developer Portal → **General Information** → **Interactions Endpoint URL** にそのURLを入力して保存（必要なら末尾に `/`）。Discordが署名付きPINGで検証します。
7. コマンド登録はGitHubの `Actions → Register slash commands → Run workflow` を実行。しばらくしてDiscordに `/無料ゲーム` `/次回配布` `/ヘルプ` が現れます。

Cloudflare WorkerはコマンドごとにEpic APIを照会し、実行者にだけ見えるエフェメラルメッセージで返答します。

## コマンド

| コマンド | 動作 |
|---|---|
| `/無料ゲーム` | 現在の無料配布一覧。終了時刻とストアリンクを表示 |
| `/次回配布` | 公開済みの次回無料配布予告（開始時刻とリンク） |
| `/ヘルプ` | 使い方を表示 |

## 自動通知

- **新規無料配布**：現在の無料配布の新たな開始を確認したら1回だけ通知。
- **次回無料配布予告**：`upcomingPromotionalOffers` に新しく登場したゲームについて1回だけ通知。
- **終了24時間前**：次の定期チェックの時点で終了まで24時間以内なら1回通知。ぴったり24時間前の通知は保証されません。
- **重複防止**：`ゲームID | 配布開始日時` と通知種別を `state.json` に記録。送信成功の後に状態を書きます。GitHubのコミットが失敗した場合には再通知される可能性があります。
- **ミステリーゲーム**：Epicがゲーム名を公開していない場合、実際にAPIに存在する表示名で通知。未公開ゲームの正体を推測しません。

## 注意点・トラブルシュート

- Epic側の非公式ストアAPIが変更された場合、プログラムの改修が必要になる可能性があります。
- ゲームごとに地域制限があるため、日本で利用できない商品が混じる可能性があります。
- `/無料ゲーム` が応答しない場合はWorkersのログ・Interactions Endpoint URL・Public Keyを確認してください。
- Discord APIの `403` はBOTのチャンネル権限不足、`401` はBOTトークン誤りの可能性があります。
- Actionsが `git push` で失敗する場合は Workflow permissions、ブランチ保護、リポジトリ構成を確認してください。
- セキュリティのためBOTトークンはSecret、Public KeyはWorker Secretに設定します。コードやコミットへ貼り付けないでください。
- 同じタイトルの同じ配布期間をBOTが繰り返し送信することは防ぎますが、外部からの二重実行やAPI変更などで稀に重複する可能性があります。
- 初回は、すでに終了まで24時間以内のゲームにも「新規」と「終了前」の2種類の通知が送られることがあります。
- GitHub Actionsは常時起動するサーバーではなく定期起動です。DiscordコマンドはWorkersが応答します。

## 同梱ファイル

```text
EpicFreeGameNotifier_Cloud/
├─ .github/workflows/notify.yml             定期通知
├─ .github/workflows/register_commands.yml コマンド登録
├─ epic.py                                  Epicデータ取得・分類
├─ notifier.py                              Discordへの通知と状態保存
├─ register_commands.py                     スラッシュコマンド登録
├─ state.json                               送信済みIDを永続保存
├─ worker/
│  ├─ index.js                               コマンド受付・署名検証
│  ├─ package.json
│  └─ wrangler.toml
└─ tests/test_epic.py                       モックデータでのユニットテスト
```

## 動作テスト

```bash
python -m unittest discover -s tests -v
```

上記はAPIアクセスなしのテストです。実際のDiscord投稿・Worker URL設定・Epicへのアクセスはユーザーの環境でデプロイして確認する必要があります。
