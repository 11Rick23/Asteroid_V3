# レベリング改修 テスト計画

2026-11-01 / P1 597件・P2 MySQL 56件・既存315件、全体968件成功。入力処理・Discord・実データ移行の試験は後続フェーズ。[P2の検証範囲と未検証項目](LEVELING_P2_REPORT.md)を参照。

## 1. 方針とテスト環境

[要件ID](LEVELING_REQUIREMENTS.md)に基づき、Given-When-Then・日本語docstring・機能／非機能要件コメントで実装する。配置は `tests/README.md` に従う。時刻・乱数・Discord APIを注入可能にし、業務判断をmockで置き換えない。SQLiteは純粋repository入出力の補助、本番同等MySQL/InnoDBでロック・数値・migrationを必ず検証する。

本番DBへテストしない。実装時に宣言Python・SQLAlchemy・Discord.pyと一致した隔離環境を用意し、現行環境のバージョン差を解消してから結果を記録する。Discord payloadの構造検証に加え、実装リリース前に専用検証Guildで表示・権限・再参加を確認する。

## 2. 単体・契約テスト

| ケース | 要件 | 入力／操作 | 必須結果 |
|---|---|---|---|
| U01 成長境界 | R01 | grade0/49、必要XP前後、prestige境界268375、複数昇格、減算0下限 | 現行純粋関数との同値性、種類別合計と進行度整合 |
| U02 通常入力 | R02,R03,R19 | default/system、Bot/Webhook、人、DM/他Guild、除外ID、ロール有無 | 拒否時DB・通知・cache副作用なし。アクションだけ独立許可 |
| U03 cooldown | R02 | 期限直前・ちょうど・直後、同時2投稿、DB失敗 | 現行境界、成功した1件だけ加算、失敗でcooldownを消費しない |
| U04 予約 | R13 | 同一role複数、別role重複、start/end一致時刻、無期限、再起動 | 加算率の総和、開始含む終了含まない、power不変 |
| U05 数値 | R01,R13/DR03 | 負値、小数、NaN/Infinity、DB精度最大と超過、管理者add/set | 不正拒否、部分commitなし、超過の暗黙clampなし |
| U06 期間 | R04,R06 | JST/UTC変換、月曜、閏日、年越し、同時日週月境界 | 半開区間、重複境界は1精算、前期間へ帰属 |
| U07 順位 | R04,R07 | 100,100,90、0、退出者、同率10位多数 | 1,1,3、0除外、繰上げなし、TOP10全対象 |
| U08 VC資格 | R03,R14 | 1/2/3人、Bot、各mute/deaf/AFK、除外role、除外channel、Stage | 現行条件、除外roleは人数のみ参加、影響する全員の資格更新 |
| U09 VC端数 | R14 | 59秒+1秒、退出再参加、20秒境界、0量境界、同時日週月 | 60秒1抽選、残余保存、境界比例・floor、同じ残余の再利用なし |
| U10 VC倍率 | R13,R14 | R20,a0.3、30秒0%+30秒100% | 基本6、ボーナス3、power6。checkpoint頻度で結果が変わらない |
| U11 VC配分 | R14 | A/B各30秒、power3、ID逆順、3チャンネル不均等 | 最大剰余、同率ID昇順、割当合計=実power |
| U12 上限 | R15 | shardのみ満杯、powerのみ満杯、両方、残1、旧残高>300 | 満杯側だけ停止、独立clip、旧値維持、powerだけ受取可能 |
| U13 通知 | R15 | 先着・同時到達、API失敗、送信直前停止、再受取 | 1サイクル1試行、50%なし、失敗再送なし、適切な再arm |
| U14 カード | R08 | 成長あり月間行なし、各power欠損 | ランクカード表示・欠損0、内部全件読込みなし |
| U15 ロール | R10,R12 | 同率1/10、退出、3連続、空月、移行前月 | 1位両付与、非在籍APIなし、空月連続切断、移行月から開始 |

