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

    // VIOLATION: bypasses the application layer to query the store directly
    public Order getOrder(String orderId) {
        return orderRepository.findById(orderId);
    }
}
