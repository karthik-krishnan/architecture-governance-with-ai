# Architecture Governance with AI — Demo Script

**Audience:** Enterprise architects, engineering leaders  
**Duration:** 15–20 minutes  
**Setup:** Pre-run `python3 run_tests.py` before the room fills. Report is open in a browser tab.

---

## Run Commands Reference

```bash
# Pre-demo: run everything once, opens HTML report (takes a few minutes)
cd architecture-skill-demo
python3 run_tests.py

# Act 2 — show raw ArchUnit failures in terminal
cd ..          # project root
mvn test

# Act 5 — re-run during demo (fast — structural cache hits, API re-scans)
cd architecture-skill-demo
python3 run_tests.py

# Regenerate report only, no agent calls
python3 run_tests.py --no-run

# Run a single agent
python3 run_tests.py --structural
python3 run_tests.py --api

# Demo: ADR changed → structural tests regenerate
# (edit any file in inputs/adrs/ — governance hash changes, auto-triggers)
python3 run_tests.py --structural
# or force without editing:
python3 structural_fitness_agent.py --refresh-tests

# Demo: API style guide changed → Spectral ruleset regenerates
# (edit inputs/specs/api-style-guide.md — SHA changes, auto-triggers)
python3 run_tests.py --api
# or force without editing:
python3 api_fitness_agent.py --refresh-ruleset
```

---

## Before You Start — Setup Checklist

- [ ] `python3 run_tests.py` has been run and the HTML report is open in a browser tab
- [ ] IDE or editor open with the project root visible
- [ ] Terminal ready at `architecture-skill-demo/`
- [ ] Spectral ruleset already generated (`inputs/spectral-ruleset.yaml` exists)

---

## Act 1 — The Problem (3 min)

### What to say

> "Every enterprise I've worked with has the same arc. Architecture Council meets, decisions
> get made, ADRs get written. They go into Confluence. Engineers read them — once, maybe —
> and then go build things. Six months later the codebase looks nothing like the diagram."

> "The standard response is more process: bigger architecture review boards, more gates,
> mandatory sign-offs. None of it scales. You have one EA team and a hundred engineers
> shipping code every day."

> "What we've built here is a different answer. The rules run in CI. An AI agent reads your
> ADRs and writes the enforcement code. Let me show you what that looks like in practice."

---

## Act 2 — The Codebase (3 min)

### What to show

Open `src/main/java/com/example/restaurant/order/controller/OrderController.java`

### What to say

> "This is a normal-looking Spring controller. Order service, restaurant domain. Nothing
> obviously wrong at first glance."

Point to line 16:
```java
private final OrderRepository orderRepository;
```

> "But look here. The controller is holding a reference to the repository directly. ADR-003
> says controllers may only call the application layer. The repository is two layers down.
> This is a violation — but it compiled, it passed code review, and it's running in production."

Open `src/main/java/com/example/restaurant/order/application/OrderService.java`

Point to line 6:
```java
import com.example.loyalty.repository.LoyaltyRepository; // VIOLATION
```

> "Here's the more expensive one. The Order service is importing the Loyalty bounded
> context's repository directly. ADR-001 exists precisely to prevent this — bounded contexts
> must communicate through APIs or events, never by sharing a repository.
> This is the kind of coupling that turns one team's deployment into every team's outage."

> "Neither violation was intentional. Both passed review. That's the point."

---

## Act 3 — Traditional Fitness Functions (2 min)

### What to say

> "The traditional answer is to write these rules as ArchUnit tests — executable architecture
> rules that run in CI. Here's what that looks like."

### What to show

Open `src/test/java/com/example/restaurant/order/ArchitectureFitnessFunctionsTest.java`

> "A tech lead sat down and encoded the rules from ADR-003 as JUnit tests. This is the right
> instinct. The rules are now in version control, they run on every PR, and they produce a
> failure message a developer can act on."

> "The problem is who writes these. This took an hour for one service. We have forty services.
> And when ADR-003 is updated, someone has to remember to update the tests too."

---

## Act 4 — The AI Agents (2 min)

### What to say

> "This is where the AI agents come in. Instead of a human translating ADRs into tests,
> an agent does it. Let me show you the inputs."

### What to show

Open `architecture-skill-demo/inputs/adrs/ADR-001-bounded-context-boundaries.md`

> "This is the same ADR the Architecture Council approved in 2024. We haven't touched it.
> The agent reads this document — the naming conventions, the enforcement intent, the
> package patterns — and generates the ArchUnit rule."

Open `architecture-skill-demo/inputs/specs/api-style-guide.md`

> "And this is the platform API style guide. Version 3.0, owned by Platform Architecture.
> Every HTTP API the platform exposes is supposed to follow these rules: version prefix in
> every path, POST returns 201, error responses have a standard schema. The second agent
> reads this and generates a Spectral lint ruleset."

---

## Act 5 — The Report (5 min)

### What to say

> "Let me show you what we get when we run both agents against this codebase."

Switch to the browser — HTML governance report is already open.

