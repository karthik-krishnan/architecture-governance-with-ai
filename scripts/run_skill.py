#!/usr/bin/env python3
"""
Architecture Governance — Two-Skill Live Demo Pipeline

Step 1: Codebase Scanner skill reads actual Java source files and produces
        a structured architecture scan (package inventory, violations, SDK usage).

Step 2: ArchUnit Generator skill reads the scan output + ADRs + architecture
        standards + service definition and produces generic, runnable ArchUnit
        fitness function tests.

The generated test is written to generated-tests/ at the Maven project root.
Maven is configured to compile and run that directory automatically, so:

    python3 run_skill.py        # generates the tests
    cd .. && mvn test           # compiles and runs everything, including generated tests

Usage:
    python3 run_skill.py                          # scans ../src by default
    python3 run_skill.py --codebase /path/to/src  # scan any Java project

Prerequisites:
    pip install anthropic python-dotenv

    Create architecture-skill-demo/.env (copy from .env.example):
        AZURE_INFERENCE_ENDPOINT=https://<your-project>.services.ai.azure.com
        AZURE_INFERENCE_KEY=<your-azure-api-key>
        AZURE_INFERENCE_MODEL=claude-3-7-sonnet   # optional, this is the default
"""

import os
import re
import sys
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

SCRIPTS_DIR    = pathlib.Path(__file__).parent
REPO_ROOT      = SCRIPTS_DIR.parent
SKILLS_DIR     = REPO_ROOT / "skills"
GOVERNANCE_DIR = REPO_ROOT / "example-company" / "architecture"
PROJECT_DIR    = REPO_ROOT / "example-company" / "projects" / "example-service"
DEPLOY_PKG     = "com.example.governance"
GENERATED_DIR  = PROJECT_DIR / "generated-tests" / "com" / "example" / "governance"
DEPLOY_CLASS   = "GeneratedFitnessFunctionsTest.java"


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def collect_java_files(codebase_path: pathlib.Path) -> list[pathlib.Path]:
    files = sorted(codebase_path.rglob("*.java"))
    if not files:
        sys.exit(f"No .java files found under: {codebase_path}")
    return files


