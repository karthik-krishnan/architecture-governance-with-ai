# Recommended Fitness Functions — QSR Digital Platform

**Produced by:** Architecture Fitness Function Advisor  
**Status:** Advisory — all items require architect validation before commitment to CI  
**Date:** 2026-Q1

---

> **Reading this document**
>
> Fitness functions here are in two tiers:
>
> **Tier 1 — Automatable via ArchUnit:** These rules operate on compiled bytecode. Once
> committed to a service's test suite and wired into CI, they enforce themselves on every
> pull request with no human intervention.
>
> **Tier 2 — Requires complementary tooling:** These rules address concerns ArchUnit cannot
> reach — API contract maturity, runtime call patterns, secret handling, SLO compliance.
> They require Spectral, Pact, detect-secrets, or observability policy configuration.
>
> Both tiers are fitness functions. The distinction is tooling, not importance.

---

## Tier 1 — ArchUnit-Enforceable Rules

### FF-01: Analytics Must Not Access Domain Repositories Directly

**Enforces:** Standard 1 (Bounded Context Integrity)  
**Target services:** `analytics-service`  
**Governance mode:** Enforced Candidate — promote after architect sign-off  

**Rule in plain English:** The Analytics service is a consumer of domain events. It must
materialise its own views from those events. It may not hold a direct reference to any
domain's repository interface or JPA entity outside its own domain.

**ArchUnit rule:** See [generated-archunit-tests.java](generated-archunit-tests.java) — `FF_01`

**Promotion criteria before enforcing:**
- [ ] Order Management emits `OrderCompleted` / `OrderItemised` events to Kafka
- [ ] Analytics has migrated at least the order dashboards to event-sourced views
- [ ] Architect confirms no legitimate read-only exception applies

---

### FF-02: Kitchen Display Must Not Access Order Domain Classes

**Enforces:** Standard 1 (Bounded Context Integrity)  
**Target services:** `kitchen-display-service`  
**Governance mode:** Enforced Candidate  

**Rule in plain English:** Kitchen Display derives its operational view from `OrderConfirmed`
events. It must own its own `KitchenTicket` model. It must not import `Order`, `OrderItem`,
`FulfillmentChannel`, or any other class from the Order domain.

**ArchUnit rule:** See `FF_02` in generated-archunit-tests.java

**Promotion criteria:**
- [ ] Order Management publishes `OrderConfirmed` event with all Kitchen Display required fields
- [ ] Kitchen Display has migrated ticket creation to event subscription
- [ ] Kitchen Display `TicketCreationService` no longer references any `com.example.order.*` class

---

### FF-03: No Service May Directly Access Another Domain's Repository

**Enforces:** Standard 1 (Bounded Context Integrity)  
**Target services:** All — platform-wide rule  
**Governance mode:** Enforced Candidate — highest priority for enforcement  

**Rule in plain English:** Repository interfaces and JPA entities are implementation details
of the domain that owns them. No class in any other domain's package hierarchy may reference
them. This is the "you may not read our database" rule encoded as a test.

**ArchUnit rule:** See `FF_03` in generated-archunit-tests.java

**Promotion criteria:**
- [ ] Analytics direct repo access remediated (FF-01)
- [ ] Kitchen Display direct repo access remediated (FF-02)
- [ ] No other services found with cross-domain repo references (scan complete)

---

### FF-04: Post-Order Cross-Domain Calls Must Route Through Integration Ports, Not Direct HTTP Clients

**Enforces:** Standard 2 (Asynchronous Integration for Cross-Domain State Changes)  
**Target services:** `order-service`  
**Governance mode:** Advisory — requires architecture discussion on event schema design first  

**Rule in plain English:** After an order is completed, the Order service must not hold
direct HTTP client references to Loyalty, Kitchen Display, or Analytics services in its
application layer. Post-order operations must be decoupled through events or a defined
integration port that does not create a runtime dependency on the consuming service's
availability.

**ArchUnit rule:** See `FF_04` in generated-archunit-tests.java

