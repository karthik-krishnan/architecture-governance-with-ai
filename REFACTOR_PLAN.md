# Architecture Refactor Plan

How to fix each violation so that all five ArchUnit fitness functions pass.

After each fix, run `mvn test` to watch the failure count drop.

---

## Fix 1 — Remove direct `OrderRepository` access from `OrderController`

**Failing fitness function:** `controllers_should_not_directly_access_repositories`  
**File:** [`src/main/java/com/example/restaurant/order/controller/OrderController.java`](src/main/java/com/example/restaurant/order/controller/OrderController.java)

`OrderController` currently injects `OrderRepository` and calls `findById` directly.
`OrderService` already has a `findOrder` method — use that instead.

```java
// BEFORE (violation)
public class OrderController {
    private final OrderService orderService;
    private final OrderRepository orderRepository; // ← remove this field

    public OrderController(OrderService orderService, OrderRepository orderRepository) {
        this.orderService = orderService;
        this.orderRepository = orderRepository;   // ← remove
    }

    public Order getOrder(String orderId) {
        return orderRepository.findById(orderId); // ← violation
    }
}

// AFTER (fixed)
public class OrderController {
    private final OrderService orderService;      // only dependency

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    public Order getOrder(String orderId) {
        return orderService.findOrder(orderId);   // goes through service layer
    }
}
```

---

## Fix 2 — Remove `PaymentGatewayClient` field from `Order`

**Failing fitness function:** `domain_should_not_depend_on_infrastructure`  
**File:** [`src/main/java/com/example/restaurant/order/domain/Order.java`](src/main/java/com/example/restaurant/order/domain/Order.java)

`Order` holds a `PaymentGatewayClient` field. Domain entities should hold data and
business rules only — payment processing is an application-layer concern.

```java
// BEFORE (violation)
import com.example.restaurant.order.infrastructure.PaymentGatewayClient; // ← remove import
private PaymentGatewayClient paymentClient;                               // ← remove field

// AFTER (fixed) — Order has no imports from infrastructure
```

---

## Fix 3 — Remove `OrderService` field from `Order` (breaks circular dependency)

**Failing fitness function:** `no_cyclic_dependencies_between_layers`  
**File:** [`src/main/java/com/example/restaurant/order/domain/Order.java`](src/main/java/com/example/restaurant/order/domain/Order.java)

`Order` (domain) holds an `OrderService` (application) field. This creates a cycle:
`application → domain → application`. Domain objects must never reference the application
layer — the dependency always flows application → domain.

```java
// BEFORE (violation)
import com.example.restaurant.order.application.OrderService; // ← remove import
private OrderService orderService;                            // ← remove field

// AFTER (fixed) — Order.java has zero imports from other internal layers
public class Order {
    private final String orderId;
    private final String customerId;
    private final double totalAmount;

    public Order(String orderId, String customerId, double totalAmount) { ... }
    // getters only — no references to other internal packages
}
```

---

## Fix 4 — Introduce `PaymentGateway` interface; remove direct infra dependency from `OrderService`

**Failing fitness function:** `application_should_not_directly_use_infrastructure_clients`  
**File:** [`src/main/java/com/example/restaurant/order/application/OrderService.java`](src/main/java/com/example/restaurant/order/application/OrderService.java)

`OrderService` imports the concrete `PaymentGatewayClient` from infrastructure. The fix is
the classic **Ports & Adapters** (Hexagonal Architecture) pattern:

1. **Create a `PaymentGateway` interface in the `application` package** (the "port"):

```java
// NEW FILE: src/main/java/com/example/restaurant/order/application/PaymentGateway.java
package com.example.restaurant.order.application;

public interface PaymentGateway {
    void processPayment(String orderId, double amount);
}
```

2. **Make `PaymentGatewayClient` implement it** (the "adapter"):

```java
// MODIFIED: src/main/java/com/example/restaurant/order/infrastructure/PaymentGatewayClient.java
package com.example.restaurant.order.infrastructure;

import com.example.restaurant.order.application.PaymentGateway;

public class PaymentGatewayClient implements PaymentGateway {

    @Override
    public void processPayment(String orderId, double amount) {
        System.out.println("[PaymentGatewayClient] orderId=" + orderId + ", amount=$" + amount);
    }
}
```

3. **Change `OrderService` to depend on the interface**:

```java
// MODIFIED: src/main/java/com/example/restaurant/order/application/OrderService.java
package com.example.restaurant.order.application;

import com.example.restaurant.order.domain.Order;
import com.example.restaurant.order.repository.OrderRepository;
// No more infrastructure import ← key change

public class OrderService {

    private final OrderRepository orderRepository;
    private final PaymentGateway paymentGateway; // interface, not concrete class

    public OrderService(OrderRepository orderRepository, PaymentGateway paymentGateway) {
        this.orderRepository = orderRepository;
        this.paymentGateway = paymentGateway;
    }

    public Order createOrder(String customerId, double totalAmount) {
        Order order = new Order("ORD-" + System.currentTimeMillis(), customerId, totalAmount);
        orderRepository.save(order);
        paymentGateway.processPayment(order.getOrderId(), order.getTotalAmount());
        return order;
    }

    public Order findOrder(String orderId) {
        return orderRepository.findById(orderId);
    }
}
```

---

## Verification

After all four fixes, run:

```bash
mvn test
```

Expected result:

```
[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

---

## Resulting Architecture

After the fixes, the dependency graph is clean:

```
controller
    └─→ application (OrderService, PaymentGateway interface)
              └─→ domain (Order)
              └─→ repository (OrderRepository → domain)

infrastructure
    └─→ application (PaymentGatewayClient implements PaymentGateway)
```

- `domain` has zero dependencies on other internal layers
- `application` depends only on `domain` and `repository`
- `infrastructure` depends on `application` (implements its interfaces) — dependency inversion
- `controller` depends only on `application`
- No cycles anywhere
