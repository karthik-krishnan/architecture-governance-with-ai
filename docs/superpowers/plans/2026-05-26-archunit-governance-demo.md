# ArchUnit Architecture Governance Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Maven/Java project that intentionally violates layered-architecture rules, then codifies those rules as ArchUnit fitness functions that fail in CI, plus a written refactor plan to fix them.

**Architecture:** Single Maven module, 5 production classes across 5 packages (`controller`, `application`, `domain`, `infrastructure`, `repository`). Four deliberate architecture violations baked into production code. Five ArchUnit rules in one test class catch all violations. Tests fail by design — that is the demo.

**Tech Stack:** Java 17, Maven 3.8+, ArchUnit 1.3.0, JUnit 5.10.2

---

## File Map

| File | Purpose |
|------|---------|
| `pom.xml` | Maven project descriptor with ArchUnit + JUnit 5 deps |
| `src/main/java/…/domain/Order.java` | Domain entity — **VIOLATION**: imports PaymentGatewayClient (infra) and OrderService (app) |
| `src/main/java/…/infrastructure/PaymentGatewayClient.java` | External payment adapter |
| `src/main/java/…/repository/OrderRepository.java` | In-memory store |
| `src/main/java/…/application/OrderService.java` | App service — **VIOLATION**: depends directly on PaymentGatewayClient |
| `src/main/java/…/controller/OrderController.java` | HTTP entry point — **VIOLATION**: directly wires OrderRepository |
| `src/test/java/…/ArchitectureFitnessFunctionsTest.java` | Five ArchUnit fitness functions |
| `README.md` | Demo walkthrough and commands |
| `REFACTOR_PLAN.md` | Step-by-step fix for each violation |

---

## Task 1: Maven scaffold

**Files:**
- Create: `pom.xml`

- [ ] **Step 1: Create `pom.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example.restaurant</groupId>
    <artifactId>restaurant-order-demo</artifactId>
    <version>1.0-SNAPSHOT</version>
    <packaging>jar</packaging>

    <name>Restaurant Order Service — Architecture Governance Demo</name>
    <description>
        Demonstrates architecture fitness functions using ArchUnit.
        Production code intentionally violates layered-architecture rules.
        ArchUnit tests codify those rules — they fail by design.
    </description>

    <properties>
        <java.version>17</java.version>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <archunit.version>1.3.0</archunit.version>
        <junit.version>5.10.2</junit.version>
    </properties>

    <dependencies>
        <!-- ArchUnit with JUnit 5 integration -->
        <dependency>
            <groupId>com.tngtech.archunit</groupId>
            <artifactId>archunit-junit5</artifactId>
            <version>${archunit.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- JUnit 5 -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>${junit.version}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.2.5</version>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.13.0</version>
                <configuration>
                    <source>17</source>
                    <target>17</target>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

- [ ] **Step 2: Create source directories**

```bash
mkdir -p src/main/java/com/example/restaurant/order/{controller,application,domain,infrastructure,repository}
mkdir -p src/test/java/com/example/restaurant/order
```

- [ ] **Step 3: Verify dependencies resolve**

```bash
mvn dependency:resolve -q
```

Expected: `BUILD SUCCESS`

---

## Task 2: Domain and infrastructure foundation classes

**Files:**
- Create: `src/main/java/com/example/restaurant/order/domain/Order.java`
- Create: `src/main/java/com/example/restaurant/order/infrastructure/PaymentGatewayClient.java`
- Create: `src/main/java/com/example/restaurant/order/repository/OrderRepository.java`

- [ ] **Step 1: Create `Order.java`**

`Order` is the central domain entity. It carries two violations:
- imports `PaymentGatewayClient` from `infrastructure` (domain → infra)
- imports `OrderService` from `application` (domain → application, which is also a cycle since application already depends on domain)

```java
package com.example.restaurant.order.domain;

import com.example.restaurant.order.application.OrderService;        // VIOLATION: circular — domain → application
import com.example.restaurant.order.infrastructure.PaymentGatewayClient; // VIOLATION: domain → infrastructure

public class Order {

    private final String orderId;
    private final String customerId;
    private final double totalAmount;

