# Restaurant Order Service — Architecture Governance with AI

This project demonstrates how architecture governance can be **automated and AI-assisted**
at enterprise scale using two complementary approaches:

1. **Hand-authored fitness functions** — ArchUnit rules written by a tech lead, enforced in CI
2. **AI-generated fitness functions** — two AI agents that scan the codebase and codify
   governance rules from architecture decisions and standards

The production code intentionally violates both structural and API rules.  
The fitness functions **fail by design** — that is the point.

---

## The Core Idea

> "If you can't enforce it, it isn't an architecture rule — it's a suggestion."

Architecture diagrams and wiki pages drift away from the code the moment they are written.
Fitness functions express architecture intent as **executable tests** that run in CI and
break the build the moment a violation is introduced — whether that violation is a layering
breach, a cross-context import, or a missing API version prefix.

---

## Project Structure

```
├── src/                              Java source with intentional violations
│   └── main/java/com/example/
│       ├── restaurant/order/
│       │   ├── controller/           OrderController  (API + structural violations)
│       │   ├── application/          OrderService     (cross-context violation)
│       │   ├── domain/               Order
│       │   ├── infrastructure/       PaymentGatewayClient
│       │   └── repository/           OrderRepository
│       └── loyalty/                  Separate bounded context
│           └── repository/           LoyaltyRepository
│
├── src/test/java/…/                  Hand-authored ArchUnit fitness functions
│
└── architecture-skill-demo/          AI governance agents
    ├── structural_fitness_agent.py   Generates ArchUnit tests from ADRs + specs
    ├── api_fitness_agent.py          Scans code → OpenAPI spec → Spectral lint
    ├── run_tests.py                  Unified orchestrator + HTML dashboard
    ├── inputs/
    │   ├── adrs/                     Architecture Decision Records
    │   ├── specs/                    Architecture standards, API style guide
    │   └── spectral-ruleset.yaml     Generated Spectral ruleset (committed)
    └── skills/                       AI skill definitions (prompting documents)
```

---

## Violations Baked Into This Code

### Structural violations (ArchUnit catches these)

| # | Where | What | Rule broken |
|---|-------|------|-------------|
| 1 | `OrderController` | Injects and calls `OrderRepository` directly | Controller must not access repository |
| 2 | `OrderService` | Imports concrete `PaymentGatewayClient` | Application must use abstractions |
| 3 | `OrderService` | Imports `LoyaltyRepository` from another context | Bounded contexts must not share repositories |

### API violations (Spectral catches these)

| # | Where | What | Style guide rule |
|---|-------|------|-----------------|
| 4 | `@RequestMapping("/orders")` | No version prefix | §1: paths must start with `/v{n}/` |
| 5 | `@PostMapping` | No `@ResponseStatus(CREATED)` | §4: POST must return 201 |
| 6 | Returns `Order` domain object | No response DTO | §6: internal types must not leak into contracts |
| 7 | `getOrder()` | No error response schema | §5: 4xx responses need `{code, message, correlationId}` |

---

## Prerequisites

**For the hand-authored ArchUnit tests:**
```bash
java -version    # 17+
mvn -version     # 3.8+
```

**For the AI agents (architecture-skill-demo/):**
```bash
python3 --version    # 3.11+
node --version       # 18+ (for spectral)
npm install -g @stoplight/spectral-cli
pip3 install anthropic python-dotenv openapi-spec-validator pyyaml
```

**Azure AI Foundry access** — copy `architecture-skill-demo/.env.example` to
`architecture-skill-demo/.env` and fill in your endpoint and API key.

---

## Demo Flow

### Hand-authored tests only

```bash
mvn test
```

Expected: `BUILD FAILURE` — the intentional violations are caught immediately.

### Full AI governance demo

**Step 1 — Pre-run (do this before the demo, takes a few minutes):**

```bash
cd architecture-skill-demo
python3 run_tests.py
```

This runs both AI agents and opens the unified HTML report.

**Step 2 — Subsequent runs are instant (cache hits):**

```bash
python3 run_tests.py
```

- Structural tests: skip AI generation (governance docs unchanged) → run `mvn test` → fresh results
- API agent: re-scans code, re-generates OpenAPI spec, lints against cached ruleset

**Caching model:**

| Artifact | Regenerated when |
|----------|-----------------|
| `generated-tests/…Test.java` | ADRs or architecture specs change |
| `inputs/spectral-ruleset.yaml` | API style guide changes |
| `generated-specs/openapi.yaml` | Always (reflects current code) |

