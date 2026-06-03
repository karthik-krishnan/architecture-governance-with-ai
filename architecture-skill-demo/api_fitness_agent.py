#!/usr/bin/env python3
"""
API & Integration Fitness Agent
================================
Scans a service's source code and produces two governance artifacts:
  1. openapi.yaml          — OpenAPI 3.1 spec generated from what the code actually exposes
  2. spectral-ruleset.yaml — Spectral rules that codify the platform API style guide

Then lints the spec against the ruleset and feeds failures back to the model
for self-correction, up to MAX_LINT_ITERATIONS times.

Usage:
    python3 api_fitness_agent.py
    python3 api_fitness_agent.py --codebase /path/to/any/src

Prerequisites:
    pip install anthropic python-dotenv openapi-spec-validator pyyaml
    npm install -g @stoplight/spectral-cli
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
    sys.exit("python-dotenv not found.  Run: pip install python-dotenv")

try:
    import yaml as pyyaml
except ImportError:
    sys.exit("pyyaml not found.  Run: pip install pyyaml")

try:
    from openapi_spec_validator import validate as validate_openapi_spec
    from openapi_spec_validator.validation.exceptions import OpenAPIValidationError
except ImportError:
    sys.exit("openapi-spec-validator not found.  Run: pip install openapi-spec-validator")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILL_DIR     = pathlib.Path(__file__).parent
INPUTS_DIR    = SKILL_DIR / "inputs"
SKILLS_DIR    = SKILL_DIR / "skills"
MAVEN_ROOT    = SKILL_DIR.parent
GENERATED_DIR = MAVEN_ROOT / "generated-specs"
OPENAPI_FILE  = GENERATED_DIR / "openapi.yaml"
RULESET_FILE  = INPUTS_DIR / "spectral-ruleset.yaml"   # committed; auto-regenerates when style guide changes
JUNIT_FILE    = GENERATED_DIR / "spectral-junit.xml"

STYLE_GUIDE_PATH = INPUTS_DIR / "specs" / "api-style-guide.md"
SHA_PREFIX       = "# style-guide-sha256: "

MAX_LINT_ITERATIONS = 3


# ---------------------------------------------------------------------------
# Prerequisites check
# ---------------------------------------------------------------------------

def check_spectral() -> None:
    result = subprocess.run(
        ["spectral", "--version"], capture_output=True, text=True
    )
    if result.returncode != 0:
        sys.exit(
            "spectral CLI not found.\n"
            "Install it with:  npm install -g @stoplight/spectral-cli"
        )


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def read_file(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def collect_adrs() -> str:
    adrs = sorted((INPUTS_DIR / "adrs").glob("*.md"))
    if not adrs:
        return "(no ADRs found)"
    return "\n\n---\n\n".join(f"### {f.name}\n\n{read_file(f)}" for f in adrs)


def collect_source_files(codebase_path: pathlib.Path) -> list[pathlib.Path]:
    """Collect source files across common languages."""
    files = []
    for ext in ["*.java", "*.py", "*.ts", "*.js", "*.go", "*.rb"]:
        files.extend(sorted(codebase_path.rglob(ext)))
    if not files:
        sys.exit(f"No source files found under: {codebase_path}")
    return files


def build_source_context(files: list[pathlib.Path], root: pathlib.Path) -> str:
    return "\n\n".join(
        f"// FILE: {f.relative_to(root)}\n{read_file(f)}"
        for f in files
    )


def strip_yaml_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:yaml)?\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# SHA-256 staleness helpers
# ---------------------------------------------------------------------------

def compute_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_ruleset_sha256(ruleset_path: pathlib.Path) -> str | None:
    """Return the SHA256 embedded in the first line of the ruleset, or None."""
    if not ruleset_path.exists():
        return None
    first_line = ruleset_path.read_text(encoding="utf-8").split("\n", 1)[0]
    m = re.match(r"#\s*style-guide-sha256:\s*([0-9a-f]{64})", first_line)
    return m.group(1) if m else None


def ruleset_is_stale() -> bool:
    """True if the ruleset doesn't exist or was built from a different style guide."""
    current_sha   = compute_sha256(STYLE_GUIDE_PATH)
    embedded_sha  = extract_ruleset_sha256(RULESET_FILE)
    return current_sha != embedded_sha


