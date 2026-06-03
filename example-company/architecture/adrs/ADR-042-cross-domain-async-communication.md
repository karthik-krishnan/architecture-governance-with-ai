# ADR-042: Cross-Domain Communication Must Be Asynchronous for State Changes

**Status:** Accepted  
**Date:** 2025-10-20  
**Deciders:** Architecture Council  
**Trigger:** Q3 2025 P1 incident — downstream service data loss during peak load

---

## Context

### The Incident

During a peak load window, a service made synchronous HTTP calls to a downstream service
as part of a state-change flow. When the downstream service latency increased under load,
those calls timed out. The upstream operation appeared to fail from the client's perspective
even though the primary transaction had completed. A significant number of downstream
state updates were silently dropped.

Root cause: the upstream service's SLO was implicitly extended to cover the downstream
service's availability. One team's degradation became every upstream team's incident.

### The Pattern

This is not isolated to one integration. The same synchronous coupling exists across
multiple service boundaries in state-change flows. Any synchronous call from one bounded
context to another during a state-change creates this failure mode.

## Decision

State-change flows must not make synchronous HTTP calls into consuming bounded contexts.
The triggering context publishes a domain event to the message bus and returns. Consuming
contexts subscribe and process at their own pace.

Specifically:
- Classes in `*.application.*` packages must not hold a direct reference to an HTTP
  client targeting another bounded context's service.
- Cross-context HTTP clients (classes with suffix `Client` referencing another context)
  must not appear in application-layer classes.
- State-change notifications must be triggered by domain events consumed from the message bus.

## Naming Conventions

- HTTP client classes: suffix `Client`, reside in `*.infrastructure.client.*`
- Application service classes: suffix `Service`, reside in `*.application.*`
- The rule targets: any `*Service` class importing a `*Client` that references
  a different bounded context by package or class name.

## Consequences

**Positive:** Each context's SLO is independent. A downstream service degrading does
not affect the upstream service's response latency. Events are durable — if a downstream
service is unavailable, it catches up when it recovers.

**Negative:** Eventual consistency. Downstream state is not updated in the same
transaction as the triggering event. This is an accepted trade-off documented to Product.

## Enforcement

ArchUnit rule preventing application-layer classes from importing infrastructure
HTTP clients that reference other bounded contexts. Rule ID: `FF-ASYNC-COMMS`.