> "Three sections. Hand-authored tests at the top. Then AI-generated structural tests.
> Then AI-generated API tests. One report, one command."

### Walk the Structural section (✦)

Point to the failing rules:

> "The AI agent generated this from ADR-001 and ADR-003. It found that OrderService imports
> LoyaltyRepository — the exact cross-context violation we looked at in the code. And it
> found the controller bypassing the application layer."

> "Notice the rule name: `FF_001_order_context_must_not_import_loyalty_repository`. It's
> named after the ADR, with a `because()` clause in the test that cites the business reason.
> When a developer sees this failure they know exactly which decision they've violated and
> why it matters."

Point to passing rules:

> "And here are the rules that pass. The cycle detection is clean. The domain layer has no
> infrastructure imports. Passing rules matter — you want to know your governance baseline
> is holding, not just where it's broken."

### Walk the API section (⬡)

> "Now the API agent. This one did something different — it didn't just read documents, it
> scanned the actual source code, produced an OpenAPI spec from what the code actually
> exposes, and then linted that spec against the style guide."

Point to the failing API rules:

> "`Api versioned paths` — the Order endpoint is `/orders`, not `/v1/orders`. That's a
> §1 violation. Any consumer we onboard today will break when we version the API tomorrow."

> "`Post returns 201` — the POST endpoint returns 200 by default. Every client we've
> shipped assumes 200. Every client every other team writes in the future will be
> inconsistent."

Point to passing API rules:

> "But kebab-case naming is correct. No PII in path parameters. camelCase properties.
> Those pass. The style guide is partially being followed — the agent surfaces exactly
> where it isn't."

---

## Act 6 — The Governance Model (3 min)

### What to say

> "Here's the part I want you to pay attention to, because this is where the design decision
> matters."

> "When do the AI-generated structural tests regenerate?"

Pause.

> "Not when the code changes. When the ADRs change."

> "ADR-001 hasn't changed. So the tests haven't changed. But `mvn test` ran just now and
> used those tests against the current code. The violation is caught. If someone adds a new
> cross-context import tomorrow, the same test catches it — without the agent running again."

> "That's the correct relationship between governance and implementation. The rule comes
> from the Architecture Council. The code is measured against it. The rule only changes
> when the Council changes it — and at that point, the agent regenerates automatically."

Open `architecture-skill-demo/inputs/spectral-ruleset.yaml`, show the first line:

```yaml
# style-guide-sha256: abc123...
```

> "Same model for the API ruleset. The agent embedded a hash of the style guide into the
> committed ruleset. Next time this runs, it checks the hash. If the style guide hasn't
> changed, it skips the generation entirely. No API call. No cost. Instant."

> "And if the style guide does change — if Platform Architecture publishes version 4.0 —
> the agent regenerates automatically on the next run. No one has to remember."

---

## Act 7 — The EA Pitch (2 min)

### What to say

> "This demo has one service. Let's talk about what this looks like at scale."

> "You have forty services. Each one has a team. The EA team has four architects.
> The traditional model is: architects write fitness functions for each service, update them
> when ADRs change, and somehow keep up with forty teams shipping every day. That doesn't work."

> "The AI model is: you write the ADR once. You run the agent against every service.
> Every service gets the fitness functions derived from your actual governance decisions.
> When ADR-001 is updated, you run the agent, the tests update, and that update applies
> across all forty services."

> "The EA team's job shifts from writing tests to writing good ADRs. Which is actually
> their job."

> "The API style guide enforcement is the same story. Platform Architecture owns the style
> guide. The agent enforces it across every API in the platform. An engineer who misses
> the version prefix doesn't get a code review comment two days later — they get a failed
> build in five minutes."

---

## Act 8 — Q&A Handles

**"What if the AI generates a wrong rule?"**

> "The tests are committed to the repo like any other code. An architect reviews them before
> they go into CI. The agent drafts, the human approves. That's the right split — the AI
> does the mechanical translation from ADR to code, the architect confirms the intent is
> preserved."

**"What about languages other than Java?"**

> "The API governance agent is language-agnostic — it scans source patterns and generates
> OpenAPI, then lints the spec. The structural agent uses ArchUnit which is JVM-specific,
> but the same pattern exists in other ecosystems: `dependency-cruiser` for TypeScript,
> `NetArchTest` for .NET, `import-linter` for Python."

**"How do you handle violations that are intentional during a migration?"**

> "ADR-003 has a concept for this — `REQUIRES MIGRATION FIRST`. The generated test gets
> an `ignoreDependency()` clause and a comment block with the checklist of prerequisites
> before it can be enabled. The violation is tracked in the code, not in someone's head."

**"Does this replace the Architecture Review Board?"**

> "No — it changes what the ARB spends its time on. Instead of reviewing whether someone
> violated ADR-001, the ARB discusses whether ADR-001 is still the right decision. The
> mechanical enforcement is handled. The judgment stays with the humans."

---

## Closing Line

> "Architecture governance fails when it depends on people remembering to check. This makes
> the rules run. They run on every PR, they run on every service, and they update when
> your decisions update. That's the gap we're closing."
