package com.example.orders.infrastructure;

import org.springframework.web.client.RestTemplate; // VIOLATION: RestTemplate is banned per ADR-017 — use WebClient

public class PaymentGatewayClient {

    // VIOLATION: RestTemplate bypasses platform circuit breakers and resilience config
    private final RestTemplate restTemplate = new RestTemplate();

    public void processPayment(String orderId, double amount) {
        System.out.println("[PaymentGatewayClient] Calling external payment API — orderId=" + orderId + ", amount=$" + amount);
        // In a real service this would use restTemplate.postForObject(...)
    }
}
