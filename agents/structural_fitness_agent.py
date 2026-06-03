#!/usr/bin/env python3
"""
Structural Fitness Agent
========================
An AI agent that reads a live Java codebase and enterprise architecture governance
documents, then generates compilable ArchUnit fitness function tests.

The agent runs three phases:

  PHASE 1 — SCAN
    Codebase Scanner skill reads all Java source files and produces a structured
    report: package inventory, layer violations, cross-context imports, banned
    libraries, security risks.

  PHASE 2 — GENERATE
    ArchUnit Generator skill reads the scan output + ADRs + architecture standards
    + API style guide and produces a complete, generic ArchUnit test class.

  PHASE 3 — VERIFY (agentic loop)
    The generated code is compiled with `mvn test-compile`. If it fails, the
    compiler errors are fed back to the agent which corrects and retries.
    Repeats up to MAX_COMPILE_ITERATIONS times until the code compiles clean.

The verified test class is written to generated-tests/ at the Maven project root.
Maven is configured to include that directory automatically, so:

    python3 structural_fitness_agent.py      # runs the agent
    cd .. && mvn test                        # compiles and runs all tests

Usage:
    python3 structural_fitness_agent.py
    python3 structural_fitness_agent.py --codebase /path/to/any/java/src

Prerequisites:
    pip install anthropic python-dotenv

    Create architecture-skill-demo/.env (copy from .env.example):
        AZURE_INFERENCE_ENDPOINT=https://<your-project>.services.ai.azure.com
        AZURE_INFERENCE_KEY=<your-azure-api-key>
        AZURE_INFERENCE_MODEL=claude-3-7-sonnet   # optional, this is the default
"""

import hashlib
import os
import re
import sys
import subprocess
import argparse
import datetime
import pathlib

try:
    from anthropic import AnthropicFoundry
except ImportError:
    sys.exit("anthropic package not found.  Run: pip install anthropic")

try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("python-dotenv package not found.  Run: pip install python-dotenv")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENTS_DIR     = pathlib.Path(__file__).parent
REPO_ROOT      = AGENTS_DIR.parent
SKILLS_DIR     = REPO_ROOT / "skills"

GOVERNANCE_DIR = REPO_ROOT / "example-company" / "architecture"
PROJECT_DIR    = REPO_ROOT / "example-company" / "projects" / "order-service"

DEPLOY_PKG     = "com.example.governance"
DEPLOY_CLASS   = "GeneratedFitnessFunctionsTest.java"
MAVEN_ROOT     = PROJECT_DIR
GENERATED_DIR  = PROJECT_DIR / "generated-tests" / "com" / "example" / "governance"

GOVERNANCE_HASH_PREFIX = "// governance-hash: "

# Resolved after .env is loaded in main(); default used here as a fallback
# for any code that runs before main() (tests, imports, etc.)
MAX_COMPILE_ITERATIONS = 3


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def collect_java_files(codebase_path: pathlib.Path) -> list[pathlib.Path]:
    files = sorted(codebase_path.rglob("*.java"))
    if not files:
        sys.exit(f"No .java files found under: {codebase_path}")
    return files


def read_file(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def collect_adrs() -> str:
    adrs = sorted((GOVERNANCE_DIR / "adrs").glob("*.md"))
    if not adrs:
        return "(no ADRs found)"
    return "\n\n---\n\n".join(f"### {f.name}\n\n{read_file(f)}" for f in adrs)


def collect_specs() -> str:
    specs_dir = GOVERNANCE_DIR / "standards"
    docs = (sorted(specs_dir.rglob("*.md"))
            + sorted(specs_dir.rglob("*.yaml"))
            + sorted(specs_dir.rglob("*.json")))
    if not docs:
        return "(no specs found)"
    return "\n\n".join(f"### {f.relative_to(specs_dir)}\n\n{read_file(f)}" for f in docs)


def build_java_context(java_files: list[pathlib.Path], root: pathlib.Path) -> str:
    return "\n\n".join(f"// FILE: {f.relative_to(root)}\n{read_file(f)}" for f in java_files)


def strip_markdown_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:java)?\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Governance-hash staleness helpers
# ---------------------------------------------------------------------------

