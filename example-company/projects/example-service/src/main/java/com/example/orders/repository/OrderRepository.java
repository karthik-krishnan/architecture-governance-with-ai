package com.example.orders.repository;

import com.example.orders.domain.Order;

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
