# Asteroid_V3 Agent Skills

This directory contains repository-scoped Codex skills for Asteroid_V3. These
skills are checked into the repository so the team shares the same AI guidance.

## Responsibility Split

- `AGENTS.md`: always-loaded project instructions. Keep it broad and stable.
- `.agents/README.md`: team operation notes for maintaining these skills.
- `asteroid-v3-skill-maintenance`: AI-facing workflow for creating, renaming, validating, and reorganizing shared skills.
- `asteroid-v3-*-guideline`: focused implementation rules for one responsibility area.
- `asteroid-v3-command-security`: compatibility pointer for older command-security requests.
- `asteroid-v3-overview`: legacy compatibility pointer for older overview requests.

Do not copy detailed specialist rules into `AGENTS.md`; add them to the relevant
skill instead.

## Skill Map

| Skill | Use for |
| --- | --- |
| `asteroid-v3-skill-maintenance` | Creating, renaming, deleting, validating, or reorganizing shared skills and AI docs. |
| `asteroid-v3-structure-guideline` | Project map, ownership boundaries, and where a change belongs. |
| `asteroid-v3-feature-guideline` | Features, cogs, listeners, tasks, config, file splitting, and guild-scoped behavior. |
| `asteroid-v3-app-command-guideline` | Slash commands, setup commands, persistent views, UI callbacks, permissions, responses, and command audit logs. |
| `asteroid-v3-logging-guideline` | Log levels, audit log content, exception logs, and log assertions. |
| `asteroid-v3-database-guideline` | SQLAlchemy models, repositories, DB sessions, migrations, and persistent state. |
| `asteroid-v3-code-style-guideline` | Ruff, Pyright, Pylance, typing, imports, Discord.py narrowing, and code organization. |
| `asteroid-v3-test-guideline` | pytest design, fake Discord objects, permission tests, guild-scope tests, service/repository tests, and caplog. |
| `asteroid-v3-runtime-guideline` | uv, mise, startup, dependencies, verification commands, and local tooling. |
| `asteroid-v3-command-security` | Legacy entry point that redirects current work to app-command and logging guidance. |
| `asteroid-v3-overview` | Legacy entry point that redirects normal work to `AGENTS.md` and skill maintenance to `asteroid-v3-skill-maintenance`. |

## Team Usage

- Treat `.agents/skills` as the source of truth for shared Asteroid_V3 skills.
- Start normal Asteroid_V3 work from `AGENTS.md`, then load the specialist skills required by the task.
- Use `$asteroid-v3-skill-maintenance` when changing shared skills or AI documentation.
- Avoid keeping local duplicate `asteroid-v3-*` skills enabled, because Codex may show both the local and repository versions.
- Keep `AGENTS.md` readable in every task; it should explain routing and non-negotiable repo rules, not every implementation detail.

## Updating Skills

- Prefer updating an existing focused skill over adding an overlapping one.
- Update `asteroid-v3-skill-maintenance` whenever the maintenance workflow changes.
- Update this README whenever a skill is added, renamed, removed, or materially changes responsibility.
- Preserve compatibility skills when practical instead of deleting old names immediately.
- Keep each `SKILL.md` concise enough to load directly. Move large examples or reference tables into one-level `references/` files only when needed.
- Make each `description` trigger on its own; do not rely on another skill being loaded first.
- When changing a skill, verify that `SKILL.md` has `name` and `description`, and that `agents/openai.yaml` still points at the correct `$skill-name`.
- If `quick_validate.py` is available, run it against each changed skill directory.

## Local Duplicates

The previous personal copies of these skills may exist in an archive or another
local skills directory. If Codex shows duplicate `asteroid-v3-*` skills, disable
or move the local copy and keep the repository copy active.