def compute_governance_hash() -> str:
    """Hash of governance inputs that should trigger test regeneration.

    Covers ADRs and architecture specs only — the source code is not an input
    to test generation. ArchUnit rules are derived from governance decisions,
    not from what the current code happens to look like. Tests run against the
    code on every build; they are regenerated only when the rules change.
    """
    h = hashlib.sha256()

    for adr in sorted((GOVERNANCE_DIR / "adrs").glob("*.md")):
        h.update(adr.name.encode())
        h.update(adr.read_bytes())

    specs_dir = GOVERNANCE_DIR / "standards"
    for spec in sorted(specs_dir.rglob("*")):
        if spec.is_file():
            h.update(str(spec.relative_to(specs_dir)).encode())
            h.update(spec.read_bytes())

    return h.hexdigest()


def extract_governance_hash() -> str | None:
    """Read the governance hash from the first line of the generated test file."""
    deploy_path = GENERATED_DIR / DEPLOY_CLASS
    if not deploy_path.exists():
        return None
    first_line = deploy_path.read_text(encoding="utf-8").split("\n", 1)[0]
    if first_line.startswith(GOVERNANCE_HASH_PREFIX):
        return first_line[len(GOVERNANCE_HASH_PREFIX):].strip()
    return None


def tests_are_stale(governance_hash: str) -> bool:
    """True if the generated tests don't exist or were built from different inputs."""
    return extract_governance_hash() != governance_hash


def ensure_hash_comment(java_code: str, hash_str: str) -> str:
    """Guarantee the governance hash is the very first line of the Java file."""
    header = f"{GOVERNANCE_HASH_PREFIX}{hash_str}"
    lines  = java_code.split("\n")
    if lines and lines[0].startswith(GOVERNANCE_HASH_PREFIX):
        lines = lines[1:]
    return header + "\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 3 helper — compile check
# ---------------------------------------------------------------------------

