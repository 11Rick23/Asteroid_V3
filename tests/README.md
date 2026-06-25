# Asteroid_V3 Test Guideline

## 目的

Asteroid_V3 のテストは、カバレッジ率を上げるためではなく、重要な振る舞いを壊さないための安全網として整備する。

重視すること:

- 何を検証しているかが読んで分かる
- 実装詳細ではなく、外から見た振る舞いを検証する
- 新機能追加時に迷わずテストを追加できる
- Discord API、DB、時刻、乱数などの不安定要素を適切に隔離する
- 拒否、権限不足、対象外 guild など、壊れると危険な経路を確実に守る

## 基本方針

テストは `unit` / `integration` / `e2e` のような層別ディレクトリではなく、「何をテストしたいか」に応じて分割する。
実装コードの責務は配置の手がかりとして使うが、最終的にはコードの意図から読み取れる機能要件や非機能要件が分かるファイルに置く。

テストでは、次のどちらを確認しているのかを明確にする。

- 機能要件: ユーザー操作、コマンド、UI、サービス、repository、設定などが期待される振る舞いを満たしていること。
- 非機能要件: 権限、guild scope、副作用の抑止、冪等性、ログ、エラー処理、安定性など、機能そのものではないが守るべき性質を満たしていること。

コードを読んでも非機能要件として守るべき性質が見当たらない場合は、無理に非機能要件のテストを作らない。機能要件を中心に、壊れると困る振る舞いを代表ケースで確認する。

新機能は基本的に次の対応で追加する。

```text
app/features/<feature>/
tests/features/<feature>/
```

テスト分類を先に増やすのではなく、検証したい契約に合わせて必要なテストファイルだけを作る。空の標準ファイルや将来用の分類は作らない。

`tests_archive/` は旧テストの退避場所であり、新しいテスト方針の参照元にはしない。

## 推奨ディレクトリ構成

```text
tests/
  README.md
  conftest.py
  support/
    discord_fakes.py
    config_factories.py
    db_helpers.py
    assertions.py

  common/
    test_guild_scope.py
    test_command_groups.py
    test_permissions.py
    test_persistent_panels.py

  core/
    test_config.py
    test_extensions.py
    test_system_commands.py

  database/
    test_migrations_check.py
    repositories/
      test_<repository>_repository.py

  features/
    <feature>/
      test_service.py
      test_commands.py
      test_views.py
      test_runtime.py
      test_domain.py
```

上記は候補であり、すべての feature に全ファイルを作る必要はない。

## 配置ルール

- feature 固有のテストは `tests/features/<feature>/` に置く。
- 複数 feature にまたがる共通契約は `tests/common/` に置く。
- Bot 起動、設定、extension loading、system command は `tests/core/` に置く。
- repository と migration は `tests/database/` に置く。
- fake、factory、共通 assertion は `tests/support/` に置く。
- `conftest.py` は薄く保つ。
- feature 固有 fixture は必要なら `tests/features/<feature>/conftest.py` に閉じる。
- テストファイル名は「検証したい対象」に合わせる。分類名に合わせるためだけのファイルは作らない。
- `test_service.py`、`test_commands.py`、`test_views.py` などは実装ファイル名ではなく、テストしたい契約の種類を表す名前として使う。
- 1 つの production file に複数の契約が含まれる場合は、テストしたい内容ごとにファイルを分ける。
- 1 つの契約を守るために複数の production file を通す必要がある場合は、無理に production file ごとへ分割しない。

## テストファイル分割の判断

テストファイルは、先に「どの機能要件または非機能要件を壊したくないか」を決めてから選ぶ。

- 純粋な計算、ポリシー、値の正規化を検証したい場合は `test_domain.py` に置く。
- feature の主要な状態判断、repository や Discord 操作の手前までの調整を検証したい場合は `test_service.py` に置く。
- slash command の公開 API、引数名、権限、応答、監査ログを検証したい場合は `test_commands.py` に置く。
- Button、Select、Modal、View callback の認可と副作用を検証したい場合は `test_views.py` に置く。
- listener、scheduled task、startup hook、cog lifecycle を検証したい場合は `test_runtime.py` に置く。
- 設定読み込み、feature flag、extension map、system command を検証したい場合は `tests/core/` に置く。
- DB 永続化、repository の入出力、migration revision を検証したい場合は `tests/database/` に置く。
- feature をまたぐ guild scope、command group、persistent panel、error reporting などの共通契約を検証したい場合は `tests/common/` に置く。

分割に迷う場合は、失敗したときに「どの契約が壊れたのか」が最も分かりやすい場所を選ぶ。

## テストの記述スタイル

