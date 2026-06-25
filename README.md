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

コードの意図から読み取れる機能要件を満たしていること、必要に応じて非機能要件も満たしていることを確認するテスト方針、
テストしたい機能要件 / 非機能要件に応じたファイル分割、同値分割・境界値分析・デシジョンテーブルなどのケース設計、
`機能要件：` / `非機能要件：` コメント、Given-When-Then の記述スタイル、短い英語関数名と日本語 docstring の方針は
[`tests/README.md`](tests/README.md) を参照してください。

### 一括チェック

```bash
mise run check
```

`mise run lint` は `ruff check . --fix` を実行するため、ファイルを書き換える可能性があります。

## 移行スクリプト

V2 から V3 への DB 移行補助スクリプトを用意しています。
移行先 DB は空の DB を指定してください。スクリプトは Alembic の初期 revision `273b6467e5ff` まで
スキーマを作成してから V2 のデータを投入し、最後に最新 revision までマイグレーションを適用します。

```bash
uv run python scripts/v2_to_v3_migration.py \
  --source-database-url "mysql://user:password@127.0.0.1:3306/asteroid_v2" \
  --target-database-url "mysql://user:password@127.0.0.1:3306/asteroid_v3"
```

引数を省略した場合は対話的に接続情報を入力できます。
このスクリプトを使用した場合、`alembic_version` はスクリプト内の Alembic 実行で更新されるため、
手動で `uv run alembic stamp ...` を実行する必要はありません。

## Alembic によるスキーマ管理

データベースは Alembic を使用して管理しています。Bot 起動時に DB の Alembic revision を確認し、未適用または古い revision の DB では起動を停止します。

### 既存の DB を Alembic の管理下に置く方法

既にテーブルが存在する DB に初期マイグレーションをそのまま適用しないでください。`stamp` は DB のスキーマを変更せず revision だけを記録する操作です。対象 DB のスキーマと記録する revision が一致していることを確認したうえで、実行するようにしてください。

例えば、現在の既存 DB が初期 baseline と一致している場合は次のように記録します。

```bash
uv run alembic stamp 273b6467e5ff
```

これは一例です。既存 DB の実スキーマが別の revision に対応する場合は、その revision を指定してください。`head` を安易に stamp すると、未適用のテーブル追加やカラム変更まで適用済み扱いになるため避けてください。

`stamp` 後は、必要な後続マイグレーションを適用します。

```bash
mise run db:upgrade
```
生成されたマイグレーションに現在の全テーブル作成処理が含まれていることを確認してください。

### 新規 DB に適用する場合

テーブルが存在しない新規 DB では、全マイグレーションをそのまま適用します。

```bash
uv run alembic upgrade head
```

### 既存 DB を Alembic 管理下に置く場合

既にテーブルが存在し、`alembic_version` が無い DB では、作業前に必ず DB のバックアップを取得してください。その上で、初期マイグレーションは実行せず、既存 DB に初期スキーマが適用済みであることだけを記録します。

```bash
uv run alembic stamp 273b6467e5ff
```

その後、初期 revision より後のマイグレーションを適用します。

```bash
uv run alembic upgrade head
```

`stamp head` を実行すると、後続マイグレーションまで適用済みとして記録されます。既存 DB に index 追加などの差分を実際に適用したい場合は、`stamp head` ではなく、初期 revision である `273b6467e5ff` に stamp してから `upgrade head` を実行してください。

現在の適用状態は次のコマンドで確認できます。

```bash
uv run alembic current
```

既に Alembic 管理下にある DB では、通常通り未適用分を反映します。

```bash
uv run alembic upgrade head
```

### DB の更新を適用する方法

新規 DB または Alembic 管理下の既存 DB では、起動前に最新 revision までマイグレーションを適用します。

```bash
mise run db:upgrade
```

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

### DB の更新を Alembic へ登録する方法

テーブルやカラムを追加・変更・削除した場合は、マイグレーションを作成します。`config.yaml` の `database.url` に指定した DB の構造との差異を生成します。

```bash
mise run db:revision "変更内容"
```

生成されたマイグレーションは必ず確認し、意図したテーブル、カラム、制約、index、default だけが含まれていることを確認してください。
