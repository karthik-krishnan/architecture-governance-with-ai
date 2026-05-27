# Architecture Review Report — QSR Digital Platform

**Skill used:** Architecture Fitness Function Advisor v1.0  
**Review date:** 2026-Q1  
**Inputs reviewed:** service-description.md, architecture-standards.md, current-codebase-summary.md  
**Reviewed by:** AI-assisted analysis — requires architect validation before action

---

> **How to read this report**
>
> Findings are presented at domain and platform level — the concern is how domains relate
> to each other, how the platform holds together, and where standards are not being met.
> This is not a code review. Individual class-level design decisions within a domain are
> the responsibility of that domain's engineering team.
>
> Each finding includes a Governance Mode:
> - **Advisory** — AI identified this; architect must validate before any action
> - **Enforced (Candidate)** — ready to be committed as an automated gate; awaits architect sign-off

---

## Executive Summary

The QSR Digital Platform has significant architecture debt concentrated in three areas:

1. **Bounded context boundaries are not being enforced** — domains import each other's
   internal classes and access each other's databases directly. This has already caused
   production incidents and is the primary obstacle to independent team scaling.

2. **Cross-domain integrations are synchronously coupled where they should be event-driven**
   — the P1 loyalty incident in Q3 2025 was a direct consequence of this. The coupling
   transfers operational risk from one team's service to another.

3. **The PCI-DSS and PII boundaries are being breached in telemetry and inter-service DTOs**
   — card data tokens and customer PII appear in observability tooling and in service
   contracts that have no right to hold them.

The platform has the right standards documented (architecture-standards.md). The problem
is that those standards have no automated enforcement mechanism — they rely entirely on
code review and goodwill. This review identifies where fitness functions would close that gap.

---

## Finding 1 — Analytics Service Directly Accesses Order and Loyalty Repositories

**Risk Level:** CRITICAL  
**EA Lens:** Lens 1 — Bounded Context Integrity  
**Governance Mode:** Enforced (Candidate)  
**Enforcement Mechanism:** ArchUnit  

**Business Impact:** The Analytics team's release cadence is directly coupled to the Order
Management team's schema. Any schema migration in Order Management must be coordinated with
the Analytics team to avoid breaking dashboards and ML pipelines. This killed independent
delivery for both teams. When the Order DB is slow, analytics queries compete with
transactional workload, contributing to latency spikes during peak ordering periods. The
current arrangement is also an audit risk: the Analytics service has read access to
production transactional data outside any access control boundary defined by the domain.

**Observed:** `analytics-service` imports and uses `OrderRepository`, `OrderItemRepository`,
and `MemberAccountRepository` directly. Confirmed as a 14-month-old "temporary workaround"
now serving production dashboards and ML feature pipelines.

**Recommendation:**
1. Order Management and Loyalty publish domain events to Kafka (they partially do already)
2. Analytics materialises event-sourced read views from those events
3. Remove direct repository dependencies from `analytics-service`
4. Enforce the boundary with an ArchUnit rule so the workaround cannot reappear

**Candidate Fitness Function:** See [generated-archunit-tests.java](generated-archunit-tests.java) — Rule `FF-01`.

---

## Finding 2 — Kitchen Display Service Holds Direct Reference to Order Domain Repository

**Risk Level:** CRITICAL  
**EA Lens:** Lens 1 — Bounded Context Integrity  
**Governance Mode:** Enforced (Candidate)  
**Enforcement Mechanism:** ArchUnit  

**Business Impact:** Kitchen Display and Order Management cannot be deployed, scaled, or
replatformed independently. The Kitchen Display service's query pattern against the Order
DB contributed to read latency during peak periods (per codebase summary). If Order
Management migrates its data store (a likely scenario given a planned replatforming
roadmap), Kitchen Display will break silently at the repository interface level — not at
a published API boundary where the break would be visible and versioned.

**Observed:** `kitchen-display-service` imports `OrderRepository` directly and uses `Order`,
`OrderItem`, and `FulfillmentChannel` domain entities — seven cross-domain class references.

**Recommendation:**
1. Order Management publishes `OrderConfirmed` events to Kafka with all fields Kitchen Display needs
2. Kitchen Display subscribes and maintains its own `KitchenTicket` materialised from those events
3. Remove all `com.example.order.*` imports from `kitchen-display-service`
4. Enforce with ArchUnit and a package-level dependency rule

**Candidate Fitness Function:** See [generated-archunit-tests.java](generated-archunit-tests.java) — Rules `FF-02` and `FF-03`.

---

## Finding 3 — Order Service Synchronously Calls Loyalty, Kitchen Display, and Analytics

**Risk Level:** HIGH  
**EA Lens:** Lens 2 — Cross-Domain Communication Pattern  
**Governance Mode:** Advisory → Enforced (requires event schema design first)  
**Enforcement Mechanism:** ArchUnit (indirect — verify absence of direct HTTP client references in post-order flow), then Kafka consumer contract tests