テスト本文は Given-When-Then パターンで記述する。

- Given-When-Then の前に、テストしている要件を `# 機能要件：...` または `# 非機能要件：...` のコメントで明示する。
- 1 つのテストで機能要件と非機能要件の両方を守る場合は、両方のコメントを書く。
- 要件コメントは、実装手順ではなく外から見た契約を書く。
- `# Given`: 何が与えられるのか。前提、入力、fake、fixture の準備
- `# When`: 何が行われるのか。対象操作の実行
- `# Then`: 何が期待されるのか。結果、副作用、ログ、永続化状態の検証

テスト関数名は短い英語にする。詳細な仕様説明は関数の docstring に日本語で書く。

```python
async def test_rejects_outside_guild(fake_interaction, service):
    """対象外 guild の UI 操作では拒否応答のみを返し、ロール更新は行わない。"""
    # 機能要件：対象外 guild の UI 操作は拒否応答を返す。
    # 非機能要件：拒否された操作ではロール更新などの副作用を発生させない。
    # Given
    fake_interaction.guild_id = 999

    # When
    await service.handle(fake_interaction)

    # Then
    assert fake_interaction.response.ephemeral is True
    assert service.updated_roles == []
```

良い例:

```text
test_rejects_outside_guild
test_requires_admin
test_returns_none
test_skips_side_effects
```

避ける例:

```text
test_outside_guild_button_does_not_update_roles_and_sends_ephemeral_denial
test_service
test_success
```

## テストケース設計

テストケースは思いつきで増やさず、一般的なテスト技法を使って代表ケースを選ぶ。
最初にコードの意図を読み取り、検証対象が機能要件なのか、非機能要件なのか、または両方なのかを決める。

### 同値分割

同じ扱いになる入力や状態をグループに分け、各グループから代表値を選ぶ。

- 正常系 / 異常系
- 許可される guild / 対象外 guild / DM
- 管理者 / 権限不足ユーザー
- 登録済み / 未登録
- 有効な設定 / 未知キー / 欠落値

同じ同値クラスの値を大量に並べるのではなく、仕様上の違いが出る代表値を選ぶ。

### 境界値分析

数値、日時、件数、しきい値、文字数、クールダウンなどは境界の前後を確認する。

- 最小値、最大値
- 境界ちょうど
- 境界の 1 つ手前 / 1 つ後
- 空、1 件、複数件
- クールダウン直前 / ちょうど期限切れ / 期限切れ後

境界が仕様として重要な場合は、正常に通る値だけでなく拒否される隣接値も確認する。

### デシジョンテーブル

複数条件の組み合わせで結果が変わる仕様は、条件と期待結果を表にしてからテストする。

例:

```text
operating guild | has permission | target valid | expected
yes             | yes            | yes          | executes
yes             | no             | yes          | denies
no              | yes            | yes          | denies without side effects
yes             | yes            | no           | validation error
```

すべての組み合わせを機械的に網羅するのではなく、結果が変わる条件と危険な拒否経路を優先する。

### 状態遷移

登録、更新、削除、復元、offline、panel refresh など状態を持つ機能は、遷移前後の状態と副作用を確認する。

- 未登録から登録済みになる
- 登録済みを更新する
- 削除後に見つからない
- offline 後に更新しない
- 同じイベントを再処理しても重複しない

### エラー推測

過去に壊れた箇所、Discord API や DB との境界、権限不足、対象外 guild、未知の設定値などは明示的にテストする。

特に拒否系では、拒否応答だけでなく、DB 更新、ロール変更、メッセージ送信、cache 更新などの副作用が起きないことを確認する。

## 新機能追加時のテスト判断

新しい feature を追加するときは、必要な境界だけを追加する。

### Service

対象: feature の主要な振る舞い、状態変更、Discord 操作の手前までの判断、repository との協調。

配置:

```text
tests/features/<feature>/test_service.py
```

作る条件:

- feature の中心的な仕様が service にある。
- command / view / runtime から呼ばれる処理をまとめて検証したい。
- Discord API を fake に置き換えて振る舞いを確認できる。

作らない条件:

- feature が薄い command wrapper だけで、独立した service 契約がない。

### Commands

対象: slash command、command group、公開引数、権限、応答、監査ログ。

配置:

```text
tests/features/<feature>/test_commands.py
```

作る条件:

- slash command を追加または変更する。
- 管理者権限、公開引数名、日本語説明、ephemeral 応答、監査ログが仕様に含まれる。

作らない条件:

- feature に command がない。
- 共通 command 登録基盤だけの変更で、`tests/common/` の方が適切。

### Views

