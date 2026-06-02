package com.example.loyalty.repository;

import com.example.loyalty.domain.MemberAccount;

import java.util.HashMap;
import java.util.Map;

public class LoyaltyRepository {

    private final Map<String, MemberAccount> store = new HashMap<>();

    public void save(MemberAccount account) {
        store.put(account.getMemberId(), account);
    }

    public MemberAccount findByMemberId(String memberId) {
        return store.get(memberId);
    }
}
