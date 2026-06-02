# Architecture Fitness Function Advisor — Skill Demo

This folder demonstrates an AI-assisted Architecture Skill operating at the
**Enterprise Architecture level**: bounded contexts, cross-domain coupling, platform
standards, and CI/CD enforcement — not individual class design within a service.

---

## The Operating Model

```
                        ┌──────────────────────────────────────┐
                        │      Architecture Skill (AI)         │
                        │                                      │
                        │  Reviews:                            │
                        │  · service-description.md            │
                        │  · architecture-standards.md         │
                        │  · current-codebase-summary.md       │
                        │                                      │
                        │  Produces:                           │
                        │  · architecture-review-report.md     │
                        │  · recommended-fitness-functions.md  │
                        │  · generated-archunit-tests.java     │
                        └──────────────────┬───────────────────┘
                                           │
                                    Advisory findings
                                    + Candidate rules
                                           │
                                           ▼
                        ┌──────────────────────────────────────┐
                        │         Architect Review             │
                        │                                      │
                        │  · Is the finding valid?             │
                        │  · Does the rule scope correctly?    │
                        │  · Is the timing right (migration    │
                        │    must happen before enforcement)?  │
                        └──────────────────┬───────────────────┘
                                           │
                                    Sign-off
                                           │
                                           ▼
                        ┌──────────────────────────────────────┐
                        │      Governance Committed to Code    │
                        │                                      │
                        │  ArchUnit tests → service repo       │
                        │  Spectral rules → API catalogue CI   │
                        │  detect-secrets → pre-commit hook    │
                        │  Pact tests → integration pipeline   │
                        │  Schema registry → event producer CI │
                        └──────────────────┬───────────────────┘
                                           │
                                    Automated enforcement
                                           │
                                           ▼
                        ┌──────────────────────────────────────┐
                        │         CI/CD Quality Gates          │
                        │                                      │
                        │  Every PR, every service,            │
                        │  no human required per review        │
                        └──────────────────────────────────────┘
```

---

## What the Skill Does and Does Not Do

**The Skill does:**
- Review architecture inputs and identify risks at domain and platform level
- Distinguish between critical blockers (bounded context violations, secrets in source control) and medium-term improvements (API contract gaps)
- Generate ArchUnit test candidates that an architect can validate and commit
- Point to the right tool for each rule (ArchUnit, Spectral, Pact, detect-secrets, Schema Registry)
- Explain each finding in business terms — not just "this is a dependency violation" but "this is why the Q3 loyalty points incident happened and how to prevent the next one"
- Distinguish between Advisory (AI identified it; needs human judgment) and Enforced (committed and blocking in CI)

**The Skill does not:**
- Replace architect judgment — all findings are advisory until a human signs off
- Enforce anything at runtime — enforcement happens through tools committed to CI/CD
- Perform SAST analysis — use SonarQube, Checkmarx, or Semgrep for that
- Scan for secrets — use detect-secrets, Trufflehog, or GitGuardian
- Lint API specs — use Spectral
- Validate Kafka schema compatibility — use Confluent Schema Registry

---

## The Difference Between Advisory and Enforced

This is the most important operational distinction in the governance model.

**Advisory** means the AI noticed a pattern. It requires:
1. An architect to validate: "yes, this applies to our context"
2. A decision on timing: "can we enforce now, or must a migration happen first?"
3. A sign-off before the rule is committed

**Enforced** means the rule is committed to a repository and wired into a CI gate. It blocks
merges without human intervention. Once a rule is Enforced:
- No engineer can introduce the violation without the build failing
- The rule is version-controlled alongside the code it governs
- The rule can be updated or removed through a PR, with full review history

The governance layer only works if Enforced rules are trustworthy. Prematurely enforcing a
rule that produces false positives — or enforcing before the codebase migration is done —
teaches engineers to suppress or ignore the gate. That is worse than no governance at all.

---

## Folder Structure