**Promotion criteria:**
- [ ] `OrderCompleted` and `OrderConfirmed` event schemas agreed with consuming teams
- [ ] Events published to Kafka in a backward-compatible schema
- [ ] Consuming services migrated and validated in staging
- [ ] Direct HTTP client references removed from order application layer

---

### FF-05: Delivery Partner SDKs Must Not Appear in Domain or Application Layers

**Enforces:** Standard 3 (Anti-Corruption Layer for External Partners)  
**Target services:** `delivery-orchestration-service`  
**Governance mode:** Enforced Candidate  

**Rule in plain English:** `com.doordash.*`, `com.ubereats.*`, and any other third-party
delivery partner SDK package may only appear in `infrastructure.adapters`. The domain entity
`DeliveryJob` must use only internal model types.

**ArchUnit rule:** See `FF_05` in generated-archunit-tests.java

**Promotion criteria:**
- [ ] `DeliveryPartnerPort` interface defined in application layer with internal types
- [ ] `DeliveryJob` domain entity cleaned of SDK field types
- [ ] All adapter logic moved to `infrastructure.adapters`
- [ ] Regression tested: all three delivery partners (DoorDash, Uber Eats, Skip) validated in staging

---

### FF-06: No Unapproved HTTP Client Libraries in Application or Domain Layers

**Enforces:** Standard 7 (Technology Stack Compliance)  
**Target services:** `order-service`, `delivery-orchestration-service`, any service using OkHttp or RestTemplate  
**Governance mode:** Enforced Candidate  

**Rule in plain English:** `okhttp3.*` and `org.springframework.web.client.RestTemplate`
must not be imported in any application or domain layer class. New code must use
`org.springframework.web.reactive.function.client.WebClient`.

**ArchUnit rule:** See `FF_06` in generated-archunit-tests.java

---

### FF-07: PII-Annotated Fields Must Not Appear in Observability Utility Classes

**Enforces:** Standard 5 (Observability Baseline — PII prohibition), Standard 6 (Security)  
**Target services:** All  
**Governance mode:** Enforced Candidate  
**Note:** Requires adoption of `@PiiField` annotation on domain entity fields (prerequisite)  

**Rule in plain English:** Any field annotated with `@PiiField` (or carrying a type that
contains PII by naming convention) must not be referenced in logging utility classes,
metrics emission, or trace span attribute builders. This prevents PII from reaching
Datadog, Splunk, or any other observability tooling.

**ArchUnit rule:** See `FF_07` in generated-archunit-tests.java

**Promotion criteria:**
- [ ] `@PiiField` annotation adopted on domain entities across at least Order and Loyalty domains
- [ ] Logging utility classes identified and listed in the rule scope
- [ ] Immediate patches to loyalty-service and order-service applied (PII already in prod traces)

---

### FF-08: Custom Security Libraries Banned — Platform Security Lib Required

**Enforces:** Standard 6 (Security — approved library requirement)  
**Target services:** `order-service` (confirmed); scan all services before enforcement  
**Governance mode:** Enforced Candidate  

**Rule in plain English:** No service may implement its own JWT parsing, token validation,
or OAuth2 client logic. All security handling must use `com.example.platform.security.*`
from `platform-security-lib`. Classes with names matching custom authentication patterns
(`*AuthFilter`, `*JwtParser`, `*TokenValidator`) must extend or delegate to the platform
library, not implement validation independently.

**ArchUnit rule:** See `FF_08` in generated-archunit-tests.java

---

## Tier 2 — Complementary Tooling (Not ArchUnit)

### CF-01: All Services Must Have an OpenAPI 3.1 Specification in CI

**Enforces:** Standard 4 (API Contract Maturity)  
**Tool:** Spectral (API linter) in CI pipeline  
**Governance mode:** Advisory — introduce as warning gate first, then blocking  

**Rule:** Spectral ruleset committed to the governance repository. CI job runs `spectral lint`
against every service's `openapi.yaml`. Fails if the spec is absent or violates the
enterprise ruleset (versioned paths, no inline schema references, required fields present).

**Spectral rule example:**
```yaml
rules:
  path-must-be-versioned:
    message: "All API paths must start with /v{n}/"
    given: "$.paths[*]~"
    then:
      function: pattern
      functionOptions:
        match: "^/v[0-9]+"
```

