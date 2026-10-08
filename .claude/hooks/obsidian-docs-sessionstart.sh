#!/usr/bin/env bash
# SessionStart hook: inject the Obsidian docs hub into Claude's context.
# Portable: silently no-ops if the vault is absent.
# Hooks inherit Claude's *current* cwd (can change mid-session) -> anchor to project root.
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" 2>/dev/null || exit 0
DOCS=".claude/docs/obsidian"
[ -f "$DOCS/INDEX.md" ] || exit 0

echo "PROJECT DOCUMENTATION GRAPH: this project keeps its full documentation as an Obsidian vault at $DOCS/ (hub: INDEX.md). Before writing new code, consult the code map notes (code-map/) to check whether a similar file/class/function/method already exists — prefer adapting existing code over creating duplicates. Keep the vault updated as you work."
echo ""
echo "--- $DOCS/INDEX.md ---"
cat "$DOCS/INDEX.md"
exit 0
