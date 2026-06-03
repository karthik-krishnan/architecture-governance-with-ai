# ADR-001: Bounded Context Boundaries

**Status:** Accepted  
**Date:** 2024-03-01  
**Deciders:** Architecture Council

---

## Context

The platform is decomposed into independent bounded contexts, each owned by a separate
engineering team with its own release cadence and SLO.

As the platform has grown, teams have taken shortcuts — importing domain entities and
repository interfaces directly from other contexts rather than using published APIs or
subscribing to domain events. This has created hidden coupling that prevents independent
deployment and causes cascading failures when one team's schema changes.

## Decision

Each bounded context is a deployment and ownership boundary. The following rules apply
without exception:

1. No class in context A may import a class from context B's `domain` or `infrastructure`
   packages. Cross-context data access must go through the context's published API or
   domain events on the message bus.

2. No class may directly reference another context's repository interface or JPA entity.
   Repositories are implementation details — they are not a public API.

3. Classes that need data from another context must either subscribe to that context's
   domain events or call its versioned HTTP API. The consuming context owns its own
   read model materialised from those events or API responses.

## Naming Conventions

- Bounded context root package: `com.example.{context}`
- Repository classes: suffix `Repository`
- Domain entity classes: reside in `*.domain.*` package
- Infrastructure classes: reside in `*.infrastructure.*` package

## Consequences

**Positive:** Teams can deploy independently. Schema changes in one context do not
require coordination with consuming teams. Read workloads are separated from
transactional workloads.

**Negative:** Teams must publish and maintain event schemas. Some features require
eventual consistency rather than immediate consistency.

## Enforcement

ArchUnit rule targeting `*.domain.*` and `*.infrastructure.*` import boundaries
across context packages. Rule ID: `FF-BOUNDED-CTX`.