def ensure_sha_comment(ruleset_yaml: str, sha: str) -> str:
    """Guarantee the SHA comment is the very first line of the ruleset YAML."""
    header = f"{SHA_PREFIX}{sha}"
    lines = ruleset_yaml.split("\n")
    # Strip any existing (possibly stale) sha comment
    if lines and re.match(r"#\s*style-guide-sha256:", lines[0]):
        lines = lines[1:]
    return header + "\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_openapi(yaml_text: str) -> str:
    """Returns empty string on success, error message on failure."""
    try:
        spec = pyyaml.safe_load(yaml_text)
    except pyyaml.YAMLError as e:
        return f"YAML parse error: {e}"
    try:
        validate_openapi_spec(spec)
        return ""
    except OpenAPIValidationError as e:
        return str(e)
    except Exception as e:
        return str(e)


def spectral_lint(openapi_path: pathlib.Path,
                  ruleset_path: pathlib.Path) -> tuple[int, str, str]:
    """Run spectral lint.

    Returns (returncode, spectral_error, junit_xml).

    Spectral exit codes:
      0 — lint ran, no violations
      1 — lint ran, violations found  ← expected and desired for governance demos
      2+ — Spectral runtime error (invalid ruleset YAML, unrecognised function, etc.)

    spectral_error is non-empty only when returncode >= 2 (i.e. Spectral failed to
    run the ruleset).  Violations (exit 1) are NOT errors — they are the point.
    """
    text_result = subprocess.run(
        ["spectral", "lint", str(openapi_path),
         "--ruleset", str(ruleset_path), "--format", "text"],
        capture_output=True, text=True, timeout=60,
    )
    rc = text_result.returncode
    # Only surface text output as "errors" when Spectral itself failed (rc >= 2).
    # Violations (rc == 1) are expected — don't feed them to the correction loop.
    spectral_error = (text_result.stdout + text_result.stderr) if rc >= 2 else ""

    junit_result = subprocess.run(
        ["spectral", "lint", str(openapi_path),
         "--ruleset", str(ruleset_path), "--format", "junit"],
        capture_output=True, text=True, timeout=60,
    )
    junit_xml = junit_result.stdout

    return rc, spectral_error, junit_xml


# ---------------------------------------------------------------------------
# Phase 1 — Scan
# ---------------------------------------------------------------------------

def run_scanner(client: AnthropicFoundry, source_files: list[pathlib.Path],
                source_root: pathlib.Path, model: str) -> str:

    scanner_skill  = read_file(SKILLS_DIR / "api-scanner.md")
    service_desc   = read_file(INPUTS_DIR / "service-description.md")
    source_context = build_source_context(source_files, source_root)

    system = (
        "You are a senior platform architect operating the API Scanner skill. "
        "Follow the skill definition precisely. Report only what you observe in the code. "
        "Do not make recommendations.\n\n"
        f"SKILL DEFINITION:\n{scanner_skill}"
    )
    user = (
        f"Scan the following {len(source_files)} source files and produce the API inventory "
        "as defined in the skill.\n\n"
        f"SERVICE DESCRIPTION:\n{service_desc}\n\n"
        f"{source_context}"
    )

    print(f"\n{'─' * 70}")
    print(f"  PHASE 1 — API Scan  ({len(source_files)} files)")
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
# Phase 2 — Generate OpenAPI spec (with openapi-spec-validator retry loop)
# ---------------------------------------------------------------------------