```
architecture-skill-demo/
├── skill.md                               ← The advisor skill definition and evaluation lenses
├── run_skill.py                           ← Live demo runner — calls the Claude API
│
├── inputs/                                ← What you feed the skill
│   ├── service-description.md             ← Platform overview: domains, ownership, integrations
│   ├── architecture-standards.md          ← Enterprise standards the platform must meet
│   └── current-codebase-summary.md        ← Codebase scan results: violations, gaps, risks
│
├── samples/                               ← Pre-written examples of skill output (for reference)
│   ├── architecture-review-report.md
│   ├── recommended-fitness-functions.md
│   └── generated-archunit-tests.java
│
└── outputs/                               ← Live-generated output lands here (empty until you run)
    └── live-<timestamp>/
        ├── architecture-review-report.md
        ├── recommended-fitness-functions.md
        └── generated-archunit-tests.java
```

---

## EA-Level Concerns vs. Code Design Concerns

The fitness functions in the [`restaurant-order-demo`](../src/) (controller calling repository,
domain depending on infrastructure) are **code design rules**. They are useful for
demonstrating *how* ArchUnit works, but they are not what an Enterprise Architecture team
primarily governs.

The concerns in this folder are what EA actually cares about:

| EA Concern | Example from This Demo | Business Consequence If Ignored |
|-----------|----------------------|--------------------------------|
| Bounded context boundaries | Analytics reading Order + Loyalty repositories directly | Analytics releases coupled to every domain team's schema; read workloads compete with transactions |
| Cross-domain sync coupling | Order service calling Loyalty synchronously on completion | Q3 2025 P1 incident: loyalty points lost under load because the synchronous call timed out |
| Anti-Corruption Layer | DoorDash SDK in `DeliveryJob` domain entity | Partner SDK update forces domain model change; adding a fourth delivery partner requires touching the domain |
| API contract governance | Kitchen Display has no OpenAPI spec | Undetected breaking changes; consumer teams have no deprecation notice |
| PII in telemetry | `customerEmail` in Datadog trace attributes | Data governance breach; broad access to observability tooling ≠ data access controls |
| Secrets in source | DoorDash API key in `application.properties` | Anyone with git read access has production credentials |
| Technology stack compliance | OkHttp and RestTemplate in two services | Platform resilience configuration (circuit breakers, retries) bypassed; SRE cannot diagnose what they don't own |

---

## How to Use the Skill

### Option A — Run It Live (Recommended for Stakeholder Demo)

`run_skill.py` calls the Claude API in real time so you can watch the AI generate the
review from scratch.  This makes the AI skill tangible — the outputs aren't static files,
they are produced live from the inputs.

```bash
# 1. Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 2. Run the live demo
cd architecture-skill-demo
python3 run_skill.py
```

The script:
- Loads `skill.md` as the AI's operating instructions (the "skill")
- Loads the three files in `inputs/` as the review context
- Calls `claude-opus-4-7` with adaptive thinking enabled
- Streams the response to the terminal as it is generated
- Saves the output to `outputs/live-architecture-review-<timestamp>.md`

You can then compare the live output with the pre-authored examples in `outputs/` to see
how the skill shapes the analysis.

### Option B — Sample Outputs

The `samples/` directory contains pre-authored examples showing the kind of output the
skill produces.  These are useful for reviewing the format before running the live demo.

### Invoke the Skill in Any Claude Session

You can also invoke the advisor directly in any Claude conversation by pasting the three
input files as context and using this prompt:

> "Using the Architecture Fitness Function Advisor skill, review the QSR platform described
> in service-description.md against the standards in architecture-standards.md, given the
> current state in current-codebase-summary.md. Produce a review report, recommended
> fitness functions, and ArchUnit candidates."

The skill will work through each of the seven evaluation lenses and produce structured output
in the format defined in `skill.md`.

---

## The Governance Loop in CI/CD

Once rules are promoted from Advisory to Enforced, they run automatically:

```
Developer opens PR
        │
        ▼
CI pipeline triggers
        │
        ├── mvn test (ArchUnit fitness functions)           ← bounded context, ACL, banned libs
        ├── spectral lint openapi.yaml                      ← API contract standards
        ├── pact verify (Pact broker)                       ← consumer-driven contracts
        ├── detect-secrets scan                             ← secrets detection
        ├── mvn dependency-check:check (OWASP)             ← vulnerability scanning
        └── sonar (SonarQube quality gate)                 ← static analysis
                        │
               All gates pass?
                │           │
               YES           NO
                │           │
            Merge         Block
          permitted      with specific
                         failure message
                         and remediation link
```

The architecture team authors the rules once. CI enforces them on every PR across every
team, without an architect needing to attend any code review.
