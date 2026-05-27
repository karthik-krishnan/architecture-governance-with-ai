package com.example.restaurant.order.infrastructure;

public class PaymentGatewayClient {

    public void processPayment(String orderId, double amount) {
        System.out.println("[PaymentGatewayClient] Calling external payment API — orderId=" + orderId + ", amount=$" + amount);
    }
}