---

### CF-02: Consumer-Driven Contract Tests for All Synchronous Integrations

**Enforces:** Standard 4 (API Contract Maturity — Pact requirement)  
**Tool:** Pact broker in CI pipeline  
**Governance mode:** Advisory  

**Rule:** Every synchronous service-to-service integration must have a Pact consumer contract
published in the Pact broker. Producer verification runs in the producer's CI pipeline.
A breaking change in the producer fails the producer's build if a consumer contract exists.

**Priority integrations to add Pact tests first:**
1. `order-service` → `loyalty-service` (highest incident history)
2. `order-service` → `payment-service` (business-critical)
3. `delivery-orchestration` → delivery partner adapters (external change risk)

---

### CF-03: Kafka Event Schemas Must Be Registered with FULL_TRANSITIVE Compatibility

**Enforces:** Standard 4 (API Contract Maturity — event schema governance)  
**Tool:** Confluent Schema Registry + CI compatibility check  
**Governance mode:** Advisory  

**Rule:** Every Kafka event type produced by a service must have its Avro or JSON Schema
registered in the Confluent Schema Registry with `FULL_TRANSITIVE` compatibility. A CI
check (`schema-registry-maven-plugin`) verifies that each schema change is backward and
forward compatible before merge.

---

### CF-04: Secrets Must Not Appear in Source Control

**Enforces:** Standard 6 (Security — secrets management)  
**Tool:** detect-secrets (pre-commit hook + CI scan)  
**Governance mode:** Enforced — immediate, platform-wide  

**Rule:** `detect-secrets` baseline committed to each repository. Pre-commit hook blocks
commits containing high-entropy strings matching credential patterns. CI job re-runs the
scan and fails the build on any new secret detected.

**Immediate action:** Rotate DoorDash API key, run BFG on delivery-orchestration repo history.

---

### CF-05: Business-Critical Paths Must Emit Audit Events

**Enforces:** Standard 5 (Observability Baseline — audit event requirement)  
**Tool:** Kafka consumer contract test (verifies audit event emitted) + observability SLO  
**Governance mode:** Advisory  

**Rule:** Order placement, payment authorisation, and loyalty redemption operations must emit
a corresponding event to the `platform.audit` Kafka topic. Verified in integration tests by
asserting the audit event is present after each operation.

**Currently missing:** Payment Processing emits no audit events. This is a regulatory gap.

---

## Fitness Function Priority Matrix

| ID | Description | Risk | Mode | Tool | Estimated Effort |
|----|-------------|------|------|------|-----------------|
| FF-03 | No cross-domain repo access | CRITICAL | Enforced Candidate | ArchUnit | Medium (after remediation) |
| FF-05 | Delivery SDK confined to adapters | HIGH | Enforced Candidate | ArchUnit | Medium |
| FF-08 | Custom security libs banned | HIGH | Enforced Candidate | ArchUnit | Low |
| CF-04 | Secrets detection in CI | CRITICAL | Enforced — Immediate | detect-secrets | Low |
| FF-06 | Unapproved HTTP clients banned | MEDIUM | Enforced Candidate | ArchUnit | Low |
| FF-07 | PII out of observability classes | HIGH | Enforced Candidate | ArchUnit | Medium (needs @PiiField) |
| FF-01 | Analytics off domain repositories | CRITICAL | Enforced (after migration) | ArchUnit | High (migration) |
| FF-02 | Kitchen Display off Order domain | CRITICAL | Enforced (after migration) | ArchUnit | High (migration) |
| FF-04 | Post-order calls via events not HTTP | HIGH | Advisory → Enforced | ArchUnit + Kafka | High (event design) |
| CF-01 | OpenAPI specs in CI | MEDIUM | Advisory | Spectral | Medium |
| CF-02 | Pact tests for sync integrations | MEDIUM | Advisory | Pact | Medium |
| CF-03 | Event schema registry | MEDIUM | Advisory | Schema Registry | Medium |
| CF-05 | Audit events on critical paths | MEDIUM | Advisory | Kafka + contracts | Medium |