def run_spec_generator(client: AnthropicFoundry, scan_output: str, model: str) -> str:

    generator_skill = read_file(SKILLS_DIR / "openapi-generator.md")
    service_desc    = read_file(INPUTS_DIR / "service-description.md")
    adrs            = collect_adrs()

    system = (
        "You are a senior platform architect operating the OpenAPI Generator skill. "
        "Follow the skill definition precisely. "
        "Return only the OpenAPI YAML — no explanation, no markdown fences.\n\n"
        f"SKILL DEFINITION:\n{generator_skill}"
    )
    initial_user = (
        "Generate the OpenAPI 3.1 spec from the inputs below.\n\n"
        f"SERVICE DESCRIPTION:\n{service_desc}\n\n"
        f"ADRs:\n{adrs}\n\n"
        f"API SCAN:\n{scan_output}\n"
    )

    messages: list[dict] = [{"role": "user", "content": initial_user}]
    yaml_text = ""

    for attempt in range(1, MAX_LINT_ITERATIONS + 1):

        print(f"\n{'─' * 70}")
        print(f"  PHASE 2 — Generate OpenAPI Spec  (attempt {attempt}/{MAX_LINT_ITERATIONS})")
        print(f"{'─' * 70}\n")

        collected: list[str] = []
        with client.messages.stream(
            model=model, max_tokens=8000, system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                collected.append(text)
        print()

        raw       = "".join(collected)
        yaml_text = strip_yaml_fences(raw)

        print(f"  Validating OpenAPI 3.1 syntax...", end="", flush=True)
        errors = validate_openapi(yaml_text)

        if not errors:
            print("  ✓\n")
            return yaml_text

        print(f"  ✗\n")
        for line in errors.splitlines()[:10]:
            print(f"     {line}")
        print()

        if attempt < MAX_LINT_ITERATIONS:
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    "The generated OpenAPI spec has validation errors. "
                    "Fix every error and return the complete corrected YAML. "
                    "Return only the YAML — no explanation, no markdown fences.\n\n"
                    f"ERRORS:\n{errors}"
                ),
            })

    print(f"  ⚠  Could not produce valid spec after {MAX_LINT_ITERATIONS} attempts.")
    return yaml_text


# ---------------------------------------------------------------------------
# Phase 3 — Generate Spectral ruleset
# ---------------------------------------------------------------------------

def run_ruleset_generator(client: AnthropicFoundry, model: str) -> str:

    generator_skill = read_file(SKILLS_DIR / "spectral-ruleset-generator.md")
    api_style_guide = read_file(STYLE_GUIDE_PATH)

    system = (
        "You are a senior platform architect operating the Spectral Ruleset Generator skill. "
        "Follow the skill definition precisely. "
        "Return only the Spectral YAML ruleset — no explanation, no markdown fences.\n\n"
        f"SKILL DEFINITION:\n{generator_skill}"
    )
    user = (
        "Generate the Spectral ruleset from the API style guide below.\n\n"
        f"API STYLE GUIDE:\n{api_style_guide}\n"
    )

    print(f"\n{'─' * 70}")
    print(f"  PHASE 3 — Generate Spectral Ruleset")
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

    ruleset_yaml = strip_yaml_fences("".join(collected))
    sha = compute_sha256(STYLE_GUIDE_PATH)
    return ensure_sha_comment(ruleset_yaml, sha)


# ---------------------------------------------------------------------------
# Phase 4 — Verify: spectral lint loop
# ---------------------------------------------------------------------------