    // VIOLATION: domain entity holds infrastructure concern
    @SuppressWarnings("unused")
    private PaymentGatewayClient paymentClient;

    // VIOLATION: domain entity references application layer → creates domain ↔ application cycle
    @SuppressWarnings("unused")
    private OrderService orderService;

    public Order(String orderId, String customerId, double totalAmount) {
        this.orderId = orderId;
        this.customerId = customerId;
        this.totalAmount = totalAmount;
    }

    public String getOrderId()     { return orderId; }
    public String getCustomerId()  { return customerId; }
    public double getTotalAmount() { return totalAmount; }
}
```

- [ ] **Step 2: Create `PaymentGatewayClient.java`**

```java
package com.example.restaurant.order.infrastructure;

public class PaymentGatewayClient {

    public void processPayment(String orderId, double amount) {
        System.out.println("[PaymentGatewayClient] Calling external payment API — orderId=" + orderId + ", amount=$" + amount);
    }
}
```

- [ ] **Step 3: Create `OrderRepository.java`**

```java
package com.example.restaurant.order.repository;

import com.example.restaurant.order.domain.Order;

import java.util.HashMap;
import java.util.Map;

public class OrderRepository {

    private final Map<String, Order> store = new HashMap<>();

    public void save(Order order) {
        store.put(order.getOrderId(), order);
    }

    public Order findById(String orderId) {
        return store.get(orderId);
    }
}
```

---

## Task 3: Application and controller layers (with violations)

**Files:**
- Create: `src/main/java/com/example/restaurant/order/application/OrderService.java`
- Create: `src/main/java/com/example/restaurant/order/controller/OrderController.java`

- [ ] **Step 1: Create `OrderService.java`**

Violation: application layer imports the concrete `PaymentGatewayClient` from infrastructure instead of depending on a `PaymentGateway` interface.

```java
package com.example.restaurant.order.application;

import com.example.restaurant.order.domain.Order;
import com.example.restaurant.order.infrastructure.PaymentGatewayClient; // VIOLATION: application → infrastructure
import com.example.restaurant.order.repository.OrderRepository;

public class OrderService {

    private final OrderRepository orderRepository;

    // VIOLATION: should depend on a PaymentGateway interface, not the concrete infrastructure class
    private final PaymentGatewayClient paymentGatewayClient;

    public OrderService(OrderRepository orderRepository, PaymentGatewayClient paymentGatewayClient) {
        this.orderRepository = orderRepository;
        this.paymentGatewayClient = paymentGatewayClient;
    }

    public Order createOrder(String customerId, double totalAmount) {
        Order order = new Order("ORD-" + System.currentTimeMillis(), customerId, totalAmount);
        orderRepository.save(order);
        paymentGatewayClient.processPayment(order.getOrderId(), order.getTotalAmount());
        return order;
    }

    public Order findOrder(String orderId) {
        return orderRepository.findById(orderId);
    }
}
```

- [ ] **Step 2: Create `OrderController.java`**

Violation: controller injects and calls `OrderRepository` directly, bypassing the service layer.

```java
package com.example.restaurant.order.controller;

import com.example.restaurant.order.application.OrderService;
import com.example.restaurant.order.domain.Order;
import com.example.restaurant.order.repository.OrderRepository; // VIOLATION: controller → repository

public class OrderController {

    private final OrderService orderService;

    // VIOLATION: controller should never hold a reference to a repository
    private final OrderRepository orderRepository;

    public OrderController(OrderService orderService, OrderRepository orderRepository) {
        this.orderService = orderService;
        this.orderRepository = orderRepository;
    }

    public Order placeOrder(String customerId, double amount) {
        return orderService.createOrder(customerId, amount);
    }

    // VIOLATION: bypasses service layer to query the store directly
    public Order getOrder(String orderId) {
        return orderRepository.findById(orderId);
    }
}
```

- [ ] **Step 3: Verify all classes compile**

```bash
mvn compile
```

Expected: `BUILD SUCCESS` — violations are valid Java; ArchUnit catches them at test-time, not compile-time.

---

## Task 4: ArchUnit fitness function tests

**Files:**
- Create: `src/test/java/com/example/restaurant/order/ArchitectureFitnessFunctionsTest.java`

- [ ] **Step 1: Create `ArchitectureFitnessFunctionsTest.java`**

```java
package com.example.restaurant.order;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.library.dependencies.SliceRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

