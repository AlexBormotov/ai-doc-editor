# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

Claude-specific wiring only; the working agreement lives in `AGENTS.md`.

- Development machine is Windows: use `uv run poe <task>`, not `make`. Paths with `!` in them
  (`D:\Projects\!Python\...`) need quoting in Bash.
- Project documentation is an Obsidian vault in `docs/obsidian/` (hub `INDEX.md`, one
  note per source file in `code-map/`, `Timeline.md`). Hooks in `.claude/settings.json` load the
  hub at session start and require a documentation pass after a turn that changed source files.
- The method this repository follows (intent, spec, plan, oracle, gates) is in the local
  `ai-factory-kit/` folder, which is not part of the repository. Its `skills/` are reference only.