## 3. Repository・競合テスト

別々のMySQL sessionをbarrierで指定位置まで進め、sleepの偶然に頼らずcommit順を制御する。

| ケース | 操作 | 検証する不変条件 |
|---|---|---|
| D01 初回同時加算 | account/periodのない同一ユーザーへ2イベント | 行作成競合でも両加算保持、UQ整合 |
| D02 同一message | 同一IDを2session、text/actionルート違いも投入 | receipt・イベント・成長・powerは各1回、outbox重複なし |
| D03 途中失敗 | receipt後、成長後、3期間更新途中、outbox前に例外 | 全rollback、同じキーの再試行で正しく1回 |
| D04 締め対加算 | writer先／締め先を別々に再現 | 前者はsnapshotへ、後者は確定期間だけ拒否。他期間は受理 |
| D05 独立期間 | 日FINALIZED・週月OPENへ過去イベント | 日不変、週月増加、event_periodsに受理可否、warning記録 |
| D06 受取競合 | 手動×手動、手動×月末、月末×付与 | 恒常1回、power再加算0、新月pending不消失 |
| D07 月末再実行 | 事前受取batch途中停止、最終commit前後停止 | 全員受取に収束、結果1版、月間job1組、翌月加算保持 |
| D08 deadlock | 競合rollback・再試行・上限回数超過 | operation_key・乱数固定、部分commitなし、有限再試行 |
| D09 commit不明 | commit済みだが応答を喪失、未commitで切断も実施 | キー照会で区別、VC seqの再抽選・再加算なし |
| D10 訂正競合 | 同じrevisionのプレビュー2件、一般加算の介入 | 先着だけ承認可、古いプレビュー拒否、再認可 |
| D11 訂正集計 | channel user減算／全体未割当減算／0化 | scope合計整合、負値拒否、影響者順位すべて履歴保存 |
| D12 後続月 | 過去TOP1取消で複数3連続窓に影響 | 後続全月再判定、別窓の資格は維持、剥奪は個別承認のみ |
| D13 保持 | 記録89日23:59、90日境界、古いoccurredの新規記録 | expires基準、snapshot/監査/pending不変、batch削除再開可 |
| D14 検索 | user/channel/time/kind全組合せ・0件・多数 | AND、権限範囲、stable pagination、本文保存なし |
| D15 復元 | 最新name更新・削除・90日経過 | 過去値・順位・内訳再現、最新／最後の名前表示 |

DR01は確定。処理後90日直前は重複0加算、境界以降は通常遅延受付を維持する。receipt未削除／削除済み両方で新generationを扱い、OPEN期間への再加算が可能な保証期間外動作を検証する。期限内再配送で保持期限を延長しない。

## 4. VC障害・復旧マトリクス

| 注入点 | 期待 |
|---|---|
| 初回照合中のjoin/leave/move/mute/role変更 | 最新ユーザー状態へ集約し、旧新channel全員を再判定。初期snapshotで上書きしない |
| 初回照合・DB保存の連続失敗 | 停止維持、5→10→20→40→60、config反映、復旧成功まで0秒 |
| checkpoint直前の強制終了 | 最後の成功値のみ復元、停止時間を足さず保存済み端数のみ保持 |
| Gateway切断／resume中の移動 | 不明区間除外、全VC再照合後に計測、重複付与なし |
| DB障害とGateway障害の重複 | 片方だけ回復しても再開しない |
| 期間境界を跨ぐ障害 | 旧保存区間を旧期へ精算、未知時間0、締め済み期間不変 |
| 同じユーザーの連続イベントと定期照合 | seq/versionで古い状態を拒否、負の時間や二重計測なし |
| OS時刻前進・後退 | 単調差分を維持、暦境界異常は再照合し推測加算しない |
| 永続checkpoint破損・不整合 | 最後の正常値を保持、対象計測停止、自動修復不能時のみ管理者対応通知 |
| エラー報告先も送信失敗 | ログfallback、再帰ループなし、障害／復旧通知は遷移単位 |

