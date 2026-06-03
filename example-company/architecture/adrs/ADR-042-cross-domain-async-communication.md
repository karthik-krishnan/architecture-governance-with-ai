# ADR-042: Cross-Domain Communication Must Be Asynchronous for State Changes

**Status:** Accepted  
**Date:** 2025-10-20  
**Deciders:** Architecture Council  
**Trigger:** Q3 2025 P1 incident — loyalty points lost during peak load

---

## Context

### The Incident

On 2025-08-14 during a peak trading window, the Order service made synchronous HTTP calls
to the Loyalty service as part of the order completion flow. When Loyalty service latency
increased under load, those calls timed out. Orders appeared to fail from the customer's
perspective even though payment had completed. Approximately 12,000 loyalty point awards
were silently dropped.

Root cause: the Order service's SLO was implicitly extended to cover the Loyalty service's
availability. One team's degradation became every upstream team's incident.

### The Pattern

This is not isolated to Order → Loyalty. The same synchronous coupling exists in:
- Order → Kitchen Display (ticket creation blocks order confirmation response)
- Order → Analytics (event push blocks order completion flow)

Any synchronous call from one bounded context to another in a state-change flow
creates this failure mode.

## Decision

Post-order state change flows must not make synchronous HTTP calls into consuming
bounded contexts. The triggering context (Order) publishes a domain event to the
message bus and returns. Consuming contexts (Loyalty, Kitchen Display, Analytics)
subscribe and process at their own pace.

Specifically:
- Classes in `*.application.*` packages must not hold a direct reference to an HTTP
  client targeting another bounded context's service.
- Cross-context HTTP clients (classes with suffix `Client` referencing another context
  by name) must not appear in application-layer classes.
- Post-order operations must be triggered by domain events consumed from the message bus.

## Naming Conventions

- HTTP client classes: suffix `Client`, reside in `*.infrastructure.client.*`
- Application service classes: suffix `Service`, reside in `*.application.*`
- The rule targets: any `*Service` class importing a `*Client` that references
  a different bounded context by package or class name.

## Consequences

**Positive:** Each context's SLO is independent. Loyalty degradation does not affect
order confirmation latency. Events are durable — if Loyalty is down, points are
awarded when it recovers.

**Negative:** Eventual consistency. Loyalty points are not awarded in the same
transaction as the order. This is an accepted trade-off documented to Product.

## Enforcement

ArchUnit rule preventing application-layer classes from importing infrastructure
HTTP clients that reference other bounded contexts. Rule ID: `FF-ASYNC-COMMS`.
