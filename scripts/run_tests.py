#!/usr/bin/env python3
"""
Architecture Governance — Unified Dashboard
=============================================
Runs both governance agents and renders a combined HTML report.

Each agent is a complete governance check for its domain:
  structural_fitness_agent  — generates ArchUnit tests, compile-verifies, then runs them
  api_fitness_agent         — generates OpenAPI spec + Spectral ruleset, then lints

This script orchestrates both and produces a single HTML report.

Usage:
    python3 run_tests.py                # run both agents, open unified report
    python3 run_tests.py --structural   # structural agent only
    python3 run_tests.py --api          # API agent only
    python3 run_tests.py --no-run       # regenerate report from last artifacts

Caching:
    Structural tests regenerate only when ADRs or arch specs change.
    Spectral ruleset regenerates only when the API style guide changes.
    Use --refresh-tests / --refresh-ruleset to force regeneration.
"""

import argparse
import datetime
import pathlib
import re
import subprocess
import sys
import webbrowser
import xml.etree.ElementTree as ET

SCRIPTS_DIR     = pathlib.Path(__file__).parent
REPO_ROOT       = SCRIPTS_DIR.parent
GOVERNANCE_DIR  = REPO_ROOT / "example-company" / "architecture"
PROJECT_DIR     = REPO_ROOT / "example-company" / "projects" / "example-service"
REPORTS_DIR     = PROJECT_DIR / "target" / "surefire-reports"
GENERATED_SPECS = PROJECT_DIR / "generated-specs"
OUTPUT_DIR      = REPO_ROOT / "outputs"
OUTPUT_HTML     = OUTPUT_DIR / "governance-report.html"

RULESET_FILE    = GOVERNANCE_DIR / "spectral-ruleset.yaml"
JUNIT_FILE      = GENERATED_SPECS / "spectral-junit.xml"

MAX_VIOLATIONS_SHOWN = 5

CLASS_LABELS = {
    "ArchitectureFitnessFunctionsTest": ("Hand-authored Fitness Functions",    "✍"),
    "GeneratedFitnessFunctionsTest":    ("AI-generated Fitness Functions",     "✦"),
    "spectral":                         ("AI-generated API Fitness Functions", "⬡"),
}


# ---------------------------------------------------------------------------
# Run agents / tests
# ---------------------------------------------------------------------------

def run_structural(governance_dir: pathlib.Path, project_dir: pathlib.Path) -> None:
    print("\nRunning Structural Fitness Agent...")
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "agents" / "structural_fitness_agent.py"),
            "--governance-dir", str(governance_dir),
            "--project-dir",    str(project_dir),
        ],
        cwd=REPO_ROOT / "agents",
    )


def run_api(governance_dir: pathlib.Path, project_dir: pathlib.Path) -> None:
    print("\nRunning API & Integration Fitness Agent...")
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "agents" / "api_fitness_agent.py"),
            "--governance-dir", str(governance_dir),
            "--project-dir",    str(project_dir),
        ],
        cwd=REPO_ROOT / "agents",
    )




# ---------------------------------------------------------------------------
# Parse Surefire XML
# ---------------------------------------------------------------------------

def short_name(classname: str) -> str:
    return classname.split(".")[-1]


def parse_violations(cdata: str) -> list[str]:
    violations = []
    for raw in cdata.strip().splitlines():
        line = raw.strip()
        if not line:
            continue
        if (line.startswith("at ") or line.startswith("java.lang.")
                or line.startswith("Caused by:") or line.startswith("... ")):
            continue
        if line.startswith(("Method ", "Field ", "Constructor ", "Class ")):
            for part in line.split(" and "):
                part = part.strip()
                if part:
                    violations.append(part)
        else:
            violations.append(line)
    return violations


def load_surefire_report(xml_path: pathlib.Path) -> dict:
    root  = ET.parse(xml_path).getroot()
    suite = short_name(root.attrib.get("name", xml_path.stem))
    total = int(root.attrib.get("tests",    0))
    fails = int(root.attrib.get("failures", 0)) + int(root.attrib.get("errors", 0))

    rules = []
    for tc in root.findall("testcase"):
        f = tc.find("failure")
        rules.append({
            "name":       tc.attrib.get("name", "unknown"),
            "passed":     f is None,
            "violations": parse_violations(f.text or "") if f is not None else [],
        })

    return {"suite": suite, "total": total, "passed": total - fails,
            "failed": fails, "rules": rules}


