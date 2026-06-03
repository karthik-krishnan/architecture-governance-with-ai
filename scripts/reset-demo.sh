#!/usr/bin/env bash
# reset-demo.sh — wipe all agent-generated artifacts so the demo runs from scratch
#
# Cleans generated artifacts across ALL company folders (not just example-company),
# matching the same patterns used in .gitignore.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo ""
echo "Resetting demo — removing all generated artifacts..."
echo ""

# Generated ArchUnit fitness functions and OpenAPI specs (under any projects/ tree)
count=0
while IFS= read -r -d '' dir; do
    rel="${dir#$REPO_ROOT/}"
    rm -rf "$dir"
    echo "  ✓  deleted $rel"
    count=$((count + 1))
done < <(find "$REPO_ROOT" -type d \( -name "generated-tests" -o -name "generated-specs" \) -not -path "*/node_modules/*" -print0)
if [ "$count" -eq 0 ]; then
    echo "  –  generated-tests/ and generated-specs/ (already absent)"
fi

# Generated Spectral rulesets (under any architecture/ tree)
count=0
while IFS= read -r -d '' file; do
    rel="${file#$REPO_ROOT/}"
    rm "$file"
    echo "  ✓  deleted $rel"
    count=$((count + 1))
done < <(find "$REPO_ROOT" -type f -name "spectral-ruleset.yaml" -not -path "*/node_modules/*" -print0)
if [ "$count" -eq 0 ]; then
    echo "  –  spectral-ruleset.yaml (already absent)"
fi

# Agent run outputs (scan reports, reference copies)
if [ -d "$REPO_ROOT/outputs" ]; then
    rm -rf "$REPO_ROOT/outputs"
    echo "  ✓  deleted outputs/"
else
    echo "  –  outputs/ (already absent)"
fi

echo ""
echo "Done. The repo is back to a clean demo state."
echo ""
echo "Next steps:"
echo "  python3 agents/structural_fitness_agent.py   # generates ArchUnit tests"
echo "  python3 agents/api_fitness_agent.py          # generates OpenAPI spec + Spectral ruleset"
echo "  python3 scripts/run_tests.py                 # open governance report in browser"
echo ""
