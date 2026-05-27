# Current Codebase Summary — QSR Digital Platform

**Generated:** 2026-Q1 Architecture Review  
**Method:** Automated dependency scan (jQAssistant) + manual review of flagged packages  
**Scope:** 8 bounded context services, ~340,000 lines of Java

---

## Cross-Domain Import Analysis

The following cross-domain class imports were detected. Each represents a direct compile-time
dependency between bounded contexts — a potential violation of Standard 1.

| From Service | Imported Package | Count | Severity |
|--------------|-----------------|-------|----------|
| `order-service` | `com.example.loyalty.domain` | 3 classes | HIGH |
| `order-service` | `com.example.inventory.domain` | 1 class | MEDIUM |
| `kitchen-display-service` | `com.example.order.domain` | 7 classes | HIGH |
| `analytics-service` | `com.example.order.infrastructure.repository` | 2 repository interfaces | CRITICAL |
| `analytics-service` | `com.example.loyalty.infrastructure.repository` | 1 repository interface | CRITICAL |
| `delivery-orchestration` | `com.doordash.sdk.model` | 14 classes | HIGH |
| `delivery-orchestration` | `com.ubereats.client.dto` | 9 classes | HIGH |

**Detail — order-service importing loyalty domain:**
```
com.example.order.application.OrderCompletionService
  → com.example.loyalty.domain.MemberAccount        (field type in response builder)
  → com.example.loyalty.domain.PointsCalculation    (used to pre-calculate display points)
  → com.example.loyalty.api.LoyaltyServiceClient    (direct HTTP client, not via event)
```

**Detail — kitchen-display-service importing order domain:**
```
com.example.kitchen.application.TicketCreationService
  → com.example.order.domain.Order                  (full entity, not a published DTO)
  → com.example.order.domain.OrderItem              (full entity)
  → com.example.order.domain.FulfillmentChannel     (enum from order domain)
  → com.example.order.infrastructure.repository.OrderRepository  (direct repo access — CRITICAL)
```

**Detail — analytics-service importing repositories:**
```
com.example.analytics.pipeline.OrderDataLoader
  → com.example.order.infrastructure.repository.OrderRepository
  → com.example.order.infrastructure.repository.OrderItemRepository
com.example.analytics.pipeline.LoyaltyDataLoader
  → com.example.loyalty.infrastructure.repository.MemberAccountRepository
```
Note: Analytics team confirmed this was introduced as a "temporary workaround" 14 months ago.
The workaround is now the production data path for three dashboards and one ML feature pipeline.

---

## External Partner SDK Leakage

The following third-party SDK classes appear outside the `infrastructure.adapters` package —
a violation of Standard 3 (Anti-Corruption Layer).

**delivery-orchestration-service:**
```
com.example.delivery.application.DeliveryCoordinationService
  → com.doordash.sdk.model.OrderPayload          (used as method parameter)
  → com.doordash.sdk.model.DeliveryStatusUpdate  (used in status handling logic)

com.example.delivery.domain.DeliveryJob
  → com.doordash.sdk.model.DeliveryJobId         (used as field type — domain entity polluted)

com.example.delivery.application.PartnerRoutingService
  → com.ubereats.client.dto.UberEatsOrderRequest (constructed here, not in adapter)
  → com.ubereats.client.dto.UberEatsOrderStatus  (used in business logic branching)
```

---

## Synchronous Cross-Domain State Changes

The following synchronous calls trigger state changes in consuming domains — violating
Standard 2 for post-order operations:

| Calling Service | Called Service | Operation | Call Type | Standard Violation |
|-----------------|----------------|-----------|-----------|-------------------|
| `order-service` | `loyalty-service` | Award points on order completion | Synchronous REST POST | Yes — Standard 2 |
| `order-service` | `kitchen-display-service` | Create kitchen ticket on order confirmation | Synchronous REST POST | Yes — Standard 2 |
| `order-service` | `analytics-service` | Push order event for ingestion | Synchronous REST POST | Yes — Standard 2 |

**Impact observed:**
- Loyalty points not awarded during Order service peak load (P1 incident, Q3 2025) — root cause: synchronous call timed out; order completed but loyalty event was lost
- Kitchen tickets delayed by 800ms during lunch peak because order confirmation waits for kitchen-display acknowledgment
- Analytics dashboard lags during high-volume periods because the synchronous push becomes a back-pressure bottleneck

---

## Observability Gaps

| Service | Missing | Risk |
|---------|---------|------|
| `payment-service` | W3C trace context not propagated on outbound calls | Payment failures cannot be correlated to upstream order traces |
| `loyalty-service` | `memberId` and `customerEmail` emitted as Datadog trace span attributes | PII in observability tooling — compliance risk |
| `order-service` | `customerPhone` appears in error log messages (unmasked) | PII in logs — compliance risk |
| `delivery-orchestration` | No structured logging — plain `logger.info(string)` throughout | Cannot aggregate or alert on delivery failures |
| `kitchen-display-service` | No `/actuator/health/readiness` endpoint | Cannot distinguish application startup from availability |
| All services | No audit events emitted to the audit Kafka topic for business-critical operations | Regulatory gap — cannot reconstruct order/payment audit trail without DB access |

---

## Security Findings

| Service | Finding | Severity |
|---------|---------|---------|
| `order-service` | Custom JWT parsing code in `OrderAuthFilter` — not using `platform-security-lib` | HIGH |
| `delivery-orchestration` | DoorDash API key stored in `application.properties`, committed to git | CRITICAL |
| `kitchen-display-service` | Service-to-service calls use internal network trust, no OAuth2 token | MEDIUM |
| `payment-service` | `CardLast4` field present in `OrderSummary` DTO used by non-PCI services | HIGH |

---

## Technology Stack Violations

| Service | Violation | Standard Ref |
|---------|-----------|-------------|
| `order-service` | Uses `RestTemplate` for outbound calls to Loyalty service | Standard 7 (use WebClient) |
| `delivery-orchestration` | Uses OkHttp directly for Uber Eats calls | Standard 7 (use WebClient) |
| `legacy-pos-integration` | Spring Boot 2.5 (EOL May 2025) | Standard 7 |
| `analytics-service` | Raw JDBC in `OrderDataLoader` | Standard 7 (use Spring Data) |
| `loyalty-service` | Imports `platform-bom` version 1.8 (current: 2.3) — 14 months behind | Standard 7 |

---

## API Contract Gaps

| Service | Gap |
|---------|-----|
| `kitchen-display-service` | No OpenAPI specification — API undocumented |
| `delivery-orchestration` | OpenAPI spec exists but not registered in API catalogue |
| `order-service` | No Pact tests for order → loyalty integration |
| `inventory-service` | REST paths lack version prefix (`/menu-items` not `/v1/menu-items`) |
| `analytics-service` | Consumes Order domain events but no consumer contract registered in Pact broker |

---

## Summary Risk Register

| Risk | Count | Highest Severity |
|------|-------|-----------------|
| Cross-domain class imports | 7 instances | CRITICAL |
| Direct repository access across domains | 3 instances | CRITICAL |
| External SDK leakage beyond ACL | 23 class references | HIGH |
| Synchronous calls for state-changing cross-domain ops | 3 integrations | HIGH |
| PII in telemetry | 2 services confirmed | HIGH |
| Secrets in source control | 1 confirmed | CRITICAL |
| Missing API contracts | 5 services | MEDIUM |
| EOL / misaligned dependencies | 3 services | MEDIUM |
