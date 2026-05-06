@AGENTS.md

# Claude Code

Shared project instructions live in [`AGENTS.md`](AGENTS.md). Claude Code loads
this file as its entrypoint, imports the shared guidance above, and avoids
duplicating long-lived rules here.

## Claude-specific notes

- Prefer `lean-ctx` MCP tools over native equivalents when reading or
  searching: `ctx_read` instead of `Read`, `ctx_search` instead of `Grep`,
  `ctx_shell` for commands with verbose output. Native `Edit` / `Write` stay
  unchanged.
- For non-trivial changes (anything beyond a typo or one-line fix), draft a
  plan in plan mode first. The PRD is detailed; jumping into code without a
  plan loses context fast.
- Keep this file short. If a rule applies to all agents, put it in
  `AGENTS.md` instead.
- If Claude repeatedly makes the same project-specific mistake, codify it as
  a durable rule in `AGENTS.md`.
