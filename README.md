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

## Running Only the Architecture Tests

```bash
mvn test -Dtest=ArchitectureFitnessFunctionsTest
```
