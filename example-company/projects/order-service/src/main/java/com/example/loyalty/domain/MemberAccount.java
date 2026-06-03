package com.example.loyalty.domain;

public class MemberAccount {

    private final String memberId;
    private final String customerEmail;
    private int pointsBalance;

    public MemberAccount(String memberId, String customerEmail) {
        this.memberId = memberId;
        this.customerEmail = customerEmail;
        this.pointsBalance = 0;
    }

    public void awardPoints(int points) {
        this.pointsBalance += points;
    }

    public String getMemberId()      { return memberId; }
    public String getCustomerEmail() { return customerEmail; }
    public int getPointsBalance()    { return pointsBalance; }
}
