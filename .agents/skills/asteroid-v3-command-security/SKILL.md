---
name: asteroid-v3-command-security
description: Use when an older Asteroid_V3 command-security request appears; keep this compatibility entry and route current command, UI callback, permission, setup, and audit-log work to asteroid-v3-app-command-guideline.
---

# Asteroid V3 Command Security

This skill is kept as a compatibility entry point. For current command, permission, setup command, UI callback, response, and command audit logging rules, load `asteroid-v3-app-command-guideline`.

Also load `asteroid-v3-logging-guideline` when the command or UI callback changes DB rows, roles, channels, punishment state, reports, ranking, XP, shards, power, setup posts, persistent messages, or other user/server state.
