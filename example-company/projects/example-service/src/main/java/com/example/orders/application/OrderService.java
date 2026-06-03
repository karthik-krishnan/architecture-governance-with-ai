package com.example.orders.application;

import com.example.orders.domain.Order;
import com.example.orders.infrastructure.PaymentGatewayClient; // VIOLATION: application → concrete infrastructure
import com.example.orders.repository.OrderRepository;
import com.example.loyalty.repository.LoyaltyRepository; // VIOLATION: cross-context — Order reaching into Loyalty's repository

public class OrderService {

    private final OrderRepository orderRepository;
    private final PaymentGatewayClient paymentGatewayClient;
    // VIOLATION: cross-context — Order domain directly accessing Loyalty's data store
    private final LoyaltyRepository loyaltyRepository;

    public OrderService(OrderRepository orderRepository, PaymentGatewayClient paymentGatewayClient,
                        LoyaltyRepository loyaltyRepository) {
        this.orderRepository = orderRepository;
        this.paymentGatewayClient = paymentGatewayClient;
        this.loyaltyRepository = loyaltyRepository;
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
