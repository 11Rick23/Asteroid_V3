# P2実装・検証記録

2026-11-01。P2「DB基盤・Repository・トランザクション」を実装し、隔離MySQLで検証した。
P3の実装へ進める状態。ただし新DBを既存Botへ接続・本番有効化する判断ではない。
既存BotのRepository wiring、Discordイベント経路、旧Alembic revision、本番DBは変更していない。

## 環境と隔離

| 対象 | 実測 |
|---|---|
| Python | 3.14.10 |
| SQLAlchemy / Alembic | 2.1.5 / 1.18.5 |
| aiomysql | 0.3.2 |
| pytest / pytest-asyncio | 9.1.1 / 1.4.0 |
| Ruff / Pyright | 0.15.22 / 1.1.414 |
| MySQL | 26.10.0、InnoDB、REPEATABLE READ |

既存 `.venv` と隔離環境の実インストール値を確認した。依存宣言との相違は残るが、
既存環境のsync・依存更新、pyproject.toml・uv.lockの変更は行っていない。
検証環境は `/private/tmp/asteroid-p2-venv`。mise経由の依存同期を避け、ここから直接実行した。
P1記録の環境値は過去の記録として残す。

MySQLは専用data directory `/private/tmp/asteroid-p2-mysql/data`、専用socket
`/private/tmp/asteroid-p2-mysql/mysql.sock`、DB名 `asteroid_p2_test`。
`--no-defaults --skip-networking --mysqlx=OFF` で起動し、本番設定やネットワーク接続を使用していない。
Docker daemonは未起動。sandbox内の初期化はSIGSEGVとなり、専用ディレクトリだけを対象に
sandbox外で初期化して成功した。検証用MySQLは再検証用に残している。

## 追加・変更ファイル

| 配置 | 内容 |
|---|---|
| `app/database/models/leveling_v2/` | 独立metadata、型、35テーブルのモデル（10ファイル） |
| `app/database/repositories/leveling_v2/` | 公開Repository・DTOと責務別内部処理（28ファイル） |
| `alembic-leveling-p2.ini` | 隔離検証専用Alembic設定 |
| `app/database/leveling_migrations/` | 接続先制限付きenvと新規revision |
| `tests/database/repositories/leveling_v2/` | fixtureと56件のMySQL統合テスト |
| `README.md` | 隔離検証の実行方法 |
| 既存6設計文書 | P2実装状況、実装上の補足、次フェーズとの境界 |
| `LEVELING_P2_REPORT.md` | この記録 |

P1のdomain実装・597件の契約テストは今回の新規実装数に含めない。
作業開始前から未追跡だったP1ファイル・設計文書は削除せず維持した。

## DBモデル一覧

すべて `leveling_` prefix。旧 `Base` に登録せず、独立 `LevelingBase` を使用する。

| モジュール | テーブル（prefix省略） |
|---|---|
| accounts | installation, accounts, channels, boosts |
| events | events, event_channels, event_periods, message_receipts |
| voice | voice_state, voice_segments, voice_grants, voice_pending, claims, claim_items |
| periods | periods, period_users, period_channel_users, period_channels |
| rankings | ranking_revisions, snapshot_user_inputs, snapshot_channel_inputs, ranking_rows |
| audit | corrections, correction_changes, correction_role_choices, operations, event_ownership_moves |
| outbox | monthly_qualifications, permanent_awards, role_desires, outbox, announcement_parts |
| migration | migration_runs, migration_items, import_items |

Discord IDはunsigned BIGINT、日時はUTC DATETIME(6)、数量はDECIMAL(65,0)。
VC合算率snapshotは個別予約上限を超え得るため整数文字列で保存する。
PK/UQ/FK/CHECK/索引をmigrationへ反映し、metadataとの差分なしを実MySQLで確認した。
CHECKの全組合せを網羅したという意味ではなく、DECIMAL境界・FK・prepared状態の代表的な拒否例も試験した。

## Repositoryと正本

| 公開クラス | 責務 |
|---|---|
| `LevelingRepository` | 恒常取得、メッセージ計上、受取、VC状態取得・CAS checkpoint・原子的精算、期間確定、承認済みsnapshot訂正 |
| `CatalogueRepository` | 運用Guild／開始日時固定、チャンネル最新名・論理削除 |
| `BoostRepository` | 予約作成・論理取消・時点照会、永久操作台帳による冪等性 |
| `RankingRepository` | OPENのwindow順位＋DBページング、確定revision固定照会 |
| `HistoryRepository` | user/channel/time/kind等のAND検索・stable cursor、受取・操作監査・月間資格DTO照会 |
| `MaintenanceRepository` | OPEN正本から派生集計の再構築と操作監査 |
| `OutboxRepository` | lease取得・完了・再試行待ち・UNKNOWN・期限切れ復旧、永久監査への結果転記 |
| `RetentionRepository` | 90日履歴のbatch回収、checksum確認後の公開済み作業表回収 |
| `MigrationAuditRepository` | 移行runと原本値の追記・照合。旧データ読取／移行処理は含まない |

