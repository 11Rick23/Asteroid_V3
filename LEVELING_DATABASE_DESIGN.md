# レベリング改修 論理DB設計

2026-11-01 / P2のDDL・Repository・隔離migrationを実装・検証済み。[要件](LEVELING_REQUIREMENTS.md)と[処理フロー](LEVELING_ARCHITECTURE.md)を参照。

## 1. 型・前提・不変条件

MySQL/InnoDB、SQLAlchemy async、Repositoryからdataclass DTO。単一GuildのDBとしてguild列を全表に増やさず、installation行に運用Guild IDを記録して起動時に一致確認。別Guildへ設定だけ変更して残高を流用させない。

Discord IDと内部連番はBIGINT UNSIGNED。時刻はUTC DATETIME(6)、境界生成だけJST。秒数は整数マイクロ秒BIGINT。残高・率はDECIMAL(65,0)、係数はDecimal（保存は正規化文字列）をDR03で確定した基本案とする。計算中は任意精度整数／Decimalを使いDB格納前に検証。浮動小数を永続数値の正本にしない。全残高>=0、gradeは0..49、期間start<end、予約endはNULLまたはstartより後。

不変条件:

- 通常メッセージは処理後90日間、一意キーにつき一度だけ確定する。無期限遅延受付は維持し、保証期間外の再加算は許容リスクとして明記する。VC・移行・管理操作はそれぞれ永続seq／台帳の契約を用いる。
- `total_power = text + voice + action`。総合を独立に増減しない。
- ユーザーの各テキスト／VC全体値 = チャンネル割当合計 + 未割当値。actionは未割当のみ。
- channel全体値 = 同channel内ユーザー値のSUM。同率順位は値だけで定義する。
- 恒常総量 = text_shard + voice_shard + bonus_shard = prestige*268375 + cumulative_grade_shard(grade) + shard。旧不一致はDR05で切替停止。
- 未受取powerカウンターを受取してもperiod残高は変化しない。
- FINALIZEDの通常集計は変更不可。訂正は別revision。イベントを削除しても結果・訂正は残る。

## 2. テーブル定義案

名前は実装時の新規テーブル候補。共通created_at/updated_atはUTC。下記PK/UQは必須。列挙状態はVARCHAR＋アプリ検証、利用DBが対応するCHECKも追加する。

### 2.1 運用・恒常・入力

| 表 | 主な列とキー | 制約／索引／保持 |
|---|---|---|
| leveling_installation | PK id=1, guild_id, cutover_at, ranking_started_at, active_schema_generation | 1Guild固定。無期限 |
| leveling_accounts | PK user_id, text_shard, voice_shard, bonus_shard, prestige, grade, shard, version | 数式整合検証。順位索引(prestige DESC,grade DESC,shard DESC,user_id)。無期限 |
| leveling_channels | PK channel_id, last_name, kind(text/voice), deleted_at NULL, last_seen_at | 過去集計から参照。物理削除しない。最新名更新、無期限 |
| leveling_events | PK event_id, UQ operation_key, user_id, kind, occurred_at, interval_start/end NULL, recorded_at, expires_at, raw_xp, base_shard, bonus_shard, power, source_message_id NULL, source_bot_id NULL, status, calculation_version, calculation_inputs JSON | 原因と実付与量、clip前後、倍率区間を保存。索引(user_id,occurred_at,event_id),(kind,occurred_at,event_id),(occurred_at,event_id),(expires_at,event_id)。90日 |
| leveling_event_channels | PK(event_id,channel_id), duration_us, allocated_power | FK event CASCADEのみ許可。索引(channel_id,event_id)。eventと同寿命 |
| leveling_event_periods | PK(event_id,period_id), accepted, reason, accepted_power | 独立した期間の受理結果。FK event CASCADE、period削除禁止。eventと同寿命 |
| leveling_message_receipts | PK message_id, route(text/action), generation, operation_key, processed_at, expires_at, outcome | 同じメッセージをルート違いで再加算しない。索引(expires_at,message_id)。処理確定から90日 |
| leveling_boosts | PK boost_id, role_id, name, rate_percent, starts_at, ends_at NULL, cancelled_at NULL, version | role_idは非一意。索引(role_id,starts_at,ends_at)。重複許可。有効判定starts<=t<ends、cancel適用時刻までの区間を保存 |

