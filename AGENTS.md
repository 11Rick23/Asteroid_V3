# Asteroid_V3 AI Instructions

## 基本方針

- 正確性を最優先にし、不明瞭な点や仕様判断が必要な点は確認する。
- 回答、ユーザー向け文言、Discord の表示文言は原則として日本語にする。
- 既存の責務分割、命名、ファイル構成、Discord.py の実装パターンに合わせる。
- 関係のないリファクタリング、仕様変更、依存関係追加、メタデータ変更は行わない。
- 秘密情報を出力・記録しない。`.env`、`config.yaml`、トークン、DB URL、API キーは必要最小限の確認に留める。

## スキルの使い分け

Asteroid_V3 の作業では、内容に応じて必要な専門スキルを直接読み込む。
詳細ルールは `AGENTS.md` に重複させず、`.agents/skills` の専門スキルへ置く。

- 構造や配置: `$asteroid-v3-structure-guideline`
- 機能追加、Cog、イベント、タスク、設定: `$asteroid-v3-feature-guideline`
- Slash command、View、Modal、権限、応答、監査ログ: `$asteroid-v3-app-command-guideline`
- ログレベル、監査ログ、例外ログ: `$asteroid-v3-logging-guideline`
- SQLAlchemy、Repository、DB 状態、マイグレーション: `$asteroid-v3-database-guideline`
- Ruff、Pyright、型、import、Discord.py narrowing: `$asteroid-v3-code-style-guideline`
- pytest、fake Discord objects、権限・guild scope テスト: `$asteroid-v3-test-guideline`
- uv、mise、起動、依存関係、検証コマンド: `$asteroid-v3-runtime-guideline`
- `.agents/skills`、`AGENTS.md`、`.agents/README.md`、`agents/openai.yaml` の管理: `$asteroid-v3-skill-maintenance`
- 古い `$asteroid-v3-overview` 参照: 互換ポインタとして扱い、通常作業では専門スキルを直接使う。

## 作業の進め方

- 大きな変更や影響範囲が広い変更では、不明点を明確にしてから段階的な実装計画を作る。
- UI、View、Modal、Select、Button、command 群も長いファイルの例外扱いにしない。
- 既存の長いファイルは方針ではなく負債として扱い、触る範囲で安全に分割できる場合は分割する。
- Command、UI callback、listener、scheduled task は operating guild の制約を意識し、必要な専門スキルを併用する。
- DB、権限、ログ、テストにまたがる変更では、該当する専門スキルを複数使う。
- セットアップ、設定、機能一覧、ディレクトリ構成、開発コマンド、移行手順、AI 共有基盤に影響する変更では `README.md` も必ず確認し、必要なら同じ変更で更新する。

## 検証

- 変更中は焦点を絞った pytest や静的チェックを先に実行する。
- 共有基盤、権限、DB、command registration、guild scope を触った場合は広めに検証する。
- 最終確認は変更範囲に応じて `mise run test`、`mise run typecheck`、Ruff、`mise run check` を使い分ける。
- `mise run lint` は `--fix` によりファイルを書き換えるため、意図したタイミングでのみ実行する。

## AI ドキュメント管理

- `.agents/skills` をチーム共有スキルの正本とする。
- `AGENTS.md` は常時読む入口、`.agents/README.md` はチーム運用、`asteroid-v3-skill-maintenance` はスキル保守手順に限定する。
- スキルを追加・削除・改名・責務変更した場合は、`asteroid-v3-skill-maintenance`、`.agents/README.md`、必要に応じて `AGENTS.md` と `README.md` を更新する。