@AnalyzeClasses(
        packages = "com.example.restaurant.order",
        importOptions = ImportOption.DoNotIncludeTests.class
)
public class ArchitectureFitnessFunctionsTest {

    // ─── FITNESS FUNCTION 1 ───────────────────────────────────────────────────
    // Controllers must not access repositories directly.
    // They must go through the application (service) layer.
    @ArchTest
    static final ArchRule controllers_should_not_directly_access_repositories =
            noClasses()
                    .that().resideInAPackage("..controller..")
                    .should().accessClassesThat().resideInAPackage("..repository..")
                    .because("Controllers must go through the application layer — direct repository access " +
                             "bypasses business-logic enforcement and makes the boundary unenforceable");

    // ─── FITNESS FUNCTION 2 ───────────────────────────────────────────────────
    // Domain model must not depend on infrastructure.
    // Infrastructure details (HTTP clients, DB adapters) must never leak into business logic.
    @ArchTest
    static final ArchRule domain_should_not_depend_on_infrastructure =
            noClasses()
                    .that().resideInAPackage("..domain..")
                    .should().dependOnClassesThat().resideInAPackage("..infrastructure..")
                    .because("Domain model must stay pure — coupling it to infrastructure makes " +
                             "business logic impossible to unit-test without spinning up external systems");

    // ─── FITNESS FUNCTION 3 ───────────────────────────────────────────────────
    // Application services must not depend directly on external client implementations.
    // They must depend on abstractions (interfaces defined in application or domain).
    @ArchTest
    static final ArchRule application_should_not_directly_use_infrastructure_clients =
            noClasses()
                    .that().resideInAPackage("..application..")
                    .should().dependOnClassesThat().resideInAPackage("..infrastructure..")
                    .because("Application services must depend on abstractions, not concrete infrastructure. " +
                             "Concrete clients belong in infrastructure; interfaces belong in application or domain");

    // ─── FITNESS FUNCTION 4 ───────────────────────────────────────────────────
    // No cyclic dependencies between architectural layers.
    // If domain → application and application → domain, neither can be understood in isolation.
    @ArchTest
    static final SliceRule no_cyclic_dependencies_between_layers =
            slices()
                    .matching("com.example.restaurant.order.(*)..")
                    .should().beFreeOfCycles()
                    .because("Cyclic layer dependencies make the codebase impossible to reason about, " +
                             "test in isolation, or deploy independently");