対象: Button、Select、Modal、UI callback の認可と副作用。

配置:

```text
tests/features/<feature>/test_views.py
```

作る条件:

- View / Button / Select / Modal を追加または変更する。
- callback が DB、ロール、チャンネル、メッセージ、cache を変更する。
- 対象外 guild、権限不足、DM で副作用が起きないことを確認する必要がある。

作らない条件:

- 表示専用で副作用がない。
- 共通 UI 基盤の契約だけを確認すれば足りる。

### Runtime

対象: listener、scheduled task、startup hook、cog lifecycle。

配置:

```text
tests/features/<feature>/test_runtime.py
```

作る条件:

- `on_message`、`on_member_update`、定期タスク、startup 初期化などを追加または変更する。
- 対象外 guild で DB 更新、send、cache 更新が起きないことを確認する必要がある。

作らない条件:

- feature に runtime hook がない。

### Domain

対象: 純粋な計算、ポリシー判断、値オブジェクト、条件分岐。

配置:

```text
tests/features/<feature>/test_domain.py
```

作る条件:

- Discord object、DB、時刻、乱数なしで検証できる判断がある。
- service や command から切り出すことでテストが読みやすくなる。

作らない条件:

- feature に純粋ロジックがない。
- service の振る舞いとして確認した方が仕様を理解しやすい。

### Repository / Config

repository と config は feature 配下ではなく、共有の責務に置く。

Repository:

```text
tests/database/repositories/test_<repository>_repository.py
```

作る条件:

- DB-backed state を追加または変更する。
- create / update / delete / list / missing row の契約がある。

Config / extension:

```text
tests/core/test_config.py
tests/core/test_extensions.py
```

作る条件:

- `AsteroidConfig`、`FeatureFlags`、`FEATURE_EXTENSION_MAP`、`config.example.yaml` に変更がある。

## 常駐パネルの扱い

常駐パネルの lifecycle は共通基盤で管理するため、新機能ごとに機械的に `test_panel.py` を作らない。

原則:

- `PersistentPanelManager`、offline 表示、refresh、unregister、latest message reuse は `tests/common/test_persistent_panels.py` で守る。
- feature 側は panel 専用テストではなく、panel に渡す render 内容や service の振る舞いを必要な境界で検証する。
- feature 独自の panel logic が大きく、service や view のテストでは仕様が読みにくい場合だけ `tests/features/<feature>/test_panel.py` を作る。

## Asteroid_V3 で特に守る契約

### Guild Scope

- slash command は運用対象 guild のみ許可する。
- DM と対象外 guild では拒否する。
- View / Button / Select / Modal も callback 内で拒否する。
- listener や scheduled task は対象外 guild で DB 更新、send、cache 更新をしない。
- 拒否テストでは「拒否されたこと」だけでなく「副作用が起きないこと」も確認する。

### Command / UI

- admin command は権限と runtime check を持つ。
- public group 配下の admin subcommand も runtime check を持つ。
- 公開引数名と説明は原則日本語にする。
- state-changing command は監査ログを残す。
- UI callback は slash command の check に依存せず、callback 側で認可する。

### Database

- repository の create / update / delete / list を repository 境界で確認する。
- repository は ORM model ではなく DTO を返す。
- missing row の扱いを明確にする。
- schema 変更時は Alembic migration と revision check を確認する。

### Fake / Mock

- fake Discord object は必要な属性だけを持つ小さいものにする。
- production の type guard や認可処理をテスト都合で緩めない。
- fake を Discord.py 型として扱う必要がある場合は test boundary で `typing.cast` を使う。
- mock は Discord API、時刻、乱数、外部 HTTP、重い依存などに限定する。
- 自前 service の内部呼び出し順を過剰に検証しない。

## 実行方針

開発中は対象を絞って実行する。

```bash
uv run pytest tests/features/<feature>
```

共通基盤、権限、guild scope、DB、command registration を触った場合は広めに実行する。

```bash
uv run pytest tests/common tests/core tests/database
```

最終確認は変更範囲に応じて行う。

```bash
mise run test
mise run typecheck
mise run check
```

`mise run lint` は `--fix` によりファイルを書き換えるため、意図したタイミングでのみ実行する。

## 判断基準

良いテストとは、次を満たすものとする。

- 壊れたら正しく失敗する
- 壊れていなければ余計に失敗しない
- 読めば仕様が分かる
- リファクタリングで壊れにくい
- 失敗時に原因を追いやすい
- 新機能追加時に同じ形で増やせる

このため、Asteroid_V3 のテスト構造は、理論上のテスト層よりも「開発者が新機能を追加するときの動線」を優先する。