計算はP1のgrowth、boost、VC付与、配分、期間、rankingを利用する。
OPENでは未割当入力・channel-user入力を正本とし、totalやchannel合計は派生値。
FINALIZEDではrevision付きsnapshot入力が正本。90日で削除されるイベントを残高再構築の根拠にしない。
訂正は新revisionを追加し、旧版・間接順位差分・永久監査を保持する。
過去月訂正では後続全月の資格を再計算し、永久報酬の獲得記録を保持する。
明示承認された維持／剥奪判断だけを希望状態・監査・同期ジョブへ同一txで反映する。

同一DBのwriterには同一 `MutationGate` を注入する。共有gate＋user排他、締め／訂正は排他gate。
DB側はperiod→account→state→segments→pending→集計→監査→outboxの順でロックする。
各操作を単一commitとし、deadlock／lock timeoutは同じ入力で最大3回。
commit応答喪失は別sessionでキー照会し、結果が確認できない場合は `CommitUnknown` で停止する。

## Alembic

- 新revision: `p2_20261101_01`。
- 新version table: `alembic_version_leveling_p2`。
- 旧head: `6b2956ddba0f`（変更なし）。
- 旧起動時head検査への影響を避け、P2は独立lineageとした。
- 同じ隔離DBで旧schemaと同居させ、新schemaのupgrade→downgrade→再upgradeを確認。
  その前後で旧表DDL・テスト用旧データ・旧version tableが不変であることも確認した。
- 本番用revisionへの統合・切替、実データ移行は後続フェーズ。旧データのコピーは実施していない。

## 最終検証

| 対象 | 結果 |
|---|---|
| P2 MySQL統合テスト | **56件成功**（全体実行に含む。skipなし） |
| P1契約テスト | **597件成功**（個別実行と全体実行） |
| 既存テスト | **315件成功** |
| 全体pytest | **968件成功、14.12秒** |
| 全体Ruff | 成功 |
| P2追加Pythonのformat check | 61ファイル成功 |
| 全体Pyright | 0 errors / 0 warnings |

```bash
ASTEROID_P2_MYSQL_TEST=1 /private/tmp/asteroid-p2-venv/bin/python -m pytest -q --tb=short
/private/tmp/asteroid-p2-venv/bin/ruff check .
/private/tmp/asteroid-p2-venv/bin/pyright --pythonpath /private/tmp/asteroid-p2-venv/bin/python
```

全体ログ: `/private/tmp/asteroid-p2-final-all.log`。
P1個別ログ: `/private/tmp/asteroid-p2-p1.log`。
統合fixtureは専用DB確認後に新schemaを再作成し、実Alembic upgradeを実行する。
`create_all`やSQLiteの成功をmigration／MySQL成功として代用していない。

| 検証する契約 | 主なテストファイル |
|---|---|
| D01/D02 初回作成・同一message・text/action重複 | test_message_transactions, test_message_retention |
| D03 途中例外と再実行 | test_write_failures（恒常、期間更新途中、event、receipt）、test_message_transactions |
| D04/D05 両ロック順・確定日拒否・週月受理 | test_closing_boundaries, test_period_closing |
| D06/D07 受取競合・月末原子性・再実行 | test_claim_transactions, test_closing_boundaries, test_period_closing |
| D08/D09 実deadlock・有限再試行・commit不明 | test_transaction_recovery, test_voice_settlement |
| D10〜D12 訂正版・stale拒否・後続資格・明示剥奪 | test_revisions, test_monthly_qualifications |
| D13/D15 90日保持・永久記録・回収・名前保持 | test_retention, test_message_retention, test_catalogue_and_boosts, test_outbox |
| D14 検索・同時刻ページング・cache修復 | test_history_and_repair |
| VC CAS・端数・固定乱数・二重付与・遅延月受取 | test_voice_checkpoints, test_voice_settlement |
| 制約・数値境界・migration・新旧同居 | test_schema_contract, test_migration_coexistence |
| Outbox lease・UNKNOWN・永久監査、移行監査 | test_outbox, test_migration_audit |

