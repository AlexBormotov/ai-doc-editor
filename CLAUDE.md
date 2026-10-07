# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

Claude-specific wiring only; the working agreement lives in `AGENTS.md`.

- Development machine is Windows: use `uv run poe <task>`, not `make`. Paths with `!` in them
  (`D:\Projects\!Python\...`) need quoting in Bash.
- The method this repository follows (intent, spec, plan, oracle, gates) is in the local
  `ai-factory-kit/` folder, which is not part of the repository. Its `skills/` are reference only.
