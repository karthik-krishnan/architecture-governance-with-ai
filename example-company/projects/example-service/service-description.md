# Example Company Platform — Service Description

## Context

This document describes the current state of the Example Company digital platform.
The platform is decomposed into independently owned services, built incrementally
over several years. Not all decomposition decisions were architecturally consistent.

---

## Bounded Contexts and Domain Ownership

Each service represents a bounded context with a dedicated engineering team, its own
release cadence, and its own SLO.

Services communicate through versioned HTTP APIs and domain events published to the
shared message bus. Direct cross-service database access and direct import of another
service's internal domain classes are prohibited.

---

## Current Integration Patterns (Mixed)

The platform uses an inconsistent mix of synchronous and asynchronous patterns:

| Integration | Current Pattern | Target Pattern |
|-------------|----------------|----------------|
| State-change notifications to downstream services | Synchronous REST calls | Domain events on the message bus |
| Read queries to other services (non-state-change) | Synchronous REST (acceptable) | Keep synchronous |
| Analytics aggregation | Direct database read queries | Domain events + materialised views |

---

## Technology Stack

- **Runtime:** Java 17, Spring Boot 3.x
- **Messaging:** Apache Kafka (partially adopted)
- **Databases:** PostgreSQL (per-service)
- **Auth:** OAuth2; service-to-service auth inconsistent (some JWT, some network trust)
- **Observability:** Structured logging (inconsistent adoption), no distributed trace propagation standard

---

## Known Architecture Concerns

The following concerns are awaiting EA review:

1. Several services make synchronous REST calls to downstream services during
   state-change flows — creating implicit SLO dependencies across team boundaries
2. At least one service reads directly from another service's database, bypassing
   the owning service's API
3. PII fields appear in distributed traces for multiple services — flagged by the
   security team but not yet remediated
4. Service-to-service authentication is inconsistent — some services use platform-issued
   JWTs, others rely on internal network trust
