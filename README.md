# Asteroid_V3

Discordサーバー「ナメック星」で利用する専用 Discord Bot の3代目です。  
`discord.py` を使用しており、様々なサーバー運用機能を提供します。

## 実行環境

ツール  | バージョン | 備考
------ | --------- | ---
Python | >=3.14    |
uv     | latest    | 依存関係管理・実行ツール
MySQL  | -         | データベース
Mise   | latest    | タスクランナー（任意）
Docker | -         | コンテナ化（任意）

Mise の使用は任意ですが、本 README では Mise を使用している前提でコマンドを記載しています。

Mise を使用しない場合は、 `mise.toml` 内のコマンドを参考に、適宜 `uv run` コマンドを使用して実行してください。

## ディレクトリ構成

```text
app/
  core/        Bot 本体、設定、ロギング、拡張機能ロード
  features/    各 Discord 機能の Cog / service / view
  database/    DB モデル、リポジトリ、セッション管理
scripts/       補助スクリプト
tests/         pytest テスト
launch_app.py  BOTのエントリーポイント
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
`log` | BOT の起動通知およびエラーログ送信を行う
`punish` | 管理者がより簡単に規約違反者へ処罰を行うためのシステムを提供する
`report` | ユーザーが違反者を管理者へ通報するシステムを提供する
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

`database.url` は SQLAlchemy 形式の接続 URL です。MySQL を使う場合は次の形式を推奨します。

```text
mysql+aiomysql://user:password@127.0.0.1:3306/database
```

補足:
- `mysql://...` を指定した場合は実行時に `mysql+aiomysql://...` へ補正されます
- `features` セクションで各機能の ON / OFF を切り替えられます
- 未設定項目の多くは安全なデフォルト値 `0` または空配列で補完されます

### 3. Bot を起動

```bash
mise run start
```


## 開発用ツール

### Lint / Format

```bash
mise run lint
mise run format
```

### テスト

※ 試験的な実装です。

```bash
mise run test
```

## 移行スクリプト

V2 から V3 への DB 移行補助スクリプトを用意しています。

```bash
uv run python scripts/v2_to_v3_migration.py \
  --source-database-url "mysql://user:password@127.0.0.1:3306/asteroid_v2" \
  --target-database-url "mysql://user:password@127.0.0.1:3306/asteroid_v3"
```

引数を省略した場合は対話的に接続情報を入力できます。