## 5. UI・外部副作用

- `/power top`初期月総合、全期間／指標／scope、削除済みchannel検索、過去日付、全5ページ操作、0件・端ページ・不正ページ・訂正版更新を確認。
- 公開Viewの他ユーザー操作、DM、他GuildをEphemeral拒否し副作用0。管理者履歴／訂正／boost／addはslashとcallback双方で権限再確認。権限剥奪後の承認も拒否。
- 履歴はEphemeralでCSVなし。公開ランキングからイベント詳細が漏れない。
- 月間発表は4種、同率10位が11人／100人／全員の場合、長いメンション・内訳、40component境界と文字数境界を生成してpayload検査。収まれば1件、超過時のみ分割、全員が1回掲載、ページボタン0。
- DB確定後にDiscord 429/5xx/403/timeoutを注入。順位・恒常は不変、retry/needs_attentionを区別。発表成功後DB記録前クラッシュはmarker照合、照合不能はunknown。
- 古い月のrole jobを最新月jobの後に実行しても最新希望へ収束。同期中の訂正・受取・退出、API一部成功にも対応。
- TOP1/TOP10保存済み行が残る再参加で復元されない。特別ロールは復元する。移行直後は旧月間ロールを消さず次回集計で更新。
- 昇格通知失敗でもrole同期は継続。上限通知だけ再試行しない。

## 6. 移行・回帰・性能

移行fixtureは成長のみ、月間のみ、actionのみ、pendingのみ、退出者、0、型最大、旧上限超過、不整合、複数boost、月境界を含める。移行文書の全検証式をuser別・全体で比較。各batch途中停止と再開、同じ移行2回、異なる原本での再実行拒否、旧未受取の手動／月末受取を確認する。

復旧試験は切替前と新書込み後を分ける。新書込み後の旧バックアップ単純復元を手順が禁止すること、forward repairで新XPを保存できることを確認する。旧V2スクリプトと新移行を誤用できない運用手順を検証する。

性能は想定ユーザー数N・channel数C・同率件数T・1日イベントE・保存年数Yを実運用見積りから設定し、少なくとも想定量と10倍量で測定。深いページ、履歴複合検索、無期限snapshot、月末最終tx、90日削除をEXPLAINと時間・lock wait・メモリで評価。アプリ取得行数はページ＋定数程度、月間発表だけ全対象をstream/batch。締めがcheckpointを恒常的に遅延させる場合はリリース不可。数値SLOは実データ未確認のため実装開始時に測定条件と一緒に定める。

既存回帰はaccount_migration、roles、persistent_panels、config、guild_scope、command registration、error_reporting、V2移行手順の互換性も対象。DR04の既存機能互換契約を全経路で検証する。DR06/DR07は決定済み。恒常付与と安全な手動集計の期待値を固定し、接続部分はP3〜P5で検証する。

## 7. 実装フェーズの実行ゲート

1. 純粋計算・対象repositoryのpytestを先行。
2. MySQLでD01〜D15、境界・障害・移行試験。
3. 権限・共有基盤を含む広いpytest、Ruff read-only check、Pyright。
4. 承認された実装段階で `mise run test` / `mise run typecheck` / `mise run check`。checkのlintは--fix、sync依存もあるため差分を検査する。
5. 専用GuildでUI・API・再参加、コピーDBでdry-run・復元、負荷ゲート通過後だけ切替候補。

今回はP1の純粋計算と既存テストを検証する。後続フェーズの未実行試験を成功扱いしない。

## 8. 要件網羅の追跡表

