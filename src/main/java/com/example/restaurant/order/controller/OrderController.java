package com.example.restaurant.order.controller;

import com.example.restaurant.order.application.OrderService;
import com.example.restaurant.order.domain.Order;
import com.example.restaurant.order.repository.OrderRepository; // VIOLATION: controller → repository
import org.springframework.web.bind.annotation.*;

// API VIOLATION §1: path must start with /v{n}/ — /orders has no version prefix
@RestController
@RequestMapping("/orders")
public class OrderController {

    private final OrderService orderService;

    // VIOLATION: controller should never hold a reference to a repository (structural)
    private final OrderRepository orderRepository;

    public OrderController(OrderService orderService, OrderRepository orderRepository) {
        this.orderService = orderService;
        this.orderRepository = orderRepository;
    }

    // API VIOLATION §4: POST must return 201 Created — missing @ResponseStatus(HttpStatus.CREATED)
    // API VIOLATION §6: returns internal Order domain object directly — no response DTO,
    //                    internal field names leak into the API contract
    @PostMapping
    public Order placeOrder(@RequestParam String customerId, @RequestParam double amount) {
        return orderService.createOrder(customerId, amount);
    }

    // API VIOLATION §5: no standard error response body for the 404 case —
    //                    should return {code, message, correlationId}
    // VIOLATION: bypasses the application layer to query the store directly (structural)
    @GetMapping("/{orderId}")
    public Order getOrder(@PathVariable String orderId) {
        return orderRepository.findById(orderId);
    }
}