def run_spectral_lint_phase(spec_yaml: str) -> None:
    """
    Phase 4 — lint the generated OpenAPI spec against the committed ruleset.

    The ruleset (inputs/spectral-ruleset.yaml) is a committed governance artifact.
    This phase is read-only with respect to the ruleset — it never modifies it.
    If Spectral reports violations, that is the expected, desired result for a
    governance demo.  The JUnit is saved and the HTML report shows the failures.
    """
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'─' * 70}")
    print(f"  PHASE 4 — Spectral Lint")
    print(f"{'─' * 70}")

    OPENAPI_FILE.write_text(spec_yaml, encoding="utf-8")

    rc, spectral_error, junit_xml = spectral_lint(OPENAPI_FILE, RULESET_FILE)

    if junit_xml:
        JUNIT_FILE.write_text(junit_xml, encoding="utf-8")

    if rc == 0:
        print("  ✓  No violations — spec is fully compliant\n")
    elif rc == 1:
        print("  ✓  Spectral lint ran — violations captured (governance report ready)\n")
    else:
        # Spectral itself failed (invalid ruleset YAML, unknown function, bad JSONPath).
        # The ruleset must be fixed in Phase 3 (generation), not here.
        print("  ✗  Spectral runtime error — the committed ruleset may be invalid:\n")
        for line in spectral_error.splitlines()[:20]:
            print(f"     {line}")
        print()
        print("  ⚠  Re-generate the ruleset with: python3 api_fitness_agent.py --refresh-ruleset\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="API & Integration Fitness Agent")
    parser.add_argument(
        "--codebase", type=pathlib.Path,
        default=SKILL_DIR.parent / "src",
        help="Path to source root (default: ../src)",
    )
    parser.add_argument(
        "--refresh-ruleset", action="store_true",
        help="Force regeneration of the Spectral ruleset even if the style guide hasn't changed",
    )
    args = parser.parse_args()

    codebase_path = args.codebase.resolve()
    if not codebase_path.exists():
        sys.exit(f"Codebase path not found: {codebase_path}")

    load_dotenv(SKILL_DIR / ".env")

    global MAX_LINT_ITERATIONS
    MAX_LINT_ITERATIONS = int(os.environ.get("MAX_LINT_ITERATIONS", "3"))

    check_spectral()

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
    out_dir   = SKILL_DIR / "outputs" / f"api-{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)

    source_files = collect_source_files(codebase_path)

    # Determine whether Phase 3 (ruleset generation) is needed
    stale = args.refresh_ruleset or ruleset_is_stale()

    print("\n" + "=" * 70)
    print("  API & Integration Fitness Agent")
    print("=" * 70)
    print(f"  Provider  : Azure AI Foundry")
    print(f"  Model     : {model}")
    print(f"  Codebase  : {codebase_path}  ({len(source_files)} files)")
    ruleset_status = "regenerate" if args.refresh_ruleset else ("stale — will regenerate" if stale else "up-to-date")
    print(f"  Ruleset   : {ruleset_status}")
    print("=" * 70)

    client = AnthropicFoundry(
        api_key=api_key,
        base_url=f"{endpoint}/anthropic",
    )

    # Phase 1: Scan
    scan_output = run_scanner(client, source_files, codebase_path, model)
    scan_path   = out_dir / "api-scan.md"
    scan_path.write_text(
        f"<!-- API Scanner output — generated {timestamp} -->\n\n{scan_output}",
        encoding="utf-8",
    )
    print(f"\n  Scan saved : {scan_path.name}  ({scan_path.stat().st_size:,} bytes)")

    # Phase 2: Generate spec
    spec_yaml = run_spec_generator(client, scan_output, model)

    # Phase 3: Generate ruleset (skipped when style guide is unchanged)
    if stale:
        ruleset_yaml = run_ruleset_generator(client, model)
        RULESET_FILE.write_text(ruleset_yaml, encoding="utf-8")
        print(f"  Ruleset saved : {RULESET_FILE.relative_to(SKILL_DIR)}")

    else:
        print(f"\n{'─' * 70}")
        print(f"  PHASE 3 — Spectral Ruleset  (skipped — style guide unchanged)")
        print(f"{'─' * 70}")

    # Phase 4: Spectral lint — read-only against the committed ruleset
    run_spectral_lint_phase(spec_yaml)

    # Save reference copy of the spec in outputs/
    (out_dir / "openapi.yaml").write_text(spec_yaml, encoding="utf-8")

    print(f"  Spec saved : {out_dir.name}/openapi.yaml")

    print(f"\n{'=' * 70}")
    print(f"  Agent complete.")
    print(f"{'=' * 70}")
    print(f"\n  View results:")
    print(f"    python3 run_tests.py\n")


if __name__ == "__main__":
    main()