# ---------------------------------------------------------------------------
# Parse Spectral JUnit XML
# ---------------------------------------------------------------------------

def load_ruleset_rule_ids() -> list[str]:
    """Return all rule IDs defined in the committed Spectral ruleset, in order.

    Uses a simple regex (no extra dependency) — rule IDs sit at exactly two
    spaces of indent as YAML mapping keys directly under `rules:`.
    """
    if not RULESET_FILE.exists():
        return []
    content = RULESET_FILE.read_text(encoding="utf-8")
    # Match lines like "  qsr-some-rule-name:" (exactly 2-space indent, kebab-case id)
    return re.findall(r"^  ([a-z][a-z0-9-]+):\s*$", content, re.MULTILINE)


def load_spectral_report(xml_path: pathlib.Path) -> dict:
    """Parse spectral --format junit output.

    Spectral emits one <testcase> per *violation* — passing rules are absent.
    We augment the result by reading the committed ruleset to discover all rule
    IDs, then synthesising PASS entries for rules with no violations.

    Spectral sometimes emits non-XML text (warnings, notices) before or after
    the XML document. We extract just the XML portion before parsing.
    """
    content = xml_path.read_text(encoding="utf-8")

    # Find the start of the XML document
    xml_start = content.find("<?xml")
    if xml_start == -1:
        xml_start = content.find("<testsuites")
    if xml_start == -1:
        xml_start = content.find("<testsuite")
    if xml_start > 0:
        content = content[xml_start:]

    # Truncate at the end of the outermost closing tag
    for closing in ("</testsuites>", "</testsuite>"):
        idx = content.rfind(closing)
        if idx != -1:
            content = content[:idx + len(closing)]
            break

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return {"suite": "spectral", "total": 0, "passed": 0, "failed": 0, "rules": []}

    suite_el = root if root.tag == "testsuite" else root.find("testsuite")
    if suite_el is None:
        return {"suite": "spectral", "total": 0, "passed": 0, "failed": 0, "rules": []}

    # Collect violations grouped by rule ID
    rule_violations: dict[str, list[str]] = {}
    for tc in suite_el.findall("testcase"):
        rule_id  = tc.attrib.get("name", "unknown")
        location = tc.attrib.get("classname", "")
        f = tc.find("failure")
        if f is not None:
            msg    = f.attrib.get("message", "") or (f.text or "").strip().splitlines()[0]
            detail = f"{location}: {msg}" if location else msg
            rule_violations.setdefault(rule_id, []).append(detail)

    # Read all rule IDs from the committed ruleset so we can show passing rules too
    all_rule_ids = load_ruleset_rule_ids()

    if all_rule_ids:
        # Failing rules first (prominent), then passing rules
        rules: list[dict] = [
            {"name": rid, "passed": False, "violations": viols}
            for rid, viols in rule_violations.items()
        ]
        failing_ids = set(rule_violations.keys())
        rules += [
            {"name": rid, "passed": True, "violations": []}
            for rid in all_rule_ids
            if rid not in failing_ids
        ]
        total  = len(all_rule_ids)
        failed = len(failing_ids)
        passed = total - failed
    else:
        # Ruleset not available — fall back to violations-only
        rules  = [{"name": rid, "passed": False, "violations": v}
                  for rid, v in rule_violations.items()]
        failed = len(rules)
        total  = failed
        passed = 0

    return {"suite": "spectral", "total": total, "passed": passed,
            "failed": failed, "rules": rules}


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f6fa;
    color: #1a1a2e;
    font-size: 14px;
    line-height: 1.5;
}