イベント保持は受理・記録時から90日を採用する。古い獲得時刻の新規イベントを即削除しないため。検索は獲得時刻、削除はexpires_at。rateの負値・小数は初期案で拒否、個別値の精度はDR03。ブーストは無期限保存を初期案とし取消は論理削除。VC未精算区間が参照する履歴を失わない。

### 2.2 VC計測・未受取

| 表 | 主な列とキー | 制約／索引／保持 |
|---|---|---|
| leveling_voice_state | PK user_id, measurement_epoch, state, last_channel_id NULL, last_confirmed_at, checkpoint_version, pending_cycle, cap_notice_attempted, next_grant_seq, consumed_segment_seq, consumed_offset_us, prepared_grant_seq NULL, prepared_random NULL, calculation_version, eligible_elapsed_us | tracking/suspended/reconciling/stopped。単調時計値をプロセス跨ぎで使用しない。最後のDB成功値を保持 |
| leveling_voice_segments | PK(user_id,segment_seq), start_at,end_at,channel_id,duration_us,rate_snapshot,shard_eligible,power_eligible,grant_seq | 時系列非重複、正の時間、同一ユーザーの未精算単位のみ。60秒または境界精算commitで消費。保存済み端数は障害・90日経過でも削除しない |
| leveling_voice_grants | PK(user_id,grant_seq), measurement_epoch, operation_key UQ, period_end, committed_at | VCの付与再実行確認。stateの単調seqと併用し過去epochを受け付けない。90日後削除可能、stateのseqは巻き戻さない |
| leveling_voice_pending | PK(user_id,month_period_id,origin), voice_shard,bonus_shard,power_meter,version | origin=native/legacy。索引(month_period_id,user_id)。残高は受取まで無期限、受取済み0行は削除可。旧値が新上限を超えていても切捨てない |
| leveling_claims | PK claim_id, operation_key UQ, user_id, trigger(manual/month_close/late_closed_month), shard_amount,bonus_amount,power_released,committed_at | 受取結果の根拠、無期限。索引(user_id,committed_at) |
| leveling_claim_items | PK(claim_id,month_period_id,origin), before/claimed quantities | claim CASCADEは原則実行しない。月末再実行・移行残高追跡、無期限 |

pending集計をユーザー行ロック内でSUMして両上限の空きを計算。自動受取は指定月だけ、手動は全月を対象とする。上限を超えていた旧残高は獲得停止になるが受取可能。保存済み端数は障害履歴ではなく計測再開に必要な状態であり、専用障害履歴表は作らない。

### 2.3 期間残高・確定順位

| 表 | 主な列とキー | 制約／索引／保持 |
|---|---|---|
| leveling_periods | PK period_id, UQ(kind,start_at), end_at, status(OPEN/FINALIZED), finalized_at NULL, current_revision, coverage_start_at | kind=day/week/month。start/endはJST暦に一致。索引(status,end_at,period_id)。無期限 |
| leveling_period_users | PK(period_id,user_id), text_power,voice_power,action_power,unallocated_text,unallocated_voice,total_power | totalは計算列相当。未割当<=対応種別値。索引(period_id,total_power DESC,user_id)、各種別同型。OPEN作業表、確定版公開後に回収 |
| leveling_period_channel_users | PK(period_id,channel_id,kind,user_id), power | kind=text/voice。索引(period_id,kind,channel_id,power DESC,user_id)。OPEN作業表、確定版公開後に回収 |
| leveling_period_channels | PK(period_id,channel_id,kind), power | ユーザー行との同一tx更新。索引(period_id,kind,power DESC,channel_id)。OPEN派生cache、確定版公開後に回収 |
| leveling_ranking_revisions | PK(period_id,revision), created_at, source(close/correction), correction_id NULL, row_count, checksum | 初回revision=1。無期限。完成した版だけcurrent_revisionに指定 |
| leveling_ranking_rows | PK(period_id,revision,scope,metric,channel_key,subject_id), score,rank | scope=user/channel/channel_user。metric=total/text/voice/action、channel_key=0は全体、channel_userのみ実ID。索引(period_id,revision,scope,metric,channel_key,rank,subject_id)。score>0。確定入力から再生成可能な派生順位索引、無期限 |