| 要件 | 主設計 | 証明するテスト |
|---|---|---|
| R01 | Architecture §2、DB §1/6 | U01/U05、移行全件一致 |
| R02 | Architecture §2 | U02/U03 |
| R03 | Architecture §2/3 | U02/U08 |
| R04 | DB §2.3 | U07、UI全ページ |
| R05 | DB §2.1/2.3 | U11/D11/D15 |
| R06 | Architecture §5/9 | U06/D04/D05、境界復旧 |
| R07 | DB §2.3/4/5 | D13/D15、前期キー照合 |
| R08 | Architecture §7 | U14、UI全5操作・認可 |
| R09 | Architecture §6/7 | 4種同率発表payload・分割・API障害 |
| R10 | Architecture §6/9 | U15/D12、古いrole job |
| R11 | Architecture §6、DB §4 | D10/D11/D12、承認時権限 |
| R12 | Migration §3/4 | 再参加復元、初回月末role更新 |
| R13 | Architecture §2/3.1 | U04/U05/U10 |
| R14 | Architecture §3/9 | U08/U09/U10/U11、60秒境界一致 |
| R15 | Architecture §4/9 | U12/U13/D06/D07、受取前checkpoint |
| R16 | Architecture §3.2 | checkpoint／切断／DB障害の全マトリクス |
| R17 | Architecture §3.2/8 | 初期照合集約、backoff、障害報告先故障 |
| R18 | DB §2.1/5/6 | D13/D14、Ephemeral・CSVなし |
| R19 | Architecture §2、DB §3 | U02/D02/D03/D09 |
| R20 | Migration §3〜6 | 全移行検証式、再実行、rollback段階別 |

## 9. 追加レビューに対する受入試験

以下は設計上必要な試験の追加であり、実装試験済みという意味ではない。

| ID | レビュー対象 | 手順と合格条件 |
|---|---|---|
| V01 恒常と期間 | 全3期間FINALIZED、text/action/保存VC端数を入力。power全0と受理拒否履歴は確定期待。恒常は通常付与、VCは独立上限適用後に旧月catch-up、全不受理ではmeter消費0を試験。シャード受付判定がperiod状態に暗黙連動しない |
| V02 ロック階層 | checkpointが60秒付与を発生させる手動受取と月末最終txをbarrierで同時進行。gate共有→排他upgradeなし、全periodがaccountより前、account全件がstate全件より前。coordinator/userをDB保持中に要求しない。待機グラフに循環なし |
| V03 ロック全組合せ | 手動／月末事前／VC付与／日週月締め／訂正／account移行の各組合せと3者競合。排他待ち時に既存共有が完了し、次の共有も解放後進行。DB engineのdeadlock注入は全tx rollback＋同一キー再試行 |
| V04 正本切替 | OPEN cacheを意図的に壊し入力正本から復元。snapshot公開前停止ならOPEN読取り、公開後回収途中ならsnapshot読取り。作業表全削除後も過去順位・内訳・訂正previewを再現 |
| V05 保存量 | U/C/E/B/Kを日週月別に生成し、DB §8の行数式と一致確認。0行省略、4指標内訳重複なし。実MySQLのDATA_LENGTH/INDEX_LENGTHで仮定を置換し、訂正多数・backup込みの容量評価 |
| V06 checkpoint CAS | 同じexpected_versionを2回送信、checkpointと境界を競合、各SQL直後で切断。片方だけ成功し、segments消費・seq・pending・periodが全て一緒に進む／全て戻る |
| V07 復旧seq | prepared_random保存直後、grant commit直前／直後、90日grant掃除後に再起動。seqが巻戻らず、残余を新epochキーで再計上しない。乱数固定、古いepoch命令拒否、保存端数は保持 |
| V08 月間POST不明 | 成功応答喪失、5xx、timeout、SENDING lease切れ、DB記録失敗でUNKNOWN。自動POST回数は増えない。一致1件／複数／0件／履歴権限不足を再現し、0件でも自動再送しない |
| V09 分割発表 | part1 SENT、part2 UNKNOWNで停止・再起動。part1再送0、part3保留、hash・marker不変。管理者関連付け／明示再送のactor・理由・attemptを監査 |
| V10 管理機能 | add/remove/setの既定当月、指定日週、確定期訂正。0化でchannel入力が残らない、比例縮小previewを確認。pending setはpower集計を変えない。既存コマンド・権限・オプションが残る |
| V11 MEE6 | 同digest再取込み0、別digestの既対象者は差分承認必須。再開してもitem二重適用なし。恒常だけ変化し3期間power0。sync_role/prestige_announce選択を維持 |
| V12 account移行 | source/target両方にOPEN/FINALIZED/pending/端数。OPEN合計保存・source0、過去snapshot不変、端数混合なし、所有者監査追跡。途中Discord失敗は進行状態から復旧し、後続更新を補償で上書きしない |
| V13 移行停止 | 旧成長不一致・範囲超過・未確認boostを投入。切替しない、元行不変。MEE6基準未確認の再取込みを無断で新規扱いしない |
| V14 旧force集計 | DR07の安全なpreview／未完了締め再実行を検証。期限前確定・強制発表・強制削除なし。確定済み結果は訂正経路のみ。P5で旧オプションから危険な副作用へ到達しないことを確認 |