def compile_check(java_code: str) -> str:
    """Write java_code to the generated-tests location and run mvn test-compile.
    Returns empty string on success, or the compiler error lines on failure."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (GENERATED_DIR / DEPLOY_CLASS).write_text(java_code, encoding="utf-8")

    result = subprocess.run(
        ["mvn", "test-compile", "--batch-mode"],
        cwd=MAVEN_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode == 0:
        return ""

    combined = result.stdout + result.stderr
    error_lines = [
        line for line in combined.splitlines()
        if "[ERROR]" in line or ("error:" in line.lower() and ".java" in line)
    ]
    return "\n".join(error_lines) if error_lines else combined.strip()


# ---------------------------------------------------------------------------
# Phase 4 — Run fitness functions and print results
# ---------------------------------------------------------------------------

def run_fitness_tests() -> None:
    """Run `mvn test` and print a pass/fail summary, mirroring what the API
    agent does with `spectral lint`.  Violations are expected for a governance
    demo — the agent reports them but does not exit with an error code."""

    print(f"\n{'─' * 70}")
    print(f"  PHASE 4 — Run Fitness Functions")
    print(f"{'─' * 70}")

    result = subprocess.run(
        ["mvn", "test", "-Dmaven.test.failure.ignore=true", "--batch-mode", "-q"],
        cwd=MAVEN_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode not in (0, 1):
        print(f"  ✗  mvn exited with code {result.returncode}")
        output = (result.stdout + result.stderr).strip()
        for line in output.splitlines()[:20]:
            print(f"     {line}")
        return

    # Parse the surefire summary line from Maven's batch output
    # e.g. "Tests run: 12, Failures: 3, Errors: 0, Skipped: 0"
    combined = result.stdout + result.stderr
    summary_lines = [l for l in combined.splitlines() if "Tests run:" in l]

    passed = failed = 0
    for line in summary_lines:
        import re
        m = re.search(r"Tests run:\s*(\d+).*?Failures:\s*(\d+).*?Errors:\s*(\d+)", line)
        if m:
            run, failures, errors = int(m.group(1)), int(m.group(2)), int(m.group(3))
            passed += run - failures - errors
            failed += failures + errors

    if failed:
        print(f"  ✓  Tests ran — {failed} violation(s) found, {passed} rule(s) passed"
              f"  (governance report ready)\n")
    else:
        print(f"  ✓  All {passed} fitness function(s) passed — no violations\n")


# ---------------------------------------------------------------------------
# Phase 1 — Codebase Scanner (single-turn streaming)
# ---------------------------------------------------------------------------

def run_scanner(client: AnthropicFoundry, java_files: list[pathlib.Path],
                codebase_root: pathlib.Path, model: str) -> str:

    scanner_skill = read_file(SKILLS_DIR / "codebase-scanner.md")
    java_context  = build_java_context(java_files, codebase_root)

    system = (
        "You are a senior platform architect operating the Codebase Scanner skill. "
        "Follow the skill definition precisely. Report only what you observe in the code. "
        "Do not make recommendations — that is the next skill's job.\n\n"
        f"SKILL DEFINITION:\n{scanner_skill}"
    )
    user = (
        f"Scan the following {len(java_files)} Java source files and produce the "
        "structured codebase summary as defined in the skill.\n\n"
        f"{java_context}"
    )

    print(f"\n{'─' * 70}")
    print(f"  PHASE 1 — Scan  ({len(java_files)} Java files)")
    print(f"{'─' * 70}\n")

    collected: list[str] = []
    with client.messages.stream(
        model=model, max_tokens=8000, system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            collected.append(text)
    print()
    return "".join(collected)


# ---------------------------------------------------------------------------
# Phase 2+3 — Generator + Verify agentic loop
# ---------------------------------------------------------------------------

def run_generator_agent(client: AnthropicFoundry, model: str) -> str:

    generator_skill = read_file(SKILLS_DIR / "archunit-generator.md")
    service_desc    = read_file(PROJECT_DIR / "service-description.md")
    arch_standards  = read_file(GOVERNANCE_DIR / "standards" / "architecture-standards.md")
    adrs            = collect_adrs()
    specs           = collect_specs()

    system = (
        "You are a senior platform architect operating the ArchUnit Generator skill. "
        "Follow the skill definition precisely. Produce only generic, convention-based "
        "ArchUnit rules — no specific class names. Every rule must cite its source ADR "
        "in the because() clause. "
        f"The generated class must be named GeneratedFitnessFunctionsTest in package {DEPLOY_PKG}. "
        "Return only the Java source code — no explanation, no markdown fences.\n\n"
        f"SKILL DEFINITION:\n{generator_skill}"
    )

    initial_user = (
        "Generate the platform ArchUnit fitness functions from the inputs below.\n\n"
        f"{'=' * 60}\nSERVICE DESCRIPTION\n{'=' * 60}\n{service_desc}\n\n"
        f"{'=' * 60}\nARCHITECTURE STANDARDS\n{'=' * 60}\n{arch_standards}\n\n"
        f"{'=' * 60}\nARCHITECTURE DECISION RECORDS\n{'=' * 60}\n{adrs}\n\n"
        f"{'=' * 60}\nSPECS (API style guide, event schemas, etc.)\n{'=' * 60}\n{specs}\n"
    )

    messages: list[dict] = [{"role": "user", "content": initial_user}]
    java_code = ""

    for attempt in range(1, MAX_COMPILE_ITERATIONS + 1):

        # ── Phase 2: Generate ──────────────────────────────────────────────
        print(f"\n{'─' * 70}")
        print(f"  PHASE 2 — Generate  (attempt {attempt}/{MAX_COMPILE_ITERATIONS})")
        print(f"{'─' * 70}\n")

        collected: list[str] = []
        with client.messages.stream(
            model=model, max_tokens=16000, system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                collected.append(text)
        print()

        raw      = "".join(collected)
        java_code = strip_markdown_fences(raw)

        # ── Phase 3: Verify ────────────────────────────────────────────────
        print(f"\n{'─' * 70}")
        print(f"  PHASE 3 — Verify  (attempt {attempt}/{MAX_COMPILE_ITERATIONS})")
        print(f"{'─' * 70}")

        errors = compile_check(java_code)

        if not errors:
            print("  ✓  Compilation successful — tests are ready\n")
            return java_code

        print("  ✗  Compilation errors:\n")
        for line in errors.splitlines():
            print(f"     {line}")
        print()

        if attempt < MAX_COMPILE_ITERATIONS:
            print("  →  Sending errors back to agent for correction...\n")
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    "The generated Java class has compilation errors. "
                    "Fix every error and return the complete corrected Java class. "
                    "Return only the Java source code — no explanation, no markdown fences.\n\n"
                    f"COMPILATION ERRORS:\n{errors}"
                ),
            })

    print(f"  ⚠  Could not achieve clean compilation after {MAX_COMPILE_ITERATIONS} attempts.")
    print("  Last version written — check errors above.\n")
    return java_code


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Structural Fitness Agent")
    parser.add_argument(
        "--codebase",
        type=pathlib.Path,
        help="Path to Java source root (default: <project-dir>/src)",
    )
    parser.add_argument(
        "--governance-dir",
        type=pathlib.Path,
        default=GOVERNANCE_DIR,
        help="Path to EA governance directory containing adrs/ and standards/ "
             "(default: example-company/architecture)",
    )
    parser.add_argument(
        "--project-dir",
        type=pathlib.Path,
        default=PROJECT_DIR,
        help="Path to the Maven project root whose src/ will be scanned "
             "(default: example-company/projects/order-service)",
    )
    parser.add_argument(
        "--refresh-tests", action="store_true",
        help="Force regeneration of the fitness functions even if governance inputs haven't changed",
    )
    args = parser.parse_args()

    # Allow --governance-dir and --project-dir to override module-level constants
    # so all downstream functions (collect_adrs, compile_check, etc.) pick up the
    # correct paths without needing them threaded through every call.
    global GOVERNANCE_DIR, PROJECT_DIR, MAVEN_ROOT, GENERATED_DIR
    GOVERNANCE_DIR = args.governance_dir.resolve()
    PROJECT_DIR    = args.project_dir.resolve()
    MAVEN_ROOT     = PROJECT_DIR
    GENERATED_DIR  = PROJECT_DIR / "generated-tests" / "com" / "example" / "governance"

    codebase_path = (args.codebase or PROJECT_DIR / "src").resolve()
    if not codebase_path.exists():
        sys.exit(f"Codebase path not found: {codebase_path}")

    load_dotenv(REPO_ROOT / ".env")

    global MAX_COMPILE_ITERATIONS
    MAX_COMPILE_ITERATIONS = int(os.environ.get("MAX_COMPILE_ITERATIONS", "3"))

    endpoint = os.environ.get("AZURE_INFERENCE_ENDPOINT", "").rstrip("/")
    api_key  = os.environ.get("AZURE_INFERENCE_KEY")
    model    = os.environ.get("AZURE_INFERENCE_MODEL", "claude-3-7-sonnet")

    java_files = collect_java_files(codebase_path)

    # Governance hash covers only ADRs + specs — source code is not an input
    # to test generation. Tests are regenerated only when governance rules change.
    governance_hash = compute_governance_hash()
    stale = args.refresh_tests or tests_are_stale(governance_hash)

    print("\n" + "=" * 70)
    print("  Structural Fitness Agent")
    print("=" * 70)
    print(f"  Provider  : Azure AI Foundry")
    print(f"  Model     : {model}")
    print(f"  Codebase  : {codebase_path}  ({len(java_files)} files)")
    print(f"  ADRs      : {len(list((GOVERNANCE_DIR / 'adrs').glob('*.md')))}")
    print(f"  Standards : {len(list((GOVERNANCE_DIR / 'standards').rglob('*.*')))}")
    print(f"  Max verify attempts : {MAX_COMPILE_ITERATIONS}")
    tests_status = "regenerate" if args.refresh_tests else ("governance changed — will regenerate" if stale else "current")
    print(f"  Tests     : {tests_status}")
    print("=" * 70)

    if not stale:
        print(f"\n  Governance rules unchanged — committed tests are current.")
        print(f"  Use --refresh-tests to force regeneration.\n")
        return

    # Credentials only required when we are about to call the AI
    missing = [name for name, val in [
        ("AZURE_INFERENCE_ENDPOINT", endpoint or None),
        ("AZURE_INFERENCE_KEY",      api_key),
    ] if not val]
    if missing:
        sys.exit(
            "Missing required environment variables:\n" +
            "\n".join(f"  export {v}='...'" for v in missing)
        )

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    out_dir   = REPO_ROOT / "outputs" / f"live-{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    client = AnthropicFoundry(
        api_key=api_key,
        base_url=f"{endpoint}/anthropic",
    )

    # ── Phase 1: Scan (for human review — output saved to outputs/, not fed to Phase 2)
    scan_output = run_scanner(client, java_files, codebase_path, model)
    scan_path   = out_dir / "codebase-scan.md"
    scan_path.write_text(
        f"<!-- Codebase Scanner output — generated {timestamp} -->\n\n{scan_output}",
        encoding="utf-8",
    )
    print(f"\n  Scan saved : {scan_path.name}  ({scan_path.stat().st_size:,} bytes)")

    # ── Phases 2+3: Generate from governance docs + Verify (compile check)
    java_code = run_generator_agent(client, model)

    # Prepend governance hash — enables staleness detection on the next run
    java_code = ensure_hash_comment(java_code, governance_hash)
    (GENERATED_DIR / DEPLOY_CLASS).write_text(java_code, encoding="utf-8")

    # Save reference copy in outputs/
    (out_dir / DEPLOY_CLASS).write_text(java_code, encoding="utf-8")
    print(f"  Tests saved: {out_dir.name}/{DEPLOY_CLASS}")

    # ── Phase 4: Run the fitness functions and report results
    run_fitness_tests()

    print(f"\n{'=' * 70}")
    print(f"  Agent complete.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