SQLのnullable複合UQによる重複を避け、channel_key=0の明示sentinelを使用。ユーザー全体はmetric4種、channelとchannel_userはtext/voiceのみ。外部Discordユーザー／チャンネル削除をDB CASCADEにしない。

OPEN照会は対応残高に `RANK() OVER(ORDER BY score DESC)`、外側で順位・subject_idの順にLIMIT/OFFSET。確定版はranking_rowsの索引でページング。全順位をアプリに取得しない。任意ページジャンプのためOFFSETを初期採用、深いページの実測が悪ければ別途順序番号索引を検討。TOP10はLIMIT 10ではなくrank<=10。総数0なら1ページの空表示。

確定版の正本は§7のsnapshot_user_inputs／snapshot_channel_inputs。ranking_rowsへ内訳を4指標分コピーせず、正本からページ内のユーザーだけ内訳を合成してカードを再現する。名前はranking_rowsに固定せずchannels最新名をJOINする。削除後は最後の名前。チャンネル全体は対応kindのみ、総合チャンネル順位は初期対象外。

### 2.4 訂正・報酬・外部処理・移行

| 表 | 主な列とキー | 制約／索引／保持 |
|---|---|---|
| leveling_corrections | PK correction_id, request_key UQ, actor_id, reason, requested_at, approved_at, preview_hash, reannounce, status | 無期限。承認した要求の重複防止 |
| leveling_correction_changes | PK(correction_id,change_seq), period_id, old_revision,new_revision, scope,metric,channel_key,subject_id,old_score,new_score,old_rank NULL,new_rank NULL | 間接的に順位が変わるユーザーも保存。0化の順位はNULL。無期限 |
| leveling_correction_role_choices | PK(correction_id,user_id,role_id), old_qualified,new_qualified,decision,old_desired,new_desired | 特別ロール維持／剥奪、実行後結果はoutboxへ参照。無期限 |
| leveling_monthly_qualifications | PK(month_period_id,user_id), ranking_revision, is_top1,is_top10,consecutive_top1 | 月間結果から再計算可能、後続月も更新。無期限 |
| leveling_permanent_awards | PK(user_id,award_type), first_earned_month, earned_at, desired_granted, decision_version, last_correction_id NULL | 現在の連続記録と「過去に獲得済み」を分離。無期限 |
| leveling_role_desires | PK(user_id,role_id), desired, generation, source_month NULL, source_revision NULL, synced_generation NULL | 最新希望を同期。退出者にも希望は保持、API付与は在籍者のみ。無期限 |
| leveling_outbox | PK job_id, dedupe_key UQ, type, payload JSON, state, attempt_count,next_attempt_at,lease_until NULL,last_error_code NULL | 索引(state,next_attempt_at,job_id)。未完了は無期限、完了詳細は90日（永久監査への参照を保持） |
| leveling_announcement_parts | PK(period_id,revision,part_no), channel_id,message_id NULL,payload JSON,payload_hash,marker,state,attempt_token NULL,send_started_at NULL | 確定・訂正の送信追跡、無期限。削除済み投稿も記録は残す |
| leveling_migration_runs | PK migration_id, source_revision,source_digest,target_generation,cutover_at,status,checksums JSON | 同じsource_digestの二重適用禁止。無期限 |
| leveling_migration_items | PK(migration_id,source_table,source_key), source_values JSON,target_keys JSON,applied_at | 恒常・旧月間・旧未受取の原本値、無期限。秘密設定は保存しない |

訂正プレビュー自体は短命な署名付き状態またはアプリ内状態とし、期限15分を技術案とする。承認記録のみ永続。履歴JSONを唯一の数量正本にはしない。FKは期間・版・訂正・claimへの内部参照、削除RESTRICTを基本。ユーザーのDiscord退会で行を削除しない。

