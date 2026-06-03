# Example Company Platform — Service Description

## Context

This document describes the current state of the Example Company digital platform.
The platform was built incrementally over several years: an initial monolith decomposed
into services, with decomposition decisions that were not always architecturally consistent.

---

## Bounded Contexts and Domain Ownership

### 1. Order Management
**Owner:** Digital Commerce team
**Responsibility:** Receives and manages orders from all intake channels. Owns the order
lifecycle from placement through fulfilment confirmation.
**Key data owned:** Order, OrderItem, OrderStatus, FulfilmentChannel
**Downstream consumers:** Fulfilment, Loyalty, Inventory, Analytics

### 2. Loyalty & Rewards
**Owner:** CRM team
**Responsibility:** Manages member accounts, points accumulation, tier status, and reward
redemption.
**Key data owned:** MemberAccount, PointsLedger, RewardCatalogue, Redemption
**Upstream producers it listens to:** Order Management (order completion events)

### 3. Payment Processing
**Owner:** Finance Technology team
**Responsibility:** Authorises, captures, and refunds payments. Owns the PCI-DSS compliance boundary.
**Key data owned:** PaymentAuthorisation, TransactionRecord, RefundRequest
**Strict boundary:** No other domain may store or process card data

### 4. Inventory & Catalogue
**Owner:** Supply Chain team
**Responsibility:** Manages item availability, pricing, and catalogue configuration.
**Key data owned:** CatalogueItem, InventoryLevel, PricingRule
**Downstream consumers:** Order Management (availability checks)

### 5. Analytics & Reporting
**Owner:** Data Platform team
**Responsibility:** Aggregates operational and customer data for reporting and ML pipelines.
Read-only consumer of domain events.
**Key data owned:** None — event-sourced materialised views only

---

## Current Integration Patterns (Mixed)

The platform uses an inconsistent mix of synchronous and asynchronous patterns:

| Integration | Current Pattern | Target Pattern |
|-------------|----------------|----------------|
| Order → Loyalty (points award) | Synchronous REST call from OrderService | Domain event: `OrderCompleted` |
| Order → Fulfilment (ticket creation) | Synchronous REST call from OrderService | Domain event: `OrderConfirmed` |
| Order → Inventory (availability check) | Synchronous REST call (acceptable — read) | Keep synchronous |
| Payment → Order (authorisation result) | Synchronous response (acceptable) | Keep synchronous |
| Analytics → all domains | Direct database read replica queries | Domain events + materialised views |

---

## Technology Stack

- **Runtime:** Java 17, Spring Boot 3.x
- **Messaging:** Apache Kafka (partially adopted)
- **Databases:** PostgreSQL (per-service)
- **Auth:** OAuth2 / Keycloak; service-to-service auth inconsistent (some JWT, some network trust)
- **Observability:** Structured logging (inconsistent adoption), no distributed trace propagation standard

---

## Known Architecture Concerns

The following concerns have been raised informally and are awaiting EA review:

1. Loyalty points are sometimes not awarded when the Order service is under load — the synchronous
   REST call is the suspected failure point
2. The Fulfilment team built a direct read against the Orders database when API latency was too
   high during a peak period — this was never remediated
3. No service currently emits structured events for payment transactions — downstream teams
   reconstruct payment data from Order events, which is incomplete
4. PII fields appear in traces for the Order and Loyalty services — flagged by the security
   team but not yet remediated
