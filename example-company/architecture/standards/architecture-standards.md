# Enterprise Architecture Standards — Example Company Digital Platform

**Version:** 2.4  
**Owner:** Enterprise Architecture Council  
**Last reviewed:** Q1 2026  
**Applies to:** All services on the Example Company Digital Platform

---

## Standard 1 — Bounded Context Integrity

Each bounded context is the **sole authority** over its own data. No other domain may:

- Import domain entity classes from another bounded context
- Query another domain's database schema directly, including read replicas
- Call another domain's internal (non-published) APIs
- Store a copy of another domain's core entity data except via published integration events

**Rationale:** Direct coupling between domain data models makes it impossible to evolve,
replatform, or scale domains independently. It was a primary cause of the 2022 loyalty
outage, where a schema change in Order Management broke the Loyalty service.

**Measurement:** The percentage of cross-domain dependencies routed through published
APIs or events (target: 100% by end of 2026).

---

## Standard 2 — Asynchronous Integration for Cross-Domain State Changes

Any operation that changes state in more than one domain **must** be implemented as:

1. The originating domain completes its own transaction and publishes a domain event to Kafka
2. Consuming domains subscribe to the event and process it independently
3. No originating domain waits for consuming domain confirmation (fire-and-forget at the integration layer)

**Synchronous calls are acceptable only for:**
- Read operations where the calling domain needs data before it can proceed (e.g., availability check)
- Request/response interactions with strict consistency requirements (e.g., payment authorisation)

**Synchronous calls are not acceptable for:**
- Post-order operations: loyalty points award, analytics ingestion, kitchen ticket creation
- Any operation where the consuming domain's failure should not affect the producing domain

**Rationale:** The Loyalty team cannot serve customers when the Order service is degraded.
This coupling transfers the Order service's availability SLO onto the Loyalty SLO, which is
not owned or staffed by the same team.

---

## Standard 3 — Anti-Corruption Layers for External Partners

All integrations with third-party systems (delivery partners, payment processors, POS
vendors, franchise management platforms) **must** be encapsulated behind an Anti-Corruption
Layer (ACL):

- The ACL translates between the external partner's model and the internal domain model
- No external partner SDK class, data model, or protocol detail may appear outside the `infrastructure.adapters` package
- The ACL must be independently versioned and testable in isolation
- Partner-specific branching logic (`if partner == DoorDash`) must live in the ACL, not in domain or application logic

**Approved delivery partner integration pattern:**
```
DeliveryOrchestrationService (application)
    └── DeliveryPartnerPort (interface, application layer)
            └── DoorDashAdapter (infrastructure.adapters)
            └── UberEatsAdapter (infrastructure.adapters)
            └── SkipAdapter (infrastructure.adapters)
```

---

## Standard 4 — API Contract Standards

All service APIs (REST and event schemas) must comply with:

| Requirement | Standard |
|-------------|----------|
| REST API specification | OpenAPI 3.1 committed to the API catalogue |
| URL versioning | Major version in path prefix: `/v{n}/resource` |
| Breaking change policy | New major version; old version supported for minimum 6 months with sunset header |
| Event schema registry | All Kafka event schemas registered in Confluent Schema Registry with FULL_TRANSITIVE compatibility |
| Consumer-driven contracts | Pact tests required for all synchronous service-to-service integrations |
| Internal vs external | Internal APIs not exposed via Kong gateway; external APIs require API gateway policy |

---

## Standard 5 — Observability Baseline

Every service in production must emit:

| Signal | Requirement |
|--------|-------------|
| Distributed traces | W3C Trace Context propagated on all inbound and outbound calls; minimum 10% sample rate, 100% on errors |
| Structured logs | JSON format, mandatory fields: `traceId`, `spanId`, `serviceId`, `environment`, `severity` |
| Metrics | RED metrics (Rate, Errors, Duration) on all public endpoints; emitted to Datadog |
| Health endpoints | `/actuator/health/liveness` and `/actuator/health/readiness` |
| Business events | Order placement, payment authorisation, loyalty redemption must emit audit events to the audit Kafka topic |

**PII in telemetry is prohibited.** Customer email addresses, loyalty IDs, card numbers, or
any field classified as PII under the data classification policy must not appear in:
- Log messages (structured fields or free text)
- Trace span attributes
- Metric label values
- Alert notification bodies

---

## Standard 6 — Security

| Area | Requirement |
|------|-------------|
| Service-to-service auth | OAuth2 client credentials flow via Keycloak; network trust alone is not sufficient |
| Customer-facing auth | OAuth2 PKCE flow; JWT validation via the approved `platform-security-lib` only |
| Secrets management | All credentials injected via HashiCorp Vault; no secrets in config files, environment variables, or source code |
| PCI-DSS boundary | Only the Payment Processing service may handle card data; all other services must use a token reference |
| Custom crypto | Prohibited — use platform-approved libraries only |
| Approved security library | `com.example.platform:platform-security-lib` (JWT validation, OAuth client, audit logging) |

---

## Standard 7 — Approved Technology Stack

| Category | Approved | Not Approved |
|----------|----------|--------------|
| HTTP client (outbound) | Spring WebClient, Feign (with resilience4j) | OkHttp (direct), Apache HttpClient (direct), RestTemplate (new code) |
| Messaging | Apache Kafka via `spring-kafka` | RabbitMQ, SQS (without platform wrapper), direct socket messaging |
| Database access | Spring Data JPA, Spring Data JDBC | Native JDBC in domain/application layers, raw Hibernate session |
| Service-to-service resilience | Resilience4j (circuit breaker, retry, bulkhead) | Hystrix (EOL), custom retry loops |
| Logging | SLF4J + Logback (via platform logging BOM) | Log4j 1.x, System.out.println |
| Tracing | Micrometer Tracing + OpenTelemetry exporter | Manual span management, vendor-specific agents only |
| Build | Maven 3.8+ or Gradle 8+ with platform BOM | Ant, custom build scripts |

**Platform BOM:** All services must import `com.example.platform:platform-bom` to ensure
aligned dependency versions. Version overrides require EA Council approval.

---

## Standard 8 — CI/CD Quality Gates

Every service pipeline must include the following gates before merge to main:

| Gate | Tool | Failure action |
|------|------|----------------|
| Architecture fitness functions | ArchUnit (committed to service repo) | Block merge |
| Dependency vulnerability scan | OWASP Dependency-Check (CVSS ≥ 7: fail) | Block merge |
| Static analysis | SonarQube (quality gate: no new critical issues) | Block merge |
| API contract tests | Pact broker verification | Block merge |
| Secrets detection | detect-secrets pre-commit + CI scan | Block merge |
| Container image scan | Trivy (critical CVEs: fail) | Block merge |
| Performance baseline | k6 smoke test on staging | Advisory (alert only) |

Architecture fitness functions are the first gate. They run on compiled bytecode and
complete in under 5 seconds — there is no argument for skipping them.
