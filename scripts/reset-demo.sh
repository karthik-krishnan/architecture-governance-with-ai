#!/usr/bin/env bash
# reset-demo.sh — wipe all agent-generated artifacts so the demo runs from scratch
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_DIR="$REPO_ROOT/example-company/projects/order-service"
GOVERNANCE_DIR="$REPO_ROOT/example-company/architecture"

echo ""
echo "Resetting demo — removing all generated artifacts..."
echo ""

# Generated ArchUnit fitness functions (structural agent output)
if [ -d "$PROJECT_DIR/generated-tests" ]; then
    rm -rf "$PROJECT_DIR/generated-tests"
    echo "  ✓  deleted example-company/projects/order-service/generated-tests/"
else
    echo "  –  generated-tests/ (already absent)"
fi

# Generated OpenAPI spec + Spectral JUnit report (API agent output)
if [ -d "$PROJECT_DIR/generated-specs" ]; then
    rm -rf "$PROJECT_DIR/generated-specs"
    echo "  ✓  deleted example-company/projects/order-service/generated-specs/"
else
    echo "  –  generated-specs/ (already absent)"
fi

# Generated Spectral ruleset (API agent output, lives in architecture/)
RULESET="$GOVERNANCE_DIR/spectral-ruleset.yaml"
if [ -f "$RULESET" ]; then
    rm "$RULESET"
    echo "  ✓  deleted example-company/architecture/spectral-ruleset.yaml"
else
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