**Business Impact:** This is the root cause of the Q3 2025 P1 incident where loyalty points
were not awarded during peak load. The Order service's SLO is being implicitly extended to
cover the Loyalty service's availability. When kitchen display acknowledgment is included in
the order confirmation flow, kitchen latency becomes order latency — these are different
SLOs owned by different teams.

More broadly: three teams (Loyalty, Kitchen Display, Analytics) cannot improve their own
reliability without negotiating with the Order Management team, because their consumption
path is inside Order Management's critical path.

**Observed:** `OrderCompletionService` makes synchronous REST POST calls to:
- `loyalty-service` (award points)
- `kitchen-display-service` (create ticket)
- `analytics-service` (push event for ingestion)

**Recommendation:**
1. Order Management emits `OrderCompleted` and `OrderConfirmed` events to Kafka
2. Loyalty, Kitchen Display, and Analytics each become independent consumers
3. Order Management no longer holds references to `LoyaltyServiceClient`, `KitchenDisplayClient`, or any analytics push client in its post-order flow
4. Add ArchUnit rule to verify no cross-domain HTTP clients exist in post-order application classes

**Note:** This cannot be fully enforced by ArchUnit alone — it requires Kafka consumer
contract tests and integration environment validation. ArchUnit enforces the absence of
the wrong dependencies; the presence of the right event publication requires contract testing.

**Candidate Fitness Function:** See [generated-archunit-tests.java](generated-archunit-tests.java) — Rule `FF-04`.

---

## Finding 4 — Delivery Orchestration Has No Anti-Corruption Layer: Partner SDKs in Domain Logic

**Risk Level:** HIGH  
**EA Lens:** Lens 3 — Anti-Corruption Layer for External Partners  
**Governance Mode:** Enforced (Candidate)  
**Enforcement Mechanism:** ArchUnit  

**Business Impact:** DoorDash and Uber Eats change their APIs and data models without
notice. When their SDK updates, the `DeliveryJob` domain entity breaks because it holds
a `DeliveryJobId` typed from the DoorDash SDK. Renegotiating a delivery partner contract
or adding a fourth partner (SkipTheDishes is already hand-rolled without ACL) requires
changes deep in the domain model, not just in the adapter. This is exactly the scenario
an ACL prevents.

**Observed:** DoorDash SDK classes (`com.doordash.sdk.model.*`) appear in:
- `DeliveryCoordinationService` (application layer) as method parameters
- `DeliveryJob` (domain entity) as a field type
- `PartnerRoutingService` (application) constructing partner-specific request objects

Uber Eats DTOs appear in `PartnerRoutingService` business logic branching.

**Recommendation:**
1. Define `DeliveryPartnerPort` interface in the application layer with internal model types
2. Move all `com.doordash.*` and `com.ubereats.*` references to `infrastructure.adapters` only
3. `DeliveryJob` domain entity must use only internal types
4. Add ArchUnit rule confining third-party delivery SDK imports to adapter packages

**Candidate Fitness Function:** See [generated-archunit-tests.java](generated-archunit-tests.java) — Rules `FF-05` and `FF-06`.

---

## Finding 5 — PII Appearing in Distributed Traces and Log Statements

**Risk Level:** HIGH  
**EA Lens:** Lens 5 — Observability Baseline; Lens 6 — Security and Data Governance  
**Governance Mode:** Enforced (Candidate) for ArchUnit; Immediate manual remediation for current violations  
**Enforcement Mechanism:** ArchUnit (class confinement) + SAST (log statement scanning)  

**Business Impact:** Customer email addresses and loyalty member IDs in Datadog traces are
accessible to anyone with Datadog read access — a significantly wider audience than those
with production database access. This is a data governance breach that may trigger
notification obligations under applicable privacy regulation depending on jurisdiction.
The phone number in order service logs creates a similar exposure.

**Observed:**
- `loyalty-service` emits `memberId` and `customerEmail` as Datadog trace span attributes
- `order-service` includes `customerPhone` in unmasked error log messages
- `payment-service` passes `CardLast4` in `OrderSummary` DTO consumed by non-PCI services

**Recommendation (immediate):**
1. Patch `loyalty-service` and `order-service` to remove PII from telemetry — treat as security incident, not backlog item
2. Add `CardLast4` removal from `OrderSummary` before it is exposed to non-PCI consumers
3. Add ArchUnit rule preventing PII-annotated classes from appearing in logging/observability utility classes
4. Evaluate `@PiiField` annotation strategy on domain entities and enforce via ArchUnit

**Candidate Fitness Function:** See [generated-archunit-tests.java](generated-archunit-tests.java) — Rules `FF-07` and `FF-08`.

---

## Finding 6 — DoorDash API Key Committed to Source Control

**Risk Level:** CRITICAL  
**EA Lens:** Lens 6 — Security and Data Governance  
**Governance Mode:** Immediate remediation required — not a fitness function matter  
**Enforcement Mechanism:** Secret rotation (immediate), detect-secrets pre-commit hook (preventive)  

