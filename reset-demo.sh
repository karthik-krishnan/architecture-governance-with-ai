#!/usr/bin/env bash
# reset-demo.sh — wipe all agent-generated artifacts so the demo runs from scratch
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "Resetting demo — removing all generated artifacts..."
echo ""

# Generated ArchUnit fitness functions (structural agent output)
if [ -d "$REPO_ROOT/generated-tests" ]; then
    rm -rf "$REPO_ROOT/generated-tests"
    echo "  ✓  deleted generated-tests/"
else
    echo "  –  generated-tests/ (already absent)"
fi

# Generated OpenAPI spec + Spectral JUnit report (API agent output)
if [ -d "$REPO_ROOT/generated-specs" ]; then
    rm -rf "$REPO_ROOT/generated-specs"
    echo "  ✓  deleted generated-specs/"
else
    echo "  –  generated-specs/ (already absent)"
fi

# Generated Spectral ruleset (API agent output, lives in inputs/)
RULESET="$REPO_ROOT/architecture-skill-demo/inputs/spectral-ruleset.yaml"
if [ -f "$RULESET" ]; then
    rm "$RULESET"
    echo "  ✓  deleted architecture-skill-demo/inputs/spectral-ruleset.yaml"
else
    echo "  –  spectral-ruleset.yaml (already absent)"
fi

# Agent run outputs (scan reports, reference copies of generated artefacts)
if [ -d "$REPO_ROOT/architecture-skill-demo/outputs" ]; then
    rm -rf "$REPO_ROOT/architecture-skill-demo/outputs"
    echo "  ✓  deleted architecture-skill-demo/outputs/"
else
    echo "  –  architecture-skill-demo/outputs/ (already absent)"
fi

echo ""
echo "Done. The repo is back to a clean demo state."
echo ""
echo "Next steps:"
echo "  cd architecture-skill-demo"
echo "  python3 structural_fitness_agent.py   # generates ArchUnit tests"
echo "  python3 api_fitness_agent.py          # generates OpenAPI spec + Spectral ruleset"
echo "  python3 run_tests.py                  # open governance report in browser"
echo ""
