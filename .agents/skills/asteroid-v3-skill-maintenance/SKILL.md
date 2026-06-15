---
name: asteroid-v3-skill-maintenance
description: Use when creating, renaming, deleting, validating, or reorganizing Asteroid_V3 repository skills, AGENTS.md, .agents/README.md, agents/openai.yaml, or skill compatibility pointers.
---

# Asteroid V3 Skill Maintenance

Use this skill for Asteroid_V3 AI documentation and repository-scoped skill maintenance. Do not use it for normal bot implementation work unless the task also changes `.agents/skills`, `AGENTS.md`, or `.agents/README.md`.

## Source Of Truth

- Shared skills live in `.agents/skills`.
- `AGENTS.md` is the always-loaded project instruction entry point.
- `.agents/README.md` is the team-facing maintenance and skill map document.
- Specialist skills own implementation guidance for code, commands, DB, logs, tests, structure, and runtime.
- Compatibility skills may exist, but they should point to the current owner instead of duplicating rules.

## Workflow

1. Inspect the current files before editing.
   - Read `AGENTS.md`, `.agents/README.md`, and affected `SKILL.md` files.
   - Use `rg` to find old skill names, duplicated responsibilities, and stale prompts.
2. Decide ownership.
   - Put always-on project rules in `AGENTS.md`.
   - Put team maintenance rules and the skill map in `.agents/README.md`.
   - Put task execution procedures in the specialist skill that owns the topic.
   - Keep compatibility entries thin.
3. Edit narrowly.
   - Prefer updating an existing focused skill over creating an overlapping one.
   - When adding a skill, create a folder whose name exactly matches the skill `name`.
   - Keep `SKILL.md` concise enough to load directly; move large examples into one-level `references/` files only when they are truly needed.
   - Do not create extra README, changelog, or process notes inside individual skill folders.
4. Keep metadata aligned.
   - `SKILL.md` frontmatter must contain only `name` and `description`.
   - `description` must include the real trigger conditions because it is the primary activation surface.
   - `agents/openai.yaml` should have a clear `display_name`, a 25-64 character `short_description`, and a `default_prompt` containing the correct `$skill-name`.
5. Preserve compatibility when useful.
   - If a skill name may still be referenced, replace it with a thin pointer instead of deleting it immediately.
   - The pointer should name the current skill to load and avoid copying detailed rules.

## Validation

- Run `quick_validate.py` against every changed skill directory when available.
- If `quick_validate.py` fails with `ModuleNotFoundError: No module named 'yaml'`, use a temporary `yaml.py` shim backed by `ruamel.yaml` and run it through `uv run python`.
- Check each changed `agents/openai.yaml` still contains the corresponding `$skill-name`.
- Use `git status --short` to confirm only intended repository files changed.
- If using `plugin-eval`, compare before and after only for the changed skill and keep fixes narrow.