**Business Impact:** Any person with read access to the git repository has the DoorDash API
credentials. If the key is used for order placement, a malicious actor could place or cancel
orders at scale. This also constitutes a violation of DoorDash's API terms of service and
could result in service suspension.

**Observed:** DoorDash API key present in `delivery-orchestration/src/main/resources/application.properties`.

**Recommendation:**
1. Rotate the key immediately and revoke the committed credential
2. Move to HashiCorp Vault injection (Standard 6 requirement)
3. Run `git filter-branch` or BFG to remove the secret from git history
4. Add `detect-secrets` pre-commit hook to all repositories as per Standard 8

**This is not a fitness function candidate — it requires immediate operational response.**

---

## Finding 7 — Order Service Contains Custom JWT Validation Logic

**Risk Level:** HIGH  
**EA Lens:** Lens 6 — Security and Data Governance  
**Governance Mode:** Enforced (Candidate)  
**Enforcement Mechanism:** ArchUnit (banned class usage)  

**Business Impact:** Custom JWT validation code is a known high-risk pattern. The order
service processes every customer order — a JWT validation flaw here could allow
unauthenticated order placement or session hijacking at scale. The platform-security-lib
has been reviewed and penetration-tested; `OrderAuthFilter` has not.

**Observed:** `order-service` contains custom JWT parsing in `OrderAuthFilter`, not using
`com.example.platform:platform-security-lib`.

**Recommendation:**
1. Replace `OrderAuthFilter` with the standard filter from `platform-security-lib`
2. Add ArchUnit rule banning custom JWT parsing classes and requiring platform-security-lib usage
3. Make this a blocker in the next security review cycle

**Candidate Fitness Function:** See [generated-archunit-tests.java](generated-archunit-tests.java) — Rule `FF-09`.

---

## Finding 8 — Five Services Have No Published API Contract

**Risk Level:** MEDIUM  
**EA Lens:** Lens 4 — API Contract Maturity  
**Governance Mode:** Advisory  
**Enforcement Mechanism:** API catalogue gate in CI (Spectral lint on OpenAPI spec); Pact broker in pipeline  

**Business Impact:** Without a published contract, consumers take a compile-time or runtime
dependency on implementation details. Breaking changes ship silently. The kitchen-display
and delivery-orchestration services are high-traffic integrations — any unversioned change
is a production incident waiting to happen.

**Observed:** `kitchen-display-service` has no OpenAPI spec. Four other services have gaps
in versioning, catalogue registration, or consumer contract coverage.

**Recommendation:**
1. Require OpenAPI 3.1 spec committed alongside the service as a CI gate (Spectral lint)
2. Register all event schemas in Confluent Schema Registry with `FULL_TRANSITIVE` compatibility
3. Add Pact tests for all synchronous integrations — starting with order → loyalty (highest incident history)

**Not ArchUnit.** API contract governance requires Spectral, Pact, and schema registry policy.

---

## Finding 9 — Legacy POS Integration Running EOL Spring Boot 2.5

**Risk Level:** MEDIUM  
**EA Lens:** Lens 7 — Technology Stack Compliance  
**Governance Mode:** Advisory  
**Enforcement Mechanism:** Dependency version check in Maven/Gradle enforcer plugin  

**Business Impact:** Spring Boot 2.5 reached end of support in May 2023. No security patches
are being backported. Any vulnerability discovered in Spring Boot 2.5 or its dependency tree
will not be fixed. POS integration is an external-facing service handling transaction
initiation — a high-value attack target.

**Recommendation:** Schedule upgrade to Spring Boot 3.x in the next sprint cycle. This is
a compliance obligation, not a discretionary improvement. Add a Maven Enforcer plugin rule
to the platform BOM that rejects EOL Spring Boot versions as a CI gate.

---

## Risk Summary

| Finding | Risk | Mode | Mechanism |
|---------|------|------|-----------|
| Analytics accessing domain repositories directly | CRITICAL | Enforced Candidate | ArchUnit |
| Kitchen Display accessing Order repository directly | CRITICAL | Enforced Candidate | ArchUnit |
| DoorDash API key in source control | CRITICAL | Immediate action | Secret rotation |
| Synchronous post-order calls to Loyalty, Kitchen, Analytics | HIGH | Advisory → Enforced | ArchUnit + Kafka contracts |
| Partner SDKs leaking beyond ACL in Delivery Orchestration | HIGH | Enforced Candidate | ArchUnit |
| PII in traces and logs | HIGH | Enforced Candidate + Immediate patch | ArchUnit + SAST |
| Custom JWT validation in Order service | HIGH | Enforced Candidate | ArchUnit |
| Missing API contracts (5 services) | MEDIUM | Advisory | Spectral + Pact |
| EOL Spring Boot in POS integration | MEDIUM | Advisory | Maven Enforcer |
