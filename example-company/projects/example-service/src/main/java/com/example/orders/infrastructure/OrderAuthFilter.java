package com.example.orders.infrastructure;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;

// VIOLATION: custom JWT parsing outside platform-security-lib
// All JWT validation must delegate to com.example.platform.security.*
// This class is not covered by the platform security review and is a known attack surface.
public class OrderAuthFilter {

    private final String signingKey;

    public OrderAuthFilter(String signingKey) {
        this.signingKey = signingKey;
    }

    public String extractCustomerId(String token) {
        Claims claims = Jwts.parser()
                .setSigningKey(signingKey)
                .parseClaimsJws(token)
                .getBody();
        return claims.getSubject();
    }

    public boolean isValid(String token) {
        try {
            extractCustomerId(token);
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