To force regeneration: `--refresh-tests` or `--refresh-ruleset` flags on the individual agents.

### Run a single agent

```bash
python3 run_tests.py --structural   # structural agent + mvn test
python3 run_tests.py --api          # API agent only
python3 run_tests.py --no-run       # regenerate report from existing artifacts
```

---

## The Two AI Agents

### Structural Fitness Agent

Generates ArchUnit tests from governance documents — not from the code.

```
ADRs + Architecture Specs
         │
         ▼ (only when governance docs change)
  Phase 2: archunit-generator skill → GeneratedFitnessFunctionsTest.java
         │
         ▼ (always)
  Phase 3: mvn test → results → HTML report
```

Phase 1 (codebase scan) still runs each time and is saved to `outputs/` for
human review, but it does **not** feed the test generator. Rules come from ADRs.
A rule is correct because an architect decided it, not because the scanner found a violation.

### API & Integration Fitness Agent

Scans the actual codebase and validates it against the platform API style guide.

```
Source code
    │
    ▼ Phase 1: api-scanner skill → endpoint inventory
    ▼ Phase 2: openapi-generator skill → openapi.yaml (with x-governance-gap annotations)
    ▼ Phase 3: spectral-ruleset-generator (skipped if style guide unchanged)
    ▼ Phase 4: spectral lint → spectral-junit.xml → HTML report
```

---

## The Unified HTML Dashboard

`run_tests.py` produces a single governance report with three sections:

| Section | Icon | Source |
|---------|------|--------|
| Hand-authored Fitness Functions | ✍ | Surefire XML (ArchitectureFitnessFunctionsTest) |
| AI-generated Fitness Functions | ✦ | Surefire XML (GeneratedFitnessFunctionsTest) |
| AI-generated API Fitness Functions | ⬡ | Spectral JUnit XML |

Each section shows ✓ passing and ✗ failing rules. Failing rules expand to show violation details.

---

## Why This Matters at Enterprise Scale

A large Quick Service Restaurant enterprise operates dozens of bounded domains — order
management, kitchen display, loyalty, POS integrations, inventory, delivery orchestration.
Each domain has multiple teams, and each team has engineers who may never have read the
architecture wiki.

Traditional governance relies on Architecture Review Boards (slow), wiki pages (stale), and
code reviews (partial coverage under release pressure). The result: architectural drift is
invisible until it causes an outage, a failed audit, or a replatforming project that takes
three times longer than planned.

### The EA Altitude

The fitness functions in this demo operate at two levels:

| Level | Governed by | Concerns |
|-------|-------------|---------|
| **Code design** | Tech lead | Class layering, dependency inversion, package structure within a service |
| **Enterprise Architecture** | EA team | Bounded context boundaries, cross-domain coupling, API contract standards, platform-wide technology standards |

The EA question is not "does this controller call a repository?" — it is:

> "Does the Loyalty domain import classes from the Order domain? Is the Order service calling
> the Loyalty service synchronously in the checkout path, creating a cascading failure risk?
> Are delivery partner SDKs leaking into domain logic? Does every service follow the API
> versioning standard so consumer contracts are stable?"

Those are the questions the AI agents are designed to surface automatically across every
service on the platform — without an architect reading every file.

### From Governance Decision to Running Test

```
Architect writes ADR
        │
        ▼
AI agent reads ADR → generates ArchUnit rule
        │
        ▼
Rule committed to repo, runs in CI on every PR
        │
        ▼
Violation breaks the build before it merges, before it spreads
        │
        ▼
ADR updated → agent re-generates → new rule replaces old one
```

The tests regenerate when the governance decisions change — not when the code changes.
Code changes run against the existing tests. This is the correct relationship between
governance and implementation.

---

## CI/CD Integration

```yaml
# GitHub Actions — hand-authored tests
- name: Architecture fitness functions
  run: mvn test -Dtest=ArchitectureFitnessFunctionsTest

# GitHub Actions — full governance suite (AI artifacts pre-generated)
- name: Full governance suite
  run: cd architecture-skill-demo && python3 run_tests.py --no-run
  # Note: run_tests.py --no-run reads existing artifacts; agents run separately
  # on ADR/spec changes via a dedicated workflow trigger
```

Because ArchUnit runs against compiled bytecode — not source text — it catches violations
regardless of how the dependency was introduced: direct import, reflection, framework
injection, or indirect transitive coupling.
