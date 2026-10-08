#!/usr/bin/env bash
# Stop hook: if source files changed this turn, block the stop once and tell Claude
# to update the Obsidian docs vault (code map + timeline). Guarded against loops via
# stop_hook_active and by clearing the marker before blocking.
# Portable: no jq; silently no-ops if the vault is absent.
# Hooks inherit Claude's *current* cwd (can change mid-session) -> anchor to project root.
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" 2>/dev/null || exit 0
DOCS=".claude/docs/obsidian"
MARKER="$DOCS/.pending-changes"
CHANGED="$DOCS/.changed-files"

input=$(cat)

# Already continuing because of a stop hook -> always allow stopping
if printf '%s' "$input" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  rm -f "$MARKER" "$CHANGED"
  exit 0
fi

[ -f "$MARKER" ] || exit 0

files=$(sort -u "$CHANGED" 2>/dev/null | head -20 | tr '\n' ' ' | tr -d '"')
rm -f "$MARKER" "$CHANGED"

cat <<EOF
{"decision":"block","reason":"DOCUMENTATION UPDATE REQUIRED. Source files changed this turn: $files. Update the Obsidian docs vault at $DOCS/ now: (1) for each new or changed file, create or update its note in code-map/<area>/ (e.g. code-map/backend/app-api-v1-auth.md) describing the file's purpose and every class/function/method (signature + one-line description), linking related notes with [[wikilinks]]; (2) update the relevant section note (Backend/Frontend/etc.) so the new note is reachable from it; (3) add an entry to Timeline.md as the newest entry on top: insert a new line directly below the '<!-- NEW-ENTRIES-BELOW' marker line, formatted 'YYYY-MM-DD HH:MM — what was done' (use the local date and time). Add it by replacing ONLY that marker line (old_string = the marker line, new_string = the marker line + your new entry) so existing entries are not rewritten and no extra tokens are spent shifting lines. If the changes were not code (config, scripts, docs), a Timeline.md entry is enough. Then finish your reply."}
EOF
exit 0