レビュー6項目の追跡: 1→V01、2→V02/V03、3→V04、4→V05、5→V06/V07、6→V08/V09。DR01〜05の確定対応は既存D13とV10〜V13で確認する。

## 10. P1実装・検証記録（2026-11-01）

P1の新規597件、既存315件、合計912件成功。以下の対応は純粋計算の範囲であり、DB commit、Discord操作、コマンド置換の成功を意味しない。

| 対応 | テストファイル | 検証範囲 |
|---|---|---|
| U01/U05 | `tests/features/leveling/test_growth_contract.py` | 全50グレード×2 prestige×5加減算の現行互換、49→prestige、大量加減算、65桁最大値・超過、不整合拒否 |
| U04/U05/U06 | `tests/features/leveling/test_period_boost_contract.py` | JST/UTC、閏日・年越し・半開期間、重複予約・取消、率加算、数値検証、Decimal精度非依存 |
| U08/U09 | `tests/features/leveling/test_voice_time_contract.py` | 人数・除外・mute/deaf/AFK・Stage、端数保持、停止空白除外、同時境界、60秒一致、複数日・残余消費 |
| U05/U09/U10/U11/U12/V01 | `tests/features/leveling/test_voice_award_contract.py` | 調整係数、時間比例、最終floor、最大剰余、独立上限、旧超過残高、全／一部期間不受理とmeter |
| U07/U15 | `tests/features/leveling/test_ranking_contract.py` | RANK同率、0除外、同率10位全員、隣接3ヶ月・移行月・空月・年越し・訂正後の別窓 |

実行コマンド:

- `uv run --no-sync pytest tests/features/leveling/test_*contract.py -q`: 597 passed。
- `uv run --no-sync pytest -q`: 912 passed。
- `uv run --no-sync ruff check .`: 成功。
- `uv run --no-sync pyright`: 0 errors / 0 warnings。
- `uv run --no-sync ruff format --check`（新規9モジュールと5テストファイル）: 全14ファイル整形済み。

環境差異: 実行Python 3.14.6（宣言>=3.14.8）、SQLAlchemy 2.0.51（>=2.1.5）、Ruff 0.15.20（>=0.15.22）、Pyright 1.1.411（>=1.1.414）。pytest 9.1.1、pytest-asyncio 1.4.0、Discord.py 2.7.1を使用。依存更新は行っていない。`mise run test/typecheck/check` はsync依存のため使用せず、既存venvのまま `--no-sync` で検証した。宣言環境に一致した検証は未実施で、P2のSQLAlchemy/MySQL検証に先立ち環境を揃える必要がある。

U02/U03/U13/U14とU15のロールAPI、V01のreceipt・catch-up受取、V14のコマンド接続は後続フェーズ。P1の残余を再投入しない純粋状態遷移は試験済みだが、クラッシュや競合時の二重計上防止はP2/P3のCAS・トランザクション試験で保証する。
