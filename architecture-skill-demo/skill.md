---
name: architecture-fitness-function-advisor
description: Use when reviewing a Java/Spring-based service platform for enterprise architecture governance gaps. Evaluates bounded context integrity, cross-domain coupling, event-driven compliance, API contract maturity, observability posture, security standards, and technology stack compliance. Operates at domain and platform level — not at individual class or method design level. Produces advisory findings and ArchUnit/policy-as-code candidates for architect review.
---

# Architecture Fitness Function Advisor

## Purpose

This skill guides a structured Enterprise Architecture review and produces:

- **Risk findings** framed at the domain and platform level
- **Recommended fitness functions** — advisory (AI-identified) and enforced (CI-blocking)
- **ArchUnit test candidates** for rules that are automatable via bytecode analysis
- **Pointers to complementary tooling** for rules ArchUnit cannot enforce
- **Business impact framing** for every finding — what fails for customers, the business, or regulators if this is ignored

> **Scope boundary:** This skill operates at the city-planner level. It reasons about domains,
> bounded contexts, platform contracts, and cross-cutting standards. It does not evaluate
> whether a specific controller calls a specific repository — that is a code-design concern
> owned by the development team and their tech lead.

---

## How to Use This Skill

**Inputs required (provide as context or attached documents):**

1. **Service / Platform Description** — what bounded contexts exist, what each owns, how they interact today
2. **Architecture Standards Document** — the enterprise's stated rules, reference architecture, approved patterns
3. **Codebase Summary or Scan Output** — package structure, key dependencies, identified cross-package imports, flagged patterns

**Invoke with:**
> "Review [service/platform name] against [architecture-standards.md] using the Architecture Fitness Function Advisor skill. Identify gaps, risks, and candidate fitness functions."

