#!/bin/bash
# SessionStart hook: keeps graphify-out/ fresh and tells Claude to open with a short
# "graphify checked" greeting instead of starting cold or silent.
if [ -d graphify-out ] && command -v graphify >/dev/null 2>&1; then
  OUT=$(graphify update 2>&1)
  SUMMARY=$(echo "$OUT" | grep -E 'Rebuilt:|up to date|No code-graph topology changes' | tail -1 | sed 's/\[graphify watch\] //')
  jq -n --arg ctx "This project (vos-tool) has a graphify knowledge graph at graphify-out/. It was just checked/updated at session start. ${SUMMARY:+$SUMMARY }Before anything else, greet the user with one short line confirming this, e.g. \"graphify checked — what do you want to modify today?\", then proceed. Use graphify query/explain instead of raw grep when answering questions about this codebase." \
    '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
fi
