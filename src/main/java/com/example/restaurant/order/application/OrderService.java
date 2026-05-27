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