## 3. トランザクションとロック順（レビュー後の採用案）

全数量writerは共通ユースケースRepositoryとmutation gateを通る。単一プロセスを前提に、通常は共有gate＋ユーザー排他、締め最終段階・訂正・アカウント移行は排他gateとする。これにより普段のユーザー単位並行性を保ち、全員受取時のアプリ／DBロック交差をなくす。

**階層:** mutation gate → 必要なcoordinator → アプリuser lock（ID昇順）→ DB transaction → period全件（start_at,kind序数day/week/month,ID順）→ account全件（user ID順）→ voice_state全件（user ID順）→ segments（user,seq順）→ pending（user,month,origin順）→ 入力／集計（表順、PK順）→ 永久operation/claim/event/receipt → role desire/outbox。逆順取得・途中で上位階層へ戻る取得は禁止。

| 操作 | gateと事前処理 | DB内で必要なロック |
|---|---|---|
| VC checkpoint／60秒／境界付与 | 共有→coordinator（状態更新時のみ）→user | 付与・精算で触る全periodを先に確定、period→account→state→segments→pending→集計。保存だけでperiodを省略したtx内では付与へ昇格しない |
| 手動受取 | 共有→coordinator（必要時）→user。既知時間を取り込み、付与可能単位を先に見積る | checkpointが付与を発生させるなら最初から全periodを取得。account→stateを取った後でperiodを要求しない。純受取はperiod不要でpendingを減らすだけ |
| 月末事前受取 | 共有→user。境界drainは別ユースケースとして先に完了 | 対象月period→account→state→pending。新規付与をこのtx内で呼ばない |
| 締め最終tx | drain終了後に全ロック解放、排他gateを新規取得。共有から排他へupgrade禁止 | 対象と資格参照に必要なperiod集合を最初に列挙・取得→対象account全件→state全件→pending全件。userごとにstate取得後、次userのaccountへ戻らない。全員受取とsnapshot公開を一括commit |
| 訂正／account移行 | 排他gate。必要な状態保存はgate所有を渡した内部関数で実施し、gateを再入取得しない | 関連全period→両account／全対象account→state→残高→新revision／operation。関連periodを後から発見したらrollbackして再計画 |

period/accountがない場合も同じ段階・順序でUQ upsert→SELECT ... FOR UPDATE。prepared planのversionが変わっていれば開始から再評価。gate・user lockを保持したまま別タスクへ委譲してその完了を待たない。coordinatorを持たずにuser lockを取得した経路は、その後coordinatorを要求しない。

締め排他gateの取得待ち中は既存共有処理が完了できる。新たな共有待ちはキューイングし、破棄・遅延期限を導入しない。締め中に受信したVC状態変更はユーザー別最新状態を記録し、不明になった区間を推測加算しない。排他解放後に再照合する。締めtx内からDiscord・アプリuser lock・coordinatorを待たないため、`手動: user→period` と `締め: period→user` の循環は作れない。

この順序は設計上の待機循環を除くが、InnoDBのgap/UQ/FKロックや外部writerまで含め「deadlockが絶対に起きない」と保証しない。DB deadlock／lock timeoutはtx全体をrollbackし同一キー・乱数で最大3回再試行。外部writerは運用上禁止。commit不明はキー・version照会前に再実行しない。receipt/event UQ違反は全tx rollback後に既存結果を返す。Discord操作は必ずtx外。