header {
    background: #1a1a2e;
    color: #fff;
    padding: 28px 40px 24px;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
}
header h1 { font-size: 22px; font-weight: 600; letter-spacing: -0.3px; }
header .meta { font-size: 12px; color: #8892b0; margin-top: 4px; }
header .timestamp { font-size: 12px; color: #8892b0; text-align: right; }

.summary-bar {
    background: #fff;
    border-bottom: 1px solid #e2e8f0;
    padding: 20px 40px;
    display: flex;
    gap: 32px;
    align-items: center;
}
.stat { text-align: center; }
.stat .num { font-size: 32px; font-weight: 700; line-height: 1; }
.stat .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px;
               color: #64748b; margin-top: 4px; }
.stat.pass .num { color: #16a34a; }
.stat.fail .num { color: #dc2626; }
.stat.total .num { color: #1a1a2e; }
.divider { width: 1px; height: 48px; background: #e2e8f0; }
.verdict {
    margin-left: auto;
    padding: 8px 20px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 13px;
    letter-spacing: 0.3px;
}
.verdict.clean { background: #dcfce7; color: #15803d; }
.verdict.violations { background: #fee2e2; color: #b91c1c; }

main { padding: 32px 40px; display: flex; flex-direction: column; gap: 32px; }

.section-card {
    background: #fff;
    border-radius: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
    overflow: hidden;
}

.section-header {
    padding: 18px 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid #f1f5f9;
}
.section-icon { font-size: 20px; }
.section-title { font-size: 16px; font-weight: 600; }
.section-counts { margin-left: auto; display: flex; gap: 10px; font-size: 12px; }
.badge {
    padding: 3px 10px; border-radius: 20px; font-weight: 600; font-size: 12px;
}
.badge.pass { background: #dcfce7; color: #15803d; }
.badge.fail { background: #fee2e2; color: #b91c1c; }
.badge.neutral { background: #f1f5f9; color: #475569; }

.rules-list { padding: 8px 0; }

.rule-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 10px 24px;
    border-bottom: 1px solid #f8fafc;
}
.rule-row:last-child { border-bottom: none; }
.rule-icon { font-size: 15px; margin-top: 1px; flex-shrink: 0; }
.rule-icon.pass { color: #16a34a; }
.rule-icon.fail { color: #dc2626; }
.rule-name { font-weight: 500; font-size: 13px; }
.rule-name.pass { color: #374151; }
.rule-name.fail { color: #111827; }

details { width: 100%; }
details > summary {
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: flex-start;
    gap: 0;
}
details > summary::-webkit-details-marker { display: none; }
details > summary .rule-name::after {
    content: " ▸";
    color: #94a3b8;
    font-size: 11px;
}
details[open] > summary .rule-name::after { content: " ▾"; }

.violations-block {
    margin: 8px 0 4px 28px;
    padding: 12px 16px;
    background: #fafafa;
    border-left: 3px solid #fca5a5;
    border-radius: 0 6px 6px 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.violation-summary {
    font-size: 12px;
    color: #92400e;
    background: #fef3c7;
    padding: 6px 10px;
    border-radius: 4px;
    margin-bottom: 4px;
    line-height: 1.4;
}

.violation-item {
    font-size: 12px;
    color: #374151;
    font-family: "SF Mono", "Fira Code", monospace;
    word-break: break-all;
    padding: 3px 0;
    border-bottom: 1px solid #f0f0f0;
    line-height: 1.5;
}
.violation-item:last-child { border-bottom: none; }
.violation-item .location {
    color: #6b7280;
    font-size: 11px;
}

.more-hint {
    font-size: 11px;
    color: #94a3b8;
    font-style: italic;
    margin-top: 2px;
}

.dim-block {
    font-size: 12px;
    color: #94a3b8;
    font-family: "SF Mono", "Fira Code", monospace;
    padding: 4px 0;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-all;
}

footer {
    text-align: center;
    padding: 24px;
    font-size: 11px;
    color: #94a3b8;
}
"""


def display_name(rule_name: str) -> str:
    """Convert snake_case or kebab-case rule names to readable display text."""
    name  = rule_name.replace("-", "_")
    parts = name.split("_")

    # ArchUnit rules: FF_NNN_description
    if parts and parts[0].upper() == "FF":
        prefix = [p for p in parts[:2]
                  if p.upper() == "FF" or p.isdigit() or (p.isupper() and len(p) <= 4)]
        desc_parts = parts[len(prefix):]
        desc_text  = " ".join(p.lower() for p in desc_parts)
        if desc_text:
            desc_text = desc_text[0].upper() + desc_text[1:]
        return (" ".join(prefix) + " " + desc_text).strip()

    # Spectral rules: qsr-some-rule-name → drop qsr prefix, title-case
    if parts and parts[0].lower() == "qsr":
        parts = parts[1:]
    text = " ".join(p.lower() for p in parts)
    return (text[0].upper() + text[1:]) if text else rule_name


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def format_violation_item(line: str) -> str:
    if " in (" in line and line.endswith(")"):
        body, loc = line.rsplit(" in (", 1)
        loc = loc.rstrip(")")
        return (f'<div class="violation-item">{esc(body)}'
                f' <span class="location">({esc(loc)})</span></div>')
    return f'<div class="violation-item">{esc(line)}</div>'


def render_rule(rule: dict) -> str:
    name   = rule["name"]
    passed = rule["passed"]
    viols  = rule["violations"]

    icon_cls  = "pass" if passed else "fail"
    icon_char = "✓" if passed else "✗"
    name_cls  = "pass" if passed else "fail"

    if passed:
        return f"""
        <div class="rule-row">
            <span class="rule-icon {icon_cls}">{icon_char}</span>
            <span class="rule-name {name_cls}">{esc(display_name(name))}</span>
        </div>"""

    # ArchUnit: separate summary line from detail lines.
    # The raw summary is the verbose rule definition — not useful to display since
    # the rule name is already shown as the header. Extract just the count instead.
    summary_lines = [l for l in viols if "was violated" in l or "Architecture Violation" in l]
    detail_lines  = [l for l in viols if l not in summary_lines]

    summary_html = ""
    if summary_lines:
        # Extract "N times" from the summary, e.g. "was violated (3 times):"
        count_match = re.search(r"\((\d+)\s+times?\)", " ".join(summary_lines))
        if count_match:
            count = int(count_match.group(1))
            label = f"{count} violation{'s' if count != 1 else ''} found"
        else:
            label = "violations found"
        summary_html = f'<div class="violation-summary">{esc(label)}</div>'

    violation_items = [l for l in detail_lines
                       if l.startswith(("Method ", "Field ", "Constructor ", "Class "))]
    other_lines     = [l for l in detail_lines
                       if not l.startswith(("Method ", "Field ", "Constructor ", "Class "))]

    items_html = ""
    shown = 0
    for line in violation_items:
        if shown >= MAX_VIOLATIONS_SHOWN:
            break
        items_html += format_violation_item(line)
        shown += 1

    remaining = len(violation_items) - shown
    if remaining > 0:
        items_html += (f'<div class="more-hint">… and {remaining} more '
                       f'violation{"s" if remaining != 1 else ""}</div>')

    dim_html = ""
    if other_lines and not violation_items:
        # Spectral violations or cycle detection output
        shown_lines = other_lines[:MAX_VIOLATIONS_SHOWN]
        for line in shown_lines:
            items_html += format_violation_item(line)
        extra = len(other_lines) - len(shown_lines)
        if extra > 0:
            items_html += f'<div class="more-hint">… and {extra} more</div>'

    violations_block = f"""
        <div class="violations-block">
            {summary_html}
            {items_html}
            {dim_html}
        </div>"""

    return f"""
        <div class="rule-row">
            <span class="rule-icon {icon_cls}">{icon_char}</span>
            <details>
                <summary>
                    <span class="rule-name {name_cls}">{esc(display_name(name))}</span>
                </summary>
                {violations_block}
            </details>
        </div>"""


def render_section(report: dict) -> str:
    suite  = report["suite"]
    label, icon = CLASS_LABELS.get(suite, (suite, ""))
    passed = report["passed"]
    failed = report["failed"]
    total  = report["total"]

    rules_html = "\n".join(render_rule(r) for r in report["rules"])

    passed_badge = f'<span class="badge pass">{passed} passed</span>' if passed else ""
    status_badge = (
        passed_badge
        + f'<span class="badge fail">{failed} failed</span>'
        + f'<span class="badge neutral">{total} rules</span>'
    )

    return f"""
    <div class="section-card">
        <div class="section-header">
            <span class="section-icon">{icon}</span>
            <span class="section-title">{esc(label)}</span>
            <div class="section-counts">{status_badge}</div>
        </div>
        <div class="rules-list">
            {rules_html}
        </div>
    </div>"""


def build_html(reports: list[dict]) -> str:
    total_rules  = sum(r["total"]  for r in reports)
    total_passed = sum(r["passed"] for r in reports)
    total_failed = sum(r["failed"] for r in reports)
    timestamp    = datetime.datetime.now().strftime("%d %b %Y, %H:%M")

    verdict_cls  = "clean" if total_failed == 0 else "violations"
    verdict_text = ("All rules pass" if total_failed == 0
                    else f"{total_failed} violation{'s' if total_failed != 1 else ''} found")

    sections_html = "\n".join(render_section(r) for r in reports)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Architecture Governance Report</title>
<style>{CSS}</style>
</head>
<body>

<header>
    <div>
        <h1>Architecture Governance Report</h1>
        <div class="meta">Structural Fitness Agent · API &amp; Integration Fitness Agent</div>
    </div>
    <div class="timestamp">Generated {timestamp}</div>
</header>

<div class="summary-bar">
    <div class="stat total">
        <div class="num">{total_rules}</div>
        <div class="label">Rules checked</div>
    </div>
    <div class="divider"></div>
    <div class="stat pass">
        <div class="num">{total_passed}</div>
        <div class="label">Passed</div>
    </div>
    <div class="divider"></div>
    <div class="stat fail">
        <div class="num">{total_failed}</div>
        <div class="label">Violations</div>
    </div>
    <span class="verdict {verdict_cls}">{verdict_text}</span>
</div>

<main>
    {sections_html}
</main>

<footer>Structural Fitness Agent &nbsp;·&nbsp; API &amp; Integration Fitness Agent &nbsp;·&nbsp; Architecture Governance with AI</footer>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run architecture governance agents and open unified report"
    )
    parser.add_argument("--structural", action="store_true",
                        help="Run structural fitness agent only")
    parser.add_argument("--api",        action="store_true",
                        help="Run API fitness agent only")
    parser.add_argument("--no-run",     action="store_true",
                        help="Skip agents — regenerate report from last artifacts")
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
        help="Path to the Maven project root to scan and test "
             "(default: example-company/projects/example-service)",
    )
    args = parser.parse_args()

    # Resolve the directories that vary by company/project
    governance_dir  = args.governance_dir.resolve()
    project_dir     = args.project_dir.resolve()
    reports_dir     = project_dir / "target" / "surefire-reports"
    generated_specs = project_dir / "generated-specs"
    ruleset_file    = governance_dir / "spectral-ruleset.yaml"
    junit_file      = generated_specs / "spectral-junit.xml"

    if not args.no_run:
        run_both = not args.structural and not args.api
        if run_both or args.structural:
            run_structural(governance_dir, project_dir)
        if run_both or args.api:
            run_api(governance_dir, project_dir)

    # Collect reports
    reports = []

    if reports_dir.exists():
        for xml_file in sorted(reports_dir.glob("TEST-*.xml")):
            reports.append(load_surefire_report(xml_file))

    if junit_file.exists():
        reports.append(load_spectral_report(junit_file))

    if not reports:
        sys.exit(
            "No test reports found. Run:\n"
            "  python3 run_tests.py"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(build_html(reports), encoding="utf-8")

    total_rules  = sum(r["total"]  for r in reports)
    total_passed = sum(r["passed"] for r in reports)
    total_failed = sum(r["failed"] for r in reports)
    print(f"\nRules: {total_rules}  |  Passed: {total_passed}  |  Violations: {total_failed}")
    print(f"Report: {OUTPUT_HTML}")

    webbrowser.open(OUTPUT_HTML.as_uri())


if __name__ == "__main__":
    main()