    // ─── FITNESS FUNCTION 5 ───────────────────────────────────────────────────
    // Repository classes may only be accessed from the application or infrastructure layer.
    // Controllers, domain, and other packages must not reach into the repository directly.
    @ArchTest
    static final ArchRule repositories_only_accessible_from_application_or_infrastructure =
            noClasses()
                    .that().resideOutsideOfPackages(
                            "com.example.restaurant.order.application",
                            "com.example.restaurant.order.infrastructure",
                            "com.example.restaurant.order.repository"
                    )
                    .should().accessClassesThat().resideInAPackage("..repository..")
                    .because("Uncontrolled repository access from controllers or domain objects " +
                             "turns every layer into a data-access layer and destroys the service boundary");
}
```

- [ ] **Step 2: Run tests — expect failures**

```bash
mvn test
```

Expected: `BUILD FAILURE`. You should see violations reported for:

| Fitness Function | Caught Violation |
|------------------|-----------------|
| `controllers_should_not_directly_access_repositories` | `OrderController` accesses `OrderRepository` |
| `domain_should_not_depend_on_infrastructure` | `Order` imports `PaymentGatewayClient` |
| `application_should_not_directly_use_infrastructure_clients` | `OrderService` imports `PaymentGatewayClient` |
| `no_cyclic_dependencies_between_layers` | `domain` ↔ `application` cycle via `Order` → `OrderService` |
| `repositories_only_accessible_from_application_or_infrastructure` | `OrderController` accesses `OrderRepository` (also caught by FF1) |

- [ ] **Step 3: Commit**

```bash
git init
git add pom.xml src/
git commit -m "demo: intentional architecture violations with ArchUnit fitness functions (tests fail by design)"
```

---

## Task 5: README and REFACTOR_PLAN

**Files:**
- Create: `README.md`
- Create: `REFACTOR_PLAN.md`

- [ ] **Step 1: Create `README.md`**

````markdown
# Restaurant Order Service — Architecture Governance Demo

This project demonstrates how **architecture fitness functions** can be codified as automated
tests in a CI/CD pipeline using [ArchUnit](https://archunit.org).

The production code intentionally violates layered-architecture rules.  
The ArchUnit tests **fail by design** — that is the point.

---

## What This Shows

> "If you can't enforce it, it isn't an architecture rule — it's a suggestion."

Traditional architecture diagrams and documentation drift away from the code.
ArchUnit lets you write the architecture intent as executable JUnit 5 tests
that run in CI and break the build the moment a violation is introduced.

---

## Project Structure

```
src/main/java/com/example/restaurant/order/
├── controller/    OrderController      ← HTTP entry point
├── application/   OrderService         ← Business logic / use cases
├── domain/        Order                ← Core entity
├── infrastructure/PaymentGatewayClient ← External system adapter
└── repository/    OrderRepository      ← Data store
```

**Intended dependency direction (clean architecture):**

```
controller → application → domain
infrastructure → application (implements interfaces)
repository → domain
```

---

## Violations Baked Into This Code

| # | Class | Violation | Rule Broken |
|---|-------|-----------|-------------|
| 1 | `OrderController` | Injects and calls `OrderRepository` directly | Controller must not access repository |
| 2 | `Order` (domain) | Imports `PaymentGatewayClient` (infrastructure) | Domain must not depend on infrastructure |
| 3 | `Order` (domain) | Imports `OrderService` (application) | Creates domain ↔ application cycle |
| 4 | `OrderService` | Depends on `PaymentGatewayClient` directly | Application must use abstractions |

---

## Prerequisites

- Java 17+
- Maven 3.8+

Verify: `java -version && mvn -version`

---

## Demo Flow

### Step 1 — Run the fitness functions and watch them fail

```bash
mvn test
```

Expected output: `BUILD FAILURE` with five violation reports.  
Each failure message includes the class, the offending dependency, and the governance reason.

### Step 2 — Read the violations

ArchUnit output tells you exactly what was caught and why:

```
Architecture Violation [Priority: MEDIUM] - Rule 'no classes that reside in a package '..controller..'
should access classes that reside in a package '..repository..', because Controllers must go through
the application layer' was violated (1 times):
  Method <OrderController.getOrder(String)> calls method <OrderRepository.findById(String)>
  in (OrderController.java:30)
```

### Step 3 — Review the refactor plan

See `REFACTOR_PLAN.md` for a step-by-step fix of each violation.

### Step 4 — (Optional) Fix the code and re-run

After applying the fixes in `REFACTOR_PLAN.md`, run `mvn test` again.  
Expected: `BUILD SUCCESS` — all five fitness functions pass.

---

## The Fitness Functions

| Test | Rule |
|------|------|
| `controllers_should_not_directly_access_repositories` | Controllers must go through the service layer |
| `domain_should_not_depend_on_infrastructure` | Domain stays pure — no infra imports |
| `application_should_not_directly_use_infrastructure_clients` | Services depend on interfaces, not concrete clients |
| `no_cyclic_dependencies_between_layers` | No layer A → B → A cycles |
| `repositories_only_accessible_from_application_or_infrastructure` | Controlled repository access |

---

## Why This Matters at Enterprise Scale

- Violations accumulate silently without automated enforcement
- New engineers don't know the "rules" — they follow the nearest example
- Code reviews catch some violations but miss others under time pressure
- ArchUnit makes the rules **executable** — they break the build on day one of a violation
````

- [ ] **Step 2: Create `REFACTOR_PLAN.md`**

```markdown
# Architecture Refactor Plan

This document explains how to fix each violation so that all five ArchUnit fitness functions pass.

---

## Violation 1 — `OrderController` directly accesses `OrderRepository`

**Fitness function:** `controllers_should_not_directly_access_repositories`  
**File:** `controller/OrderController.java`

