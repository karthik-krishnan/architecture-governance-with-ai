package com.example.orders.domain;

import com.example.orders.application.OrderService;           // VIOLATION: circular — domain → application
import com.example.orders.infrastructure.PaymentGatewayClient; // VIOLATION: domain → infrastructure

public class Order {

    private final String orderId;
    private final String customerId;
    private final double totalAmount;

    // VIOLATION: domain entity holds an infrastructure concern
    @SuppressWarnings("unused")
    private PaymentGatewayClient paymentClient;

    // VIOLATION: domain entity references the application layer — creates domain ↔ application cycle
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
