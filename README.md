# Asteroid_V3

Discordサーバー「ナメック星」で利用する専用 Discord Bot の3代目です。  
`discord.py` を使用しており、様々なサーバー運用機能を提供します。

## 実行環境

ツール  | バージョン | 備考
------ | --------- | ---
Python | >=3.14    |
uv     | latest    | 依存関係管理・実行ツール
MySQL  | -         | データベース
Mise   | latest    | タスクランナー
Docker | -         | コンテナ化（任意）

本 README では Mise を使用している前提でコマンドを記載しています。Mise を使用しない場合は、
`mise.toml` 内のコマンドを参考に、適宜 `uv run` コマンドを使用して実行してください。

## ディレクトリ構成

```text
app/
  core/          Bot 本体、設定、ロギング、拡張機能ロード
  common/        コマンド登録、権限、型 narrowing、共通 UI / utility
  features/      各 Discord 機能の Cog / command / service / view
  database/      DB モデル、リポジトリ、セッション管理
.agents/         AI エージェント向け共有スキルと運用メモ
scripts/         補助・移行スクリプト
tests/           pytest テスト
launch_app.py    Bot のエントリーポイント
mise.toml        ローカルタスク定義
pyproject.toml   Python 依存関係・Ruff 設定・開発ツール定義
```

## 各機能の要約

機能 | 概要
--- | ---
`auth` | 画像式の CAPTCHA を使用した、シンプルな認証システムを提供する
`birthday` | 誕生日の登録を行うことでお祝いメッセージが送信される
`bump_notifier` | [Disboard](https://disboard.org/ja) / [Dissoku](https://dissoku.net/ja) / [Dicoall](https://jp.dicoall.com/ja) の BUMP・UP 通知を検知し、クールダウン後に通知を送信する
`free_category` | ユーザーが自由なトピックのチャンネルを作成することができる「フリーカテゴリー」システムを提供する
`leveling` | テキスト / VC 活動に応じたレベルシステムを提供する
`link_expander` | Discord メッセージリンクの内容を展開表示する
`log_login` | Bot の起動通知を送信する
`log_error` | コマンドや UI などの未捕捉エラー通知を送信する
`punish` | 管理者がより簡単に規約違反者へ処罰を行うためのシステムを提供する
`report` | ユーザーが違反者を管理者へ通報するシステムを提供する
`rolepanel` | ロールパネルの作成・管理と、ブースト条件付きロール付与を行う
`roles` | サーバー参加時のロール自動付与や、帰還者のロール復元を行う
`starboard` | 「⭐️」のリアクションで面白いメッセージ等を保存することができるシステムを提供する
`suggest` | 要望チャンネルにおける可決 / 否決の管理コマンドを提供する
`vc` | ユーザーが自由なトピックのボイスチャンネルを作成できるシステムを提供する

## セットアップ

### 1. 依存関係をインストール

```bash
mise run sync
```


### 2. 設定ファイルを作成

`config.example.yaml` をコピーして `config.yaml` を作成し、内容を編集してください。

```bash
cp config.example.yaml config.yaml
```

`database.url` は SQLAlchemy 形式の接続 URL です。MySQL を使う場合は次の形式を推奨します。

```text
mysql+aiomysql://user:password@127.0.0.1:3306/database
```

補足:
- `mysql://...` を指定した場合は実行時に `mysql+aiomysql://...` へ補正されます
- `features` セクションで各機能の ON / OFF を切り替えられます
- `discord.guild_id` は Bot の運用対象サーバー ID です
- `discord.sync_commands_on_startup` で起動時のコマンド同期を制御できます
- 未設定項目の多くは安全なデフォルト値 `0` または空配列で補完されます

### 3. Bot を起動

```bash
mise run start
```


## 開発用ツール

### Lint / Format / Typecheck

```bash
mise run lint
mise run format
mise run typecheck
```

### テスト

```bash
mise run test
```

### 一括チェック

```bash
mise run check
```

`mise run lint` は `ruff check . --fix` を実行するため、ファイルを書き換える可能性があります。

### Alembic

```bash
mise run db:revision "変更内容"
mise run db:upgrade
mise run db:stamp
mise run db:test-migrations
```

`db:revision` は `alembic revision --autogenerate -m` を実行します。生成されたマイグレーションは必ず確認し、意図しない差分が混ざっていないか確認してください。

## 移行スクリプト

V2 から V3 への DB 移行補助スクリプトを用意しています。

```bash
uv run python scripts/v2_to_v3_migration.py \
  --source-database-url "mysql://user:password@127.0.0.1:3306/asteroid_v2" \
  --target-database-url "mysql://user:password@127.0.0.1:3306/asteroid_v3"
```

引数を省略した場合は対話的に接続情報を入力できます。

## Alembic によるスキーマ管理

既に作成済みの DB を Alembic 管理下に置く場合、既存 DB に初期マイグレーションをそのまま適用しないでください。初期マイグレーションは新規環境を作れるように残し、既存 DB には現在のスキーマが適用済みであることを記録します。

初期マイグレーションを作成する場合は、空の開発用 DB を `config.yaml` の `database.url` に指定してから実行します。

```bash
mise run db:revision "init"
```

生成されたマイグレーションに現在の全テーブル作成処理が含まれていることを確認してください。既にテーブルが存在する本番・既存 DB では、この初期マイグレーションを実行せず、現在の revision を適用済みとして記録します。

```bash
mise run db:stamp
```

以後のテーブル構成変更では、通常通りマイグレーションを生成して適用します。

```bash
mise run db:revision "変更内容"
mise run db:upgrade
```

Bot 起動時のテーブル作成処理は削除したため、スキーマ管理は Alembic に寄せて管理してください。
Bot 起動時には DB の Alembic revision を確認します。未適用または古い revision の DB では起動を停止するため、起動前に `stamp head` または `upgrade head` を実行してください。

Docker で運用する場合も、Bot 起動とは別にマイグレーションを明示的に実行します。Docker image には `alembic.ini` と `app/database/migrations/` が含まれている必要があります。

```bash
docker run --rm \
  -v /path/to/config.yaml:/app/config.yaml:ro \
  asteroid-v3 \
  alembic upgrade head
```

マイグレーション成功後に Bot を起動します。

```bash
docker run -d \
  -v /path/to/config.yaml:/app/config.yaml:ro \
  --name asteroid-v3 \
  asteroid-v3
```