**Output produced:** See [Output Format](#output-format) below.

---

## Evaluation Lenses

Evaluate the architecture across all seven lenses. Each lens maps to one or more governance mechanisms.

---

### Lens 1 — Bounded Context Integrity

**EA concern:** Each domain owns its data and its behaviour. Other domains interact only through published APIs or domain events — never by importing internal domain classes, sharing a database schema, or calling each other's repositories.

**What to look for:**
- Cross-domain class imports (e.g., `OrderService` importing a class from `com.example.loyalty.domain`)
- Shared database schemas or tables across bounded contexts
- Repository classes from one domain referenced in another domain's service
- Domain logic duplicated across services because one cannot import another's entities
- Aggregates whose identity is defined by another domain (no canonical ID ownership)

**ArchUnit enforceable:** Package import boundaries between top-level domain namespaces.
```
noClasses().that().resideInAPackage("com.example.ordering..")
    .should().dependOnClassesThat().resideInAPackage("com.example.loyalty..")
```

**Not ArchUnit:** Database schema isolation (enforce via DB migration policy, schema registry), API contract ownership (enforce via API gateway policy).

---

### Lens 2 — Cross-Domain Communication Pattern

**EA concern:** Cross-domain state changes must flow through events or well-defined API contracts. Synchronous point-to-point calls between domains create runtime coupling — if one domain is unavailable, dependent domains fail with it.

**What to look for:**
- Synchronous HTTP/RPC calls between domain services for state-changing operations (order placed → loyalty points awarded via direct call)
- Missing event publication: domain events that other contexts need are not being emitted
- Response objects from one domain carried deep into another domain's logic
- No circuit breaker, retry, or fallback strategy on cross-domain calls that do exist
- Event schemas that expose internal domain implementation details (anemic event payloads vs. rich domain events)

**ArchUnit enforceable:** Verify that cross-domain calls are routed through defined integration ports (e.g., classes in `..integration..` or `..events..` packages), not called directly from domain or application layers.

**Not ArchUnit:** Runtime call patterns, message broker topology, circuit breaker configuration, event schema governance (use schema registry + compatibility checks).

---

### Lens 3 — Anti-Corruption Layer for External Partners

**EA concern:** Third-party integrations (delivery partners, payment processors, POS vendors, franchise management platforms) must be encapsulated behind Anti-Corruption Layers. Their SDKs, data models, and protocols must not leak into domain or application logic.

**What to look for:**
- Third-party SDK package imports (`com.doordash`, `com.squareup`, vendor-specific classes) appearing in service, application, or domain layers
- External partner data models mapped directly to domain entities without a translation layer
- Business logic that branches on third-party provider identity (`if provider == "UberEats"`) in domain or application code
- No versioning strategy for partner API changes — tight coupling to a specific API version

**ArchUnit enforceable:**
```
noClasses().that().resideInAPackage("..domain..").or().resideInAPackage("..application..")
    .should().dependOnClassesThat().resideInAPackage("com.doordash..")
    .orShould().dependOnClassesThat().resideInAPackage("com.ubereats..")
```

**Not ArchUnit:** Adapter pattern completeness, partner SDK version governance, ACL contract testing.

---

### Lens 4 — API Contract Maturity

**EA concern:** Services must publish versioned, machine-readable API contracts. Consumers must not depend on implementation details. Breaking changes must be versioned. The platform must be able to evolve services independently.

**What to look for:**
- No OpenAPI / AsyncAPI specification committed alongside the service
- URL paths without version identifiers (`/orders` instead of `/v1/orders`)
- No consumer-driven contract tests (e.g., Pact) between producer and consumer services
- Response bodies that expose internal field names or database column structures
- Breaking changes shipped without version bumps (detected retrospectively via contract test failures)
- Missing deprecation headers or sunset dates on older API versions

**ArchUnit enforceable:** Limited — can verify presence of OpenAPI annotation classes on controller methods.

**Primary enforcement:** API linting (Spectral rules on OpenAPI specs), API gateway policy, Pact broker in CI pipeline.

---

### Lens 5 — Observability Baseline

**EA concern:** Every service must emit standard metrics, distributed traces, and structured logs sufficient to diagnose incidents, measure SLOs, and audit business-critical operations — without granting access to production databases.

**What to look for:**
- No distributed trace context propagation at service entry points (missing `@Traced` / Micrometer / OpenTelemetry instrumentation)
- PII fields (`customerEmail`, `cardNumber`, `loyaltyId`) appearing in log statements, metrics labels, or trace span attributes
- No standard health (`/actuator/health`) or readiness endpoint
- Business-critical paths (order placement, payment authorisation, loyalty redemption) with no SLO instrumentation
- Logs written as unstructured strings rather than structured JSON — prevents log aggregation and alerting

**ArchUnit enforceable:**
- PII-annotated classes must not appear in logging utility classes
- Verify observability annotations on defined entry point classes

**Primary enforcement:** Observability SLOs (alert if traces missing for critical paths), log schema validation in pipeline, APM coverage reports.

---

### Lens 6 — Security and Data Governance

**EA concern:** Service-to-service authentication must use the approved mechanism. PII and payment data must be handled according to the data classification policy. No team may implement their own authentication, encryption, or token validation logic.

**What to look for:**
- Custom JWT parsing or signature validation code outside the approved security library
- PII data classes (`CustomerProfile`, `PaymentInstrument`) used in contexts not marked as PII-safe
- Service-to-service calls without mutual TLS or token-based authentication
- Secrets or credentials present in configuration files (not injected from a secrets manager)
- Data retention: events or logs carrying full PII beyond the required retention window

**ArchUnit enforceable:**
- Banned class usage: homegrown JWT libraries, deprecated security packages
- PII classes confined to approved handling packages

**Primary enforcement:** SAST scanning (SonarQube, Checkmarx), secrets detection (Trufflehog, GitGuardian), dependency vulnerability scanning (OWASP Dependency-Check, Dependabot).

---

### Lens 7 — Technology Stack Compliance

**EA concern:** Teams must use platform-approved libraries and frameworks. Unapproved choices fragment the support model, create security blind spots, and introduce license risk.

**What to look for:**
- HTTP clients not on the approved list (e.g., using OkHttp directly when the standard is Spring WebClient)
- Multiple logging frameworks co-existing in the same service (SLF4J bridging to Log4j1 and Logback simultaneously)
- Deprecated or End-of-Life Spring Boot / Java versions
- Database migration tools inconsistent with the platform standard (Flyway vs. Liquibase mixed across services)
- Direct JDBC usage in domains that should use the standard repository abstraction

**ArchUnit enforceable:**
```
noClasses().should().dependOnClassesThat()
    .resideInAPackage("okhttp3..") // banned — use Spring WebClient
    .because("Platform standard HTTP client is Spring WebClient per ADR-017")
```

**Primary enforcement:** Dependency governance (Gradle/Maven enforcer plugin), bill-of-materials (BOM) enforcement, SCA scanning.

---

## Output Format

For each finding, produce this structure:

```
### Finding: [Short descriptive title]

**Risk Level:** Critical | High | Medium | Low
**EA Lens:** [Lens number and name]
**Business Impact:** [What fails for customers, the business, or regulators if unaddressed]
**Observed:** [What was found in the codebase summary or service description]
**Recommendation:** [What the architecture team should do]
**Governance Mode:** Advisory | Enforced
**Enforcement Mechanism:** ArchUnit | API Linting | Security Scanning | Observability SLO | Policy-as-Code | Manual Review

#### Candidate Fitness Function  ← only when ArchUnit-enforceable
[Java code block with @ArchTest rule]
```

---

## Advisory vs. Enforced

| Mode | Meaning | Who Acts |
|------|---------|----------|
| **Advisory** | The skill identified a risk pattern. Requires architect validation before action. Does not block CI. | Architect reviews, decides whether to promote to Enforced |
| **Enforced** | Rule is committed as an automated check and blocks builds or deployments on violation. | CI/CD pipeline, no human required per PR |

**The promotion path:**

```
AI identifies pattern (Advisory)
        │
        ▼
Architect validates: applies to our context? correct scope? false-positive risk?
        │
        ▼
Rule authored and committed to governance repo
        │
        ▼
CI configured to execute rule on every merge (Enforced)
        │
        ▼
Violation found → build blocked → team fixes before merge
```

New findings always start as Advisory. Promotion to Enforced requires explicit architect sign-off. This prevents the governance layer from becoming noise that engineers learn to suppress.

---

## What This Skill Is Not

| What it is not | What to use instead |
|----------------|---------------------|
| A SAST tool | SonarQube, Checkmarx, Semgrep |
| A dependency vulnerability scanner | OWASP Dependency-Check, Dependabot, Snyk |
| An API linter | Spectral (OpenAPI rules), Redocly |
| A secrets detector | Trufflehog, GitGuardian, detect-secrets |
| An observability platform | Datadog, New Relic, Grafana |
| A schema registry | Confluent Schema Registry, AWS Glue |
| A runtime policy engine | OPA/Gatekeeper, AWS SCPs |

This skill accelerates the **discovery and authoring** of governance controls. The controls themselves live in code, pipeline configuration, and policy documents — and are enforced by automated tools running in CI/CD. The skill is the beginning of the governance loop, not the loop itself.
