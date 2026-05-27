# Restaurant Order Service — Architecture Governance Demo

This project demonstrates how **architecture fitness functions** can be codified as automated
tests in a CI/CD pipeline using [ArchUnit](https://archunit.org).

The production code intentionally violates layered-architecture rules.  
The ArchUnit tests **fail by design** — that is the point.

---

## The Core Idea

> "If you can't enforce it, it isn't an architecture rule — it's a suggestion."

Architecture diagrams and wiki pages drift away from the code the moment they're written.
ArchUnit lets you express architecture intent as **executable JUnit 5 tests** that run in CI
and break the build the moment a violation is introduced.

---

## Prerequisites

- Java 17+
- Maven 3.8+

```bash
java -version   # should be 17+
mvn -version    # should be 3.8+
```

---

## Project Structure

```
src/main/java/com/example/restaurant/order/
├── controller/     OrderController       ← HTTP entry point
├── application/    OrderService          ← Business logic / use cases
├── domain/         Order                 ← Core domain entity
├── infrastructure/ PaymentGatewayClient  ← External system adapter
└── repository/     OrderRepository       ← In-memory data store
```

**Intended dependency direction (Clean Architecture):**

```
controller  →  application  →  domain
                    ↑
             infrastructure      (implements interfaces defined in application)
             repository          (depends only on domain)
```

---

## Violations Baked Into This Code

| # | Where | What | Rule Broken |
|---|-------|------|-------------|
| 1 | `OrderController` | Injects and calls `OrderRepository` directly | Controller must not access repository |
| 2 | `Order` (domain) | Imports `PaymentGatewayClient` (infrastructure) | Domain must not depend on infrastructure |
| 3 | `Order` (domain) | Imports `OrderService` (application) | Creates domain ↔ application cycle |
| 4 | `OrderService` | Depends on concrete `PaymentGatewayClient` | Application must use abstractions, not concrete infra |

---

## Demo Flow

### Step 1 — Run the fitness functions and watch them fail

```bash
mvn test
```

Expected: `BUILD FAILURE` — 5 violations reported, 0 passing.

### Step 2 — Read the violation output

Each failure tells you exactly what is wrong and why it matters:

```
Architecture Violation — Rule 'no classes that reside in a package '..controller..'
should access classes that reside in a package '..repository..',
because Controllers must go through the application layer — direct repository access
bypasses business-logic enforcement and makes the boundary unenforceable'
was violated (1 times):

  Method <OrderController.getOrder(String)> calls method
  <OrderRepository.findById(String)> in (OrderController.java:25)
```

### Step 3 — Walk through each fitness function

Open [`src/test/java/com/example/restaurant/order/ArchitectureFitnessFunctionsTest.java`](src/test/java/com/example/restaurant/order/ArchitectureFitnessFunctionsTest.java)

Each `@ArchTest` is one codified rule:

| Test Method | Governance Rule |
|-------------|----------------|
| `controllers_should_not_directly_access_repositories` | Controllers must go through the service layer |
| `domain_should_not_depend_on_infrastructure` | Domain stays pure — no infrastructure imports |
| `application_should_not_directly_use_infrastructure_clients` | Services depend on interfaces, not concrete clients |
| `no_cyclic_dependencies_between_layers` | No layer A→B→A cycles |
| `repositories_only_accessible_from_application_or_infrastructure` | Repository access is always controlled |

### Step 4 — Review the fix plan

See [`REFACTOR_PLAN.md`](REFACTOR_PLAN.md) for the step-by-step fix for each violation.

### Step 5 — (Optional) Apply the fixes and re-run

After applying the fixes in `REFACTOR_PLAN.md`:

```bash
mvn test
```

Expected: `BUILD SUCCESS` — all 5 fitness functions pass.

---

## Why This Matters at Enterprise Scale

At a large QSR enterprise with many engineers, violations accumulate silently:

- New engineers follow the nearest example in the codebase, not the architecture diagram
- Code reviews catch some violations but miss others under time pressure
- Once one violation slips through, it becomes the new "pattern" others copy

ArchUnit makes the rules **executable** — violations break the build on day one, before they
can spread, before they can be copied, and before they can become permanent.

---

## Architecture Governance at Enterprise Scale: A QSR Pattern

### The Problem With Documented Standards

A large Quick Service Restaurant enterprise operates dozens of bounded domains — order
management, kitchen display systems, loyalty, POS integrations, inventory, delivery
orchestration. Each domain has multiple teams, and each team has engineers of varying
tenure who may never have read the architecture wiki.

Traditional governance relies on:

- **Architecture Review Boards** — slow, bottlenecked, not present in every sprint
- **Wiki pages and ADRs** — accurate when written, stale within weeks
- **Code review** — catches some violations, misses others, scales poorly under release pressure
- **Convention by example** — the nearest code becomes the template, good or bad

The result: architectural drift is invisible until it causes an outage, a failed audit,
or a replatforming project that takes three times longer than planned because the layering
assumptions no longer hold.

### From Architecture Decision to Automated Fitness Function

The pattern demonstrated in this project closes that gap:

```
Architecture Decision (ADR / Whiteboard Session)
        │
        ▼
Codified as an ArchUnit Rule (one @ArchTest per principle)
        │
        ▼
Committed to the Repository (lives with the code it governs)
        │
        ▼
Executed in CI/CD on Every Pull Request
        │
        ▼
Build Fails on Violation — Before Merge, Before Spread
```

Each fitness function is a first-class citizen of the codebase. It has a name, a reason,
and a failure message a developer can act on without consulting an architect. The governance
is always running, never fatigued, never on holiday, and scales linearly with the number of
engineers on the platform.

### CI/CD Integration

Add this to your pipeline and every PR is checked automatically:

```yaml
# GitHub Actions example
- name: Architecture fitness functions
  run: mvn test -Dtest=ArchitectureFitnessFunctionsTest

# Jenkins / standard Maven pipeline
mvn verify -Dtest=ArchitectureFitnessFunctionsTest
```

Because ArchUnit runs against compiled bytecode — not source text — it catches violations
regardless of how the dependency was introduced: direct import, reflection, framework
injection, or indirect transitive coupling.

### Where AI Fits: Identifying Gaps and Generating Candidate Rules

Writing the first set of fitness functions is straightforward. The harder problem at
enterprise scale is knowing *which rules you're missing*. AI-assisted governance addresses
this in three ways:

**1. Gap analysis across the existing codebase**

An AI agent can scan a large codebase and surface dependency patterns that violate stated
architecture intent but have not yet been codified as tests. Rather than a human architect
reading thousands of files, the agent produces a prioritized list:

> "Classes in `com.example.loyalty.domain` are imported in 14 places outside the loyalty
> bounded context. No fitness function currently enforces the context boundary."

**2. Candidate rule generation from ADRs and design documents**

Given an Architecture Decision Record or a team's documented standards, an AI agent can
draft the corresponding ArchUnit rules as a starting point for engineer review:

> *ADR-042: The ordering domain must not directly depend on the loyalty domain. Use events.*

```java
// AI-generated candidate — engineer reviews and commits if correct
@ArchTest
static final ArchRule ordering_should_not_depend_on_loyalty =
    noClasses()
        .that().resideInAPackage("com.example.ordering..")
        .should().dependOnClassesThat().resideInAPackage("com.example.loyalty..")
        .because("ADR-042: cross-domain dependencies must use events, not direct calls");
```

**3. Continuous monitoring for rules that have become stale**

As the codebase evolves, some fitness functions become obsolete or start producing false
positives because the architecture itself changed intentionally. AI can flag these for
review — keeping the governance layer honest rather than letting it accumulate noise that
engineers learn to ignore.

### The Governance Loop

```
Architect defines intent
        │
        ▼
AI identifies gaps + drafts candidate rules
        │
        ▼
Engineer reviews, refines, and commits rules
        │
        ▼
CI enforces rules on every merge
        │
        ▼
Violations surface early — teams fix before drift compounds
        │
        ▼
Architecture evolves → AI detects stale rules → loop repeats
```

This is not about replacing architects or removing human judgment. It is about making
architectural decisions durable — encoding them in a form that survives team turnover,
release pressure, and the passage of time. In a QSR enterprise where the cost of a layering
violation might be invisible today and catastrophic during the next peak trading window,
that durability is the point.

---

## Running Only the Architecture Tests

```bash
mvn test -Dtest=ArchitectureFitnessFunctionsTest
```