def read_file(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def collect_adrs() -> str:
    adr_dir = GOVERNANCE_DIR / "adrs"
    adrs = sorted(adr_dir.glob("*.md"))
    if not adrs:
        return "(no ADRs found)"
    parts = []
    for adr in adrs:
        parts.append(f"### {adr.name}\n\n{read_file(adr)}")
    return "\n\n---\n\n".join(parts)


def collect_specs() -> str:
    specs_dir = GOVERNANCE_DIR / "standards"
    docs = sorted(specs_dir.rglob("*.md")) + sorted(specs_dir.rglob("*.yaml")) + sorted(specs_dir.rglob("*.json"))
    if not docs:
        return "(no specs found)"
    parts = []
    for doc in docs:
        relative = doc.relative_to(specs_dir)
        parts.append(f"### {relative}\n\n{read_file(doc)}")
    return "\n\n".join(parts)


def build_java_context(java_files: list[pathlib.Path], codebase_root: pathlib.Path) -> str:
    parts = []
    for f in java_files:
        relative = f.relative_to(codebase_root)
        parts.append(f"// FILE: {relative}\n{read_file(f)}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Azure AI Foundry (AnthropicFoundry) streaming call — returns full text
# ---------------------------------------------------------------------------

def call_claude(client: AnthropicFoundry, system: str, user: str, label: str,
                model: str) -> str:
    print(f"\n{'─' * 70}")
    print(f"  {label}")
    print(f"{'─' * 70}\n")

    collected: list[str] = []

    with client.messages.stream(
        model=model,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            collected.append(text)

    print()
    return "".join(collected)


# ---------------------------------------------------------------------------
# Step 1: Codebase Scanner
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

    return call_claude(client, system, user, f"STEP 1 — Codebase Scanner  ({len(java_files)} files)", model)


# ---------------------------------------------------------------------------
# Step 2: ArchUnit Generator
# ---------------------------------------------------------------------------

def run_generator(client: AnthropicFoundry, scan_output: str, model: str) -> str:

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
        f"The generated class must be named GeneratedFitnessFunctionsTest in package {DEPLOY_PKG}.\n\n"
        f"SKILL DEFINITION:\n{generator_skill}"
    )

    user = (
        "Generate the platform ArchUnit fitness functions from the inputs below.\n\n"
        f"{'=' * 60}\nSERVICE DESCRIPTION\n{'=' * 60}\n{service_desc}\n\n"
        f"{'=' * 60}\nARCHITECTURE STANDARDS\n{'=' * 60}\n{arch_standards}\n\n"
        f"{'=' * 60}\nARCHITECTURE DECISION RECORDS\n{'=' * 60}\n{adrs}\n\n"
        f"{'=' * 60}\nSPECS (API style guide, event schemas, etc.)\n{'=' * 60}\n{specs}\n\n"
        f"{'=' * 60}\nCODEBASE SCAN (from Scanner skill)\n{'=' * 60}\n{scan_output}\n"
    )

    return call_claude(client, system, user, "STEP 2 — ArchUnit Generator", model)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_markdown_fences(text: str) -> str:
    """Remove ```java ... ``` fences if the model wrapped its output."""
    text = text.strip()
    text = re.sub(r"^```(?:java)?\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Architecture governance demo pipeline")
    parser.add_argument(
        "--codebase",
        type=pathlib.Path,
        default=PROJECT_DIR / "src",
        help="Path to Java source root (default: ../src)"
    )
    args = parser.parse_args()

    codebase_path = args.codebase.resolve()
    if not codebase_path.exists():
        sys.exit(f"Codebase path not found: {codebase_path}")

    load_dotenv(REPO_ROOT / ".env")

    endpoint = os.environ.get("AZURE_INFERENCE_ENDPOINT", "").rstrip("/")
    api_key  = os.environ.get("AZURE_INFERENCE_KEY")
    model    = os.environ.get("AZURE_INFERENCE_MODEL", "claude-3-7-sonnet")

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

    java_files = collect_java_files(codebase_path)

    print("\n" + "=" * 70)
    print("  Architecture Governance — Live Demo Pipeline")
    print("=" * 70)
    print(f"  Provider  : Azure AI Foundry")
    print(f"  Model     : {model}")
    print(f"  Endpoint  : {endpoint}")
    print(f"  Codebase  : {codebase_path}")
    print(f"  Java files: {len(java_files)}")
    print(f"  ADRs      : {len(list((GOVERNANCE_DIR / 'adrs').glob('*.md')))}")
    print(f"  Standards : {len(list((GOVERNANCE_DIR / 'standards').rglob('*.*')))}")
    print("=" * 70)

    client = AnthropicFoundry(
        api_key=api_key,
        base_url=f"{endpoint}/anthropic",
    )

    # ── Step 1: Scan ────────────────────────────────────────────────────────
    scan_output = run_scanner(client, java_files, codebase_path, model)

    scan_path = out_dir / "codebase-scan.md"
    scan_path.write_text(
        f"<!-- Codebase Scanner output — generated {timestamp} -->\n\n{scan_output}",
        encoding="utf-8"
    )
    print(f"\n  Scan saved : {scan_path.name}  ({scan_path.stat().st_size:,} bytes)")

    # ── Step 2: Generate ────────────────────────────────────────────────────
    archunit_output = run_generator(client, scan_output, model)
    clean_java      = strip_markdown_fences(archunit_output)

    # Save a copy in outputs/ for reference
    (out_dir / DEPLOY_CLASS).write_text(clean_java, encoding="utf-8")

    # Write to generated-tests/ so mvn test picks it up automatically
    generated_path = GENERATED_DIR / DEPLOY_CLASS
    generated_path.write_text(clean_java, encoding="utf-8")

    print(f"  Tests written to: generated-tests/.../{DEPLOY_CLASS}")
    print(f"\n{'=' * 70}")
    print(f"  Done.")
    print(f"{'=' * 70}")
    print(f"\n  Now run:")
    print(f"    cd .. && mvn test surefire-report:report-only -Dmaven.test.failure.ignore=true")
    print(f"    open target/site/surefire-report.html\n")


if __name__ == "__main__":
    main()