**Fix:** Remove the `OrderRepository` field from `OrderController`.  
Add a `findOrder(String orderId)` method to `OrderService` (it already has one).  
Change `OrderController.getOrder()` to call `orderService.findOrder(orderId)`.

```java
// BEFORE (violation)
public class OrderController {
    private final OrderService orderService;
    private final OrderRepository orderRepository; // REMOVE THIS

    public Order getOrder(String orderId) {
        return orderRepository.findById(orderId);  // REMOVE THIS
    }
}

// AFTER (fixed)
public class OrderController {
    private final OrderService orderService;       // only dependency

    public Order getOrder(String orderId) {
        return orderService.findOrder(orderId);    // goes through service layer
    }
}
```

---

## Violation 2 — `Order` (domain) imports `PaymentGatewayClient` (infrastructure)

**Fitness function:** `domain_should_not_depend_on_infrastructure`  
**File:** `domain/Order.java`

**Fix:** Remove `private PaymentGatewayClient paymentClient` from `Order`.  
Domain entities should hold data and business rules only.  
Payment processing is an application-layer concern.

```java
// BEFORE (violation)
import com.example.restaurant.order.infrastructure.PaymentGatewayClient; // REMOVE
private PaymentGatewayClient paymentClient; // REMOVE

// AFTER (fixed) — no infrastructure imports in Order
```

---

## Violation 3 — `Order` (domain) imports `OrderService` (application) — circular dependency

**Fitness function:** `no_cyclic_dependencies_between_layers`  
**File:** `domain/Order.java`

**Fix:** Remove `private OrderService orderService` from `Order`.  
Domain objects must not reference application services — the dependency always flows  
application → domain, never domain → application.

```java
// BEFORE (violation)
import com.example.restaurant.order.application.OrderService; // REMOVE
private OrderService orderService; // REMOVE

// AFTER (fixed) — Order has zero imports from other internal layers
```

---

## Violation 4 — `OrderService` depends directly on `PaymentGatewayClient` (infrastructure)

**Fitness function:** `application_should_not_directly_use_infrastructure_clients`  
**File:** `application/OrderService.java`

**Fix (Ports & Adapters):**

1. Create a `PaymentGateway` interface in the `application` package:

```java
// NEW: application/PaymentGateway.java
package com.example.restaurant.order.application;

public interface PaymentGateway {
    void processPayment(String orderId, double amount);
}
```

2. Make `PaymentGatewayClient` implement it (in infrastructure):

```java
// MODIFIED: infrastructure/PaymentGatewayClient.java
package com.example.restaurant.order.infrastructure;

import com.example.restaurant.order.application.PaymentGateway;

public class PaymentGatewayClient implements PaymentGateway {
    @Override
    public void processPayment(String orderId, double amount) {
        System.out.println("[PaymentGatewayClient] orderId=" + orderId + ", amount=$" + amount);
    }
}
```

3. Change `OrderService` to depend on the interface:

```java
// MODIFIED: application/OrderService.java
import com.example.restaurant.order.application.PaymentGateway; // interface — allowed

public class OrderService {
    private final OrderRepository orderRepository;
    private final PaymentGateway paymentGateway; // interface, not concrete class

    public OrderService(OrderRepository orderRepository, PaymentGateway paymentGateway) {
        this.orderRepository = orderRepository;
        this.paymentGateway = paymentGateway;
    }
}
```

---

## After All Fixes

Run `mvn test` — all five fitness functions should pass:

```
[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

The architecture now enforces the intended dependency direction:

```
controller → application (via interfaces)
          ↓
     domain  ←  repository
          ↑
   infrastructure (implements application interfaces)
```
```

- [ ] **Step 3: Commit**

```bash
git add README.md REFACTOR_PLAN.md
git commit -m "docs: add demo README and step-by-step architecture refactor plan"
```

---

## Violations Summary

| Violation | Caught By |
|-----------|-----------|
| `OrderController` → `OrderRepository` | FF1 + FF5 |
| `Order` → `PaymentGatewayClient` | FF2 |
| `Order` → `OrderService` (circular) | FF4 |
| `OrderService` → `PaymentGatewayClient` | FF3 |
