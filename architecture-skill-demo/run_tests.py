#!/usr/bin/env python3
"""
Architecture Governance Report
================================
Runs Maven fitness function tests and generates a self-contained HTML
governance dashboard. Opens in the browser automatically.

Demo flow:
    python3 run_tests.py --reset    # BEFORE: clears AI-generated tests, shows hand-authored only
    python3 structural_fitness_agent.py   # runs the Structural Fitness Agent live
    python3 run_tests.py            # AFTER: shows hand-authored + AI-generated side by side

Other usage:
    python3 run_tests.py --no-run   # regenerate report from last test run without re-running tests
"""

import argparse
import datetime
import pathlib
import subprocess
import sys
import webbrowser
import xml.etree.ElementTree as ET

SCRIPT_DIR     = pathlib.Path(__file__).parent
MAVEN_ROOT     = SCRIPT_DIR.parent
REPORTS_DIR    = MAVEN_ROOT / "target" / "surefire-reports"
OUTPUT_DIR     = SCRIPT_DIR / "outputs"
OUTPUT_HTML    = OUTPUT_DIR / "governance-report.html"
GENERATED_FILE  = MAVEN_ROOT / "generated-tests" / "com" / "example" / "governance" / "GeneratedFitnessFunctionsTest.java"
GENERATED_CLASS = MAVEN_ROOT / "target" / "test-classes" / "com" / "example" / "governance" / "GeneratedFitnessFunctionsTest.class"
GENERATED_XML   = MAVEN_ROOT / "target" / "surefire-reports" / "TEST-com.example.governance.GeneratedFitnessFunctionsTest.xml"

MAX_VIOLATIONS_SHOWN = 5

CLASS_LABELS = {
    "ArchitectureFitnessFunctionsTest": ("Hand-authored Fitness Functions", "✍"),
    "GeneratedFitnessFunctionsTest":    ("AI-generated Fitness Functions", "✦"),
}


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

def run_tests() -> None:
    print("Running fitness function tests...", end="", flush=True)
    result = subprocess.run(
        ["mvn", "test", "-Dmaven.test.failure.ignore=true", "--batch-mode", "-q"],
        cwd=MAVEN_ROOT,
        capture_output=True,
    )
    if result.returncode not in (0, 1):
        print(" failed.")
        sys.exit(result.stderr.decode(errors="replace") or f"mvn exited with code {result.returncode}")
    print(" done.")


# ---------------------------------------------------------------------------
# Parse surefire XML
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


def load_report(xml_path: pathlib.Path) -> dict:
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
    """Convert snake_case rule names to readable display text.
    The first two parts are treated as the prefix (e.g. FF + 001, or FF + SEC)
    and kept uppercase. The rest becomes sentence-cased.
    """
    parts = rule_name.split("_")
    prefix = [p for p in parts[:2] if p.isdigit() or (p.isupper() and len(p) <= 4)]
    desc_parts = parts[len(prefix):]
    desc_text = " ".join(p.lower() for p in desc_parts)
    if desc_text:
        desc_text = desc_text[0].upper() + desc_text[1:]
    return (" ".join(prefix) + " " + desc_text).strip()


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def format_violation_item(line: str) -> str:
    """Format a single violation line, splitting the location suffix."""
    # Extract (File.java:N) suffix if present
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

    # Separate summary line from detail lines
    summary_lines = [l for l in viols if "was violated" in l or "Architecture Violation" in l]
    detail_lines  = [l for l in viols if l not in summary_lines]

    summary_html = ""
    if summary_lines:
        summary_html = f'<div class="violation-summary">{esc(summary_lines[0])}</div>'

    # Categorise detail lines
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
        items_html += f'<div class="more-hint">… and {remaining} more violation{"s" if remaining != 1 else ""}</div>'

    dim_html = ""
    if other_lines and not violation_items:
        # Cycle detection output — show first few dim lines
        dim_text = "\n".join(other_lines[:MAX_VIOLATIONS_SHOWN])
        if len(other_lines) > MAX_VIOLATIONS_SHOWN:
            dim_text += f"\n… {len(other_lines) - MAX_VIOLATIONS_SHOWN} more lines"
        dim_html = f'<div class="dim-block">{esc(dim_text)}</div>'

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
    suite = report["suite"]
    label, icon = CLASS_LABELS.get(suite, (suite, ""))
    passed = report["passed"]
    failed = report["failed"]
    total  = report["total"]

    rules_html = "\n".join(render_rule(r) for r in report["rules"])

    status_badge = (
        f'<span class="badge pass">{passed} passed</span>'
        f'<span class="badge fail">{failed} failed</span>'
        f'<span class="badge neutral">{total} rules</span>'
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
    verdict_text = "All rules pass" if total_failed == 0 else f"{total_failed} violation{'s' if total_failed != 1 else ''} found"

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
        <div class="meta">Structural Fitness Agent — ArchUnit fitness functions</div>
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

<footer>Structural Fitness Agent &nbsp;·&nbsp; Architecture Governance with AI</footer>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run architecture fitness functions and open governance report")
    parser.add_argument("--reset", action="store_true",
                        help="Remove AI-generated tests before running — use for the BEFORE state of the demo")
    parser.add_argument("--no-run", action="store_true",
                        help="Skip mvn test — regenerate report from last run")
    args = parser.parse_args()

    if args.reset:
        removed = []
        for path in (GENERATED_FILE, GENERATED_CLASS, GENERATED_XML):
            if path.exists():
                path.unlink()
                removed.append(path.name)
        if removed:
            print(f"Cleared AI-generated tests ({', '.join(removed)}) — showing hand-authored only.")
        else:
            print("No AI-generated tests found — already clean.")

    if not args.no_run:
        run_tests()

    xml_files = sorted(REPORTS_DIR.glob("TEST-*.xml")) if REPORTS_DIR.exists() else []
    if not xml_files:
        sys.exit(
            f"No test reports found at: {REPORTS_DIR}\n"
            f"Run:  python3 run_tests.py"
        )

    reports = [load_report(f) for f in xml_files]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(build_html(reports), encoding="utf-8")

    # Print brief terminal summary
    total_rules  = sum(r["total"]  for r in reports)
    total_passed = sum(r["passed"] for r in reports)
    total_failed = sum(r["failed"] for r in reports)
    print(f"Rules: {total_rules}  |  Passed: {total_passed}  |  Violations: {total_failed}")
    print(f"Report: {OUTPUT_HTML}")

    webbrowser.open(OUTPUT_HTML.as_uri())


if __name__ == "__main__":
    main()