これはP2のDB境界の検証。D10のDiscord再認可、D14の表示権限などは後続UIの検証対象であり、
D01〜D15の全フェーズ横断項目がすべて完了したという意味ではない。

## 発見した設計上・実装上の問題

1. 複合FK名を先頭列だけで生成すると訂正の旧／新版参照が衝突するため、全FK列を命名に含めた。
2. 空の月末受取でも別月への操作キー流用を拒否するため、claimsへ `month_period_id` を追加。
3. prepared seq/randomのCHECKはNULL三値論理を考慮し、両方非NULLを明示した。
4. 旧migrationへ追加すると起動時head検査に影響するため、隔離lineageへ分離した。
5. downgradeでFKを支える索引を先にDROPするとMySQL 1553になるため、新しい未公開revisionは
   テーブルDROP時の索引削除に統一した。既存revisionは編集していない。
6. MySQLが数値defaultを引用符付きで反映する差を、有限数値として比較するcallbackで吸収した。
   異なる数値defaultは差分として検出する。
7. REPEATABLE READでロック待機後に古いsnapshotを使わないよう、再実行判定にcurrent readを使用。
8. 完了Outboxを削除する前に永久監査へ結果を転記する。転記先のないジョブは安全側で保持する。

## 未検証・後続フェーズへの引継ぎ

- 実Discordイベント、再接続時のVC照合・drain、実ロール同期・発表送信、権限・UIは未接続／未検証。
- 訂正APIは承認済みsnapshot入力を保存する基盤。管理操作の入力生成、再認可・プレビューはP4/P5。
- account移行・旧値importの実行、発表partの送信状態機械、本番切替は今回行っていない。
- 本番と異なるMySQL／依存宣言バージョンでの互換試験、実データ規模の負荷・長時間耐久試験は未実施。
- 単一Botプロセス＋共通gateが前提。複数Botによる同時計測を保証しない。
- 既知の未精算VC区間があれば締めを拒否する。P3/P4側でdrain後に最終締めを呼ぶ必要がある。
- 未確定commitは自動で新しい命令へ置換しない。呼出し側で同一キーの確認を継続する。
- 検証用MySQL・venvは `/private/tmp` に残す。再起動後は専用環境の再作成が必要になり得る。

P2基盤としての完了判定は可。P3以降への実装着手は可能だが、この変更だけで本番運用へ切り替えない。

## コミット前の再検証（2026-11-06）

P1とP2は実装の依存方向が一方向のため、独立コミットに分離した。
P1は純粋計算9モジュール・契約テスト5ファイルを対象とし、P2はDB基盤・統合テスト・READMEを対象とする。
未追跡の調査・設計文書はP1/P2両方の更新を含むため、履歴を推測して分割せず、最終版をP2へ含める。
今後の各開発フェーズの完了条件（実装・検証成功・コミット）はIMPLEMENTATION_PLAN §2に明記した。

過去の一時ログは消失し、隔離venvにはpytest等がなく、専用MySQLも停止していた。
初回再検証はDB不要の912件が成功し、MySQL56件は接続拒否で失敗した。
元の一時data directoryを保持し、新しい `/private/tmp/asteroid-p2-mysql/commit-data` を初期化した。
sandbox内のMySQL起動はSIGSEGVとなったため、sandbox外で起動した。
`--no-defaults --skip-networking --mysqlx=OFF`、従来の専用socket・DB名を使用し、本番DBには接続していない。

依存同期による変更を避けて既存 `.venv` から再実行した。
Python 3.14.10、SQLAlchemy 2.1.5、Alembic 1.18.5、aiomysql 0.3.2、pytest 9.1.1、
pytest-asyncio 1.4.0、Ruff 0.15.22、Pyright 1.1.414、MySQL 26.10.0を確認した。

| 再検証 | 結果 |
|---|---|
| P1契約テスト個別実行 | 597件成功 |
| 全体pytest（P2 MySQL統合56件を含む） | 968件成功、skipなし、14.85秒 |
| 全体Ruff check | 成功 |
| P1/P2追加Pythonのformat check | 75ファイル成功 |
| 全体Pyright | 0 errors / 0 warnings |
| コミット対象検査 | 機密情報・不要ファイルの混入なし、差分の空白エラーなし |

```bash
ASTEROID_P2_MYSQL_TEST=1 .venv/bin/python -m pytest -q --tb=short --maxfail=1
.venv/bin/ruff check .
.venv/bin/pyright --pythonpath .venv/bin/python
```

全体pytestログは `/private/tmp/asteroid-commit-pytest.log`（Git対象外）。
P3実装・pushは実施していない。前節の本番互換・実Discord・負荷試験等は引き続き後続フェーズの対象。
