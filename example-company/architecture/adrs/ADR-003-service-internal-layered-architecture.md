# ADR-003: Service-Internal Layered Architecture

**Status:** Accepted  
**Date:** 2024-01-15  
**Deciders:** Architecture Council

---

## Context

Each service on the platform must maintain a clean internal layer structure to remain
testable, maintainable, and independently deployable. Without enforced layering, business
logic leaks into controllers, infrastructure concerns leak into domain models, and the
codebase becomes impossible to unit-test or reason about.

Left uncontrolled, developers follow the nearest example — and violations become the
new pattern.

## Decision

Every service must follow this layered structure with one-way dependency rules:

```
controller  →  application  →  domain
                   ↑
             infrastructure        (implements interfaces defined in application)
             repository            (depends only on domain)
```

**Rules:**

1. **Controller layer** (`*.controller.*`) may only call application layer classes. It must not
   directly access repositories, domain entities, or infrastructure adapters.

2. **Application layer** (`*.application.*`) orchestrates use cases. It may depend on domain
   and define interfaces that infrastructure implements. It must not depend directly on
   concrete infrastructure classes — only on abstractions.

3. **Domain layer** (`*.domain.*`) contains core business logic and entities. It must have
   zero dependencies on infrastructure, application, or framework classes. It must be
   testable with no Spring context.

4. **Infrastructure layer** (`*.infrastructure.*`) implements interfaces defined in the
   application layer. It may depend on domain. It must not be accessed directly by
   controllers or domain classes.

5. **Repository layer** (`*.repository.*`) stores and retrieves domain entities. It may
   only be accessed from the application or infrastructure layers.

6. **No cyclic dependencies** are permitted between any two layers. A cycle means neither
   layer can be understood or tested in isolation.

## Naming Conventions

- Controllers: class suffix `Controller`, package `*.controller.*`
- Application services: class suffix `Service`, package `*.application.*`
- Domain entities: package `*.domain.*`
- Infrastructure adapters and clients: class suffix `Client` or `Adapter`, package `*.infrastructure.*`
- Repositories: class suffix `Repository`, package `*.repository.*`

## Enforcement

Use ArchUnit's `layeredArchitecture()` API for the full layer rule set in one declaration.
Use `slices().matching("{service-root}.(*)..")` for cycle detection across layers.
Rule IDs: `FF_003_LAYER_RULES`, `FF_003_NO_LAYER_CYCLES`.
