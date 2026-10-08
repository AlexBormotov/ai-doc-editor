#!/usr/bin/env bash
# PostToolUse hook (Write|Edit|NotebookEdit): record that source files changed this turn.
# The Stop hook later uses this marker to demand a documentation update.
# Portable: no jq; silently no-ops if the vault is absent.
# Hooks inherit Claude's *current* cwd (can change mid-session) -> anchor to project root.
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" 2>/dev/null || exit 0
DOCS=".claude/docs/obsidian"
[ -d "$DOCS" ] || exit 0

input=$(cat)
fp=$(printf '%s' "$input" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*:[[:space:]]*"//; s/"$//')

# Ignore edits to the docs vault / Claude config itself and empty paths
case "$fp" in
  *".claude"*|"") exit 0 ;;
esac

printf '%s\n' "$fp" | tr '\\' '/' | tr -s '/' >> "$DOCS/.changed-files"
touch "$DOCS/.pending-changes"
exit 0
