# QSR Enterprise Platform — Service Description

## Context

This document describes the current state of the digital platform for a large Quick Service
Restaurant enterprise operating ~4,000 locations across North America and APAC. The platform
supports ordering across multiple channels (mobile app, kiosk, POS, third-party delivery),
kitchen operations, loyalty, franchise management, and corporate analytics.

The platform was built incrementally over six years: a monolith decomposed into services
starting in 2019, with accelerated decomposition during the pandemic-driven digital shift.
Not all decomposition decisions were architecturally consistent.

---

## Bounded Contexts and Domain Ownership

### 1. Order Management
**Owner:** Digital Commerce team  
**Responsibility:** Receives and manages orders from all intake channels. Owns the order
lifecycle from placement through fulfillment confirmation.  
**Key data owned:** Order, OrderItem, OrderStatus, FulfillmentChannel  
**Downstream consumers:** Kitchen Display, Loyalty, Inventory, Analytics

### 2. Loyalty & Rewards
**Owner:** CRM team  
**Responsibility:** Manages member accounts, points accumulation, tier status, and reward
redemption. Integrates with the mobile app and POS.  
**Key data owned:** MemberAccount, PointsLedger, RewardCatalogue, Redemption  
**Upstream producers it listens to:** Order Management (order completion events)

### 3. Kitchen Display & Fulfillment
**Owner:** Operations Technology team  
**Responsibility:** Routes orders to kitchen stations, tracks preparation status, manages
bump-bar interactions, and signals order-ready status.  
**Key data owned:** KitchenTicket, StationQueue, PrepTime  
**Dependency:** Requires near-real-time visibility into order details

### 4. Payment Processing
**Owner:** Finance Technology team  
**Responsibility:** Authorises, captures, and refunds payments. Integrates with card networks
and digital wallets. Owns PCI-DSS compliance boundary.  
**Key data owned:** PaymentAuthorisation, TransactionRecord, RefundRequest  
**Strict boundary:** No other domain may store or process card data

### 5. Inventory & Menu Management
**Owner:** Supply Chain Technology team  
**Responsibility:** Manages item availability, 86'd items (sold out), pricing, and menu
configuration across locations.  
**Key data owned:** MenuItem, InventoryLevel, LocationMenu, PricingRule  
**Downstream consumers:** Order Management (availability checks), Kitchen Display

### 6. Delivery Orchestration
**Owner:** Digital Commerce team (same as Order Management — shared team, separate service)  
**Responsibility:** Manages hand-off to third-party delivery partners (DoorDash, Uber Eats,
SkipTheDishes). Translates internal order model to partner-specific protocols.  
**Key data owned:** DeliveryJob, DriverAssignment, PartnerOrderRef  
**External dependencies:** DoorDash Merchant API, Uber Eats Orders API, SkipTheDishes API

### 7. Franchise & Location Management
**Owner:** Enterprise Systems team  
**Responsibility:** Manages franchisee records, location configuration, operating hours,
and compliance reporting. Used by corporate and franchise operators.  
**Key data owned:** Franchise, Location, OperatingProfile, ComplianceRecord

### 8. Analytics & Reporting
**Owner:** Data Platform team  
**Responsibility:** Aggregates operational and customer data for reporting, ML feature
pipelines, and corporate dashboards. Read-only consumer of domain events.  
**Key data owned:** None — read replica and event-sourced materialized views only

---

## Current Integration Patterns (Mixed)

The platform uses an inconsistent mix of synchronous and asynchronous patterns:

| Integration | Current Pattern | Target Pattern |
|-------------|----------------|----------------|
| Order → Loyalty (points award) | Synchronous REST call from OrderService | Domain event: `OrderCompleted` |
| Order → Kitchen (ticket creation) | Synchronous REST call from OrderService | Domain event: `OrderConfirmed` |
| Order → Inventory (availability check) | Synchronous REST call (acceptable — read, not state change) | Keep synchronous (read) |
| Delivery → Order (status updates) | Webhook callback to OrderService | Keep as callback (external initiation) |
| Analytics → all domains | Direct database read replica queries | Domain events + event-sourced views |
| Payment → Order (authorisation result) | Synchronous response (acceptable) | Keep synchronous (request/response) |

---

## Technology Stack

- **Runtime:** Java 17, Spring Boot 3.x (most services), one legacy service on Spring Boot 2.5
- **Messaging:** Apache Kafka (partially adopted — Order Management and Analytics use it; other teams have not yet onboarded)
- **Databases:** PostgreSQL (per-service), with the exception of the Analytics replica which reads from multiple schemas
- **API Gateway:** Kong (external-facing), no internal service mesh yet
- **Auth:** OAuth2 / Keycloak for customer-facing; service-to-service auth inconsistent (some use JWT, some use internal network trust)
- **Observability:** Datadog APM (partially instrumented), structured logging (inconsistent adoption), no distributed trace propagation standard
- **Delivery partner SDKs:** DoorDash Java SDK, Uber Eats REST client (hand-rolled), SkipTheDishes REST client (hand-rolled)

---

## Known Architecture Concerns (Pre-Review)

The following concerns have been raised informally and are awaiting EA review:

1. The Loyalty team has observed that points are sometimes not awarded when the Order service is under load — suggesting the synchronous call is the failure point
2. The Kitchen Display team built a direct read against the Orders PostgreSQL schema when the REST API latency was too high during a peak period — this was never remediated
3. Delivery Orchestration has DoorDash SDK classes appearing in the order translation logic, not isolated to an adapter
4. The Analytics team is blocked on the Order Management team's release schedule because they query the Order DB directly
5. No service currently emits structured events for payment transactions — Loyalty and Analytics reconstruct payment data from Order events, which is incomplete
6. PII fields appear in Datadog traces for the Order and Loyalty services — flagged by the security team but not yet remediated