MySQLでロック待ちグラフと障害注入試験を行う。[公式ロック読取り](https://dev.mysql.com/doc/refman/26.10/en/innodb-locking-reads.html)、[公式deadlock説明](https://dev.mysql.com/doc/refman/8.0/en/innodb-deadlocks.html)。実環境のversion・分離レベルは切替前に確認し、SQLiteだけで保証しない。

## 4. 訂正の整合性

確定periodはcurrent_revisionのsnapshot入力を正本として読む。訂正はこの入力を新revisionの作業集合へコピーして変更し、全scopeの派生順位を生成後に公開pointerを切替える。削除済みOPEN表を正本に戻さない。旧revisionは不変。日／週／月の独立性から一つの訂正を他種類へ自動伝播しない。channel_user変更はchannelと全体種別へ同じdelta、総合も再計算。全体addは未割当値を変更。全体set/removeがchannel合計を下回る場合はArchitecture §10の比例縮小案による内訳変更をプレビューして承認させる。負の目標・不正入力は拒否する。

将来の前期比較は同kindの隣接期間とsubject IDでJOINできる。訂正後の最新比較と当初発表版比較の両方が可能。

## 5. 保持・削除・運用

削除workerは起動時と日次でexpires_atを走査し小batchでcommit、失敗箇所から再開。90日より前には消さない。event子行のみcascade、確定版正本・pending・claim・revision・訂正・資格・移行原本は消さない。公開済み確定期間のOPEN作業表だけは§7に従い回収する。未完了outboxを期限だけで消さない。receipt削除はDR01の保証制約を伴う。

イベント検索はuser/time、kind/time、channel/event JOINを組合せる。実データ分布でEXPLAINを確認し、全組合せの巨大索引は作らない。常駐ランキングパネルは集計queryを再利用。バックアップに全無期限表を含め、最大行数・索引容量・締め時間・outbox滞留・pending不整合を監視する。

## 6. 補足契約

- event.kindはtext/voice/action/admin/import/claimを区別可能にする。獲得履歴UIのXP種別フィルタはテキスト・VC・アクション・ボーナスを表示契約とし、内部原因種別と混同しない。ボーナス検索はbonus_shard>0。claimは獲得の再計上として扱わず永久claim台帳が正本。
- receiptは処理対象として受け付けたメッセージを記録する。cooldown等で確定的に不付与とした入力もoutcomeを保存すれば再配送時の再評価を防げる。対象外Guild・未許可Botなど不正入力はDBへ保存しない。
- 巨大なシャード量の成長計算は268375でprestige商・剰余を求め、gradeは最大50段階で計算する同値な最適化案とする。現行式を変更せず、倍率が大きいほどループが無制限に伸びる実装を避ける。totalと全加算先の精度超過も同時に検査する。
- 月末最終txは新たなpendingが0になるまで対象月の行をロックして受け取る。同じ月のwriterはperiodロックで止まるため収束する。手動受取／付与とはmutation gateで最終段階を分離し、事前段階は固定DB順序で直列化する。
- snapshot checksumは安定したキー順・整数表現で計算し、訂正前後で版ごとに保存。完全性確認に使い、署名・改ざん防止の保証とはしない。
- outboxの永久監査が必要な訂正role変更は、完了詳細の90日削除前にcorrection_role_choicesへ実行結果・完了日時を追記する。希望変更とDiscord適用結果を混同しない。

## 7. 正本・派生データと確定時の切替

| 状態・データ | 正本 | 派生・再生成可能 | 不一致時の処理 |
|---|---|---|---|
| OPEN period | period_channel_usersの各power、period_usersのunallocated_text/unallocated_voice/action_power | period_usersのtext/voice/total、period_channels | period行をロックし正本からcache再生成。eventからの全再計算はしない |
| FINALIZED revision | snapshot_user_inputsの未割当text/voice/action、snapshot_channel_inputsのchannel-user power | ranking_rowsのscore/rank、月間資格cache | 指定revisionの正本から再生成。正本自体が不正なら自動数値修正せず訂正経路へ |
| 恒常 | accountsの種類別累積残高 | prestige/grade/shard | 新規処理は同一txで整合。旧不一致はDR05で移行停止 |
| 履歴 | eventsは90日間の原因・受理結果、operation/correction/claim台帳は各契約の監査正本 | 表示・24h集計 | eventsを期間残高の無期限正本にしない |

追加する論理表:

| 表 | キー・列 | 保持・索引 |
|---|---|---|
| leveling_snapshot_user_inputs | PK(period_id,revision,user_id), unallocated_text,unallocated_voice,action_power | 全て0なら省略可、無期限。FK revision RESTRICT |
| leveling_snapshot_channel_inputs | PK(period_id,revision,channel_id,kind,user_id), power | >0のみ、無期限。索引(period_id,revision,user_id,kind)。FK revision RESTRICT |
| leveling_operations | PK operation_key, kind,actor_id,request_hash,status,before_values JSON,after_values JSON,created_at,completed_at | 管理者操作・account移行・送信unknown解決の永久台帳。本文／秘密情報なし |
| leveling_import_items | PK(source_kind,source_guild_id,source_user_id,approved_revision), source_digest,calculation_version,applied_shard,operation_key | MEE6の取込み量・承認差分を永久保存。UQ(source_kind,source_guild_id,source_user_id,source_digest,calculation_version) |
| leveling_event_ownership_moves | PK(operation_key,source_user_id),target_user_id,cutoff_event_id,moved_at | 原本userを保存しhotnessの表示移動を追跡。再移行は時刻順に適用、循環も有限台帳順で評価。永久監査 |

締めtxでOPEN正本→snapshot入力→ランキングを作成しchecksum検査後、current_revisionとFINALIZEDを同時commitする。公開後の読者は必ずsnapshot経路。OPEN読者はperiod状態とデータを同一読取snapshotで読み、確定と回収の競合を避ける。回収workerは公開revisionの存在・件数・checksumを確認し、period_users/channel_users/channelsの旧作業行のみbatch削除。途中停止しても公開版は不変、再実行可。FINALIZEDの入力行へ通常writerは到達しない。

訂正ごとに正本入力を全件コピーする単純方式を採用。差分鎖方式より再現と原子公開が容易で、初期版の訂正頻度を低く見込むため。保存量は下記で見積り、実績増加時に別設計として見直す。ranking_rowsの3種内訳重複は廃止し、score/rankは高速ページングと当時順位保存のため意図的に保持する。未割当0行は省略、全種別0ユーザーも順位行を作らない。

## 8. 保存量の概算

期間pで、U_p=全体順位ユーザー数、C_p=非0のchannel-kind数、E_p=非0のchannel-kind-user組数、B_p=未割当またはactionの非0ユーザー数（B<=U）、K_p=保存revision数とする。channel-kindを数えるためtext/voiceを再度2倍しない。

- OPEN作業行数: `U_p + E_p + C_p`。通常は現在の日週月3期間、障害で未締めが溜まった分だけ追加。
- 確定1版の正本入力: `B_p + E_p`。派生順位: `R_p <= 4*U_p + E_p + C_p`。
- 確定全体の行数概算: `Σ_p K_p*(B_p + E_p + R_p)`。日365/366、週52/53、月12の実際の開始数を用い、日と月のU/Eを同じと決めつけない。
- byte概算: `Σ_p K_p*(B_p*b_input + E_p*b_channel + R_p*b_rank)*f_index`。各bは実MySQLで測った平均行長、f_indexは索引込み係数。DECIMAL(65,0)1列自体は約29byteだが行header/PK/索引等を別に見込む。圧縮率を保証しない。
- 90日event: `90*日平均event数*(親行byte + 平均channel子行数*b_child + 平均period子行数*b_period)`＋message receipt＋90日grant。獲得時刻でなく記録時刻保持なので遅延入力ピークを別に見込む。
- claim/operation/訂正監査/移行原本/発表payload/未完了outboxは別枠の無期限増加。pending/未精算segmentsは未受取・休眠者数に依存し90日で消せない。

例（容量計画用の仮定、実測値ではない）: 年429期間、各期間U=1,000,E=3,000,C=100,B=1,000、K=1.02とすると、正本4,000＋順位最大7,100＝11,100行/版、約486万行/年。b_input=160,b_channel=120,b_rank=160 byte、f_index=2なら約1.45GB/年（10進、履歴・backup別）。旧設計の作業表永続保存ならさらに約176万行/年が加わるため回収する。旧ranking_rows内訳3列×7,100行も除去でき、約27万〜62万byte/版程度の値重複を避ける（適用対象行数による）。

計算は `429*1.02*(1000*160+3000*120+7100*160)*2 = 1,449,264,960 byte`。実運用では日・週・月ごとに見積りを分け、訂正件数、二次索引、binlog、replica、backupの倍率を加える。無期限保存に上限を後付けせず容量監視で対応する。

## 9. VC・メッセージ・管理操作のキー寿命

VCのseq、消費位置、prepared_randomはstateと一体更新し、grantの90日削除で巻き戻らない。DB再接続時はexpected_versionを確認、古いepochの未commit命令は拒否するが保存済み端数そのものは新epochで続行できる。境界精算とcheckpointは同じ消費位置を競合更新するため一方だけがCAS成功する。

message receiptの有効期間は `[processed_at,processed_at+90日)`。期限内重複ではexpiresを延長しない。期限後のIDは行が物理削除前でも、receiptとexpired eventを同じtxで整理して新しい処理generationを作れる。operation_keyはmessage ID単独ではなく `message:id:generation`、receipt PKはIDのまま現generationを指す。90日超の再投入も通常経路で受付し、OPEN期間なら再計上し得る。無期限監査のoperation_keyと混同しない。


## 10. 実装前に固定する細部

- Decimalの既定precisionに依存しない。係数・率を整数分子／分母に正規化し、時間積分とfloorは任意精度整数の除算で行う案を採用する。DBへ保存する整数値が0..10^65-1か検査する。巨大な中間積をDBで計算して丸める経路は使わない。
- prepared_grant_seq/randomは最初の既知segmentを保存するcheckpointでstateに確保する。準備txは残高を増やさない。次の付与txがその乱数と未消費segmentを使用し、成功時だけseqを進め準備を消す。境界が60秒より先に来たらその準備乱数で比例精算する。
- 月末事前受取は在室ユーザーの既知区間保存を先行ユースケースで完了し、解放する枠をDBから読み直す。最終排他内での受取後はキャッシュを無効化し、次回計測が旧上限状態を使わないようstate versionを進める。
- Discord role同期用mutexは数量更新用user lockと別にする。希望状態を短いDB読取で得たらgate／DBロックを解放してAPIを呼ぶ。API終了後のversion照会は新しい読取として開始し、数量ロック保持中に同期完了を待たない。
- 削除・cache修復も対象periodの固定順序に従い、snapshot正本を変更しない。公開版を参照する読取りは一つのDB read snapshotに閉じる。READ COMMITTEDで複数statementに分かれる場合はperiod状態再確認と再読取りを行う。

## 11. P1との接続条件（2026-11-01、DB実装は未着手）

- DR06は決定済み。全期間不受理でも恒常シャードは通常付与し、power_meterを消費しない。月確定済みのVCシャードは独立上限適用後、付与と同一txでlate_closed_month受取する。
- DR07は決定済み。期限前確定、手動強制発表、月間パワー強制削除を許すRepository経路を追加しない。暦月終了後の未完了締め再実行と管理者訂正を区別する。
- P1の数値APIはPython intを格納数量の正本とする。SQLAlchemyのDecimal DTO変換では整数性・有限性を検証してから渡し、float経由で変換しない。
- `rate_snapshot` は合算率であり、個別予約のDECIMAL(65,0)上限を超える中間値になり得る。P2では正確な整数文字列として保存する（係数の正規化文字列と同様）。個別予約の範囲と最終付与整数・残高合計の範囲は引き続き検査し、倍率の業務上限を導入しない。
- 単位・消費残余・固定乱数・pending・期間power・恒常catch-upは同一txで適用する。P1単独ではDB冪等性や月末受取を保証しない。

## 12. P2実装上の補足（2026-11-01）

claimsにmonth_period_idを追加し、手動受取はNULL、自動受取は月ID必須とした。空の受取でも同一キーの別月再利用を拒否する。複合FKの名前は全列を含めて衝突を避ける。prepared seq/randomは両方NULLまたは両方非NULLをCHECKで強制する。

旧起動経路を維持するため、新metadata・Alembic lineage・version tableを分離した。revisionはp2_20261101_01。本番への統合は後続の切替設計で扱う。[実装一覧と検証](LEVELING_P2_REPORT.md)を参照。
