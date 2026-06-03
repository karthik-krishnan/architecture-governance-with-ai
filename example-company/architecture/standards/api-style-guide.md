# Example Company Digital Platform — API Style Guide

**Version:** 3.0  
**Owner:** Platform Architecture  
**Applies to:** All HTTP APIs exposed by platform services, internal and external

---

## 1. Versioning

All API paths must include a version prefix as the first path segment.

```
/v{n}/{resource}
```

- Version is a positive integer: `/v1/`, `/v2/`
- No minor versions in the path — breaking changes require a version increment
- Both the old and new version must be supported for a minimum of 90 days after a new version ships
- Deprecation notice must be published to the API catalogue before the countdown starts

**Correct:**  `/v2/orders/{orderId}`  
**Incorrect:** `/orders/{orderId}`, `/api/orders/{orderId}`, `/v2.1/orders/{orderId}`

---

## 2. Resource Naming

- Path segments use **kebab-case**: `/loyalty-accounts`, `/menu-items`
- Resources are **plural nouns**: `/orders` not `/order`, `/payments` not `/payment`
- Nested resources for ownership relationships only: `/orders/{orderId}/items`
- Actions that do not map to CRUD use a verb suffix on the resource: `/orders/{orderId}/cancel`

---

## 3. HTTP Methods

| Operation | Method | Notes |
|-----------|--------|-------|
| Fetch a resource | GET | Idempotent, no body |
| Create a resource | POST | Returns 201 with Location header |
| Full replacement | PUT | Idempotent |
| Partial update | PATCH | Only send changed fields |
| Delete | DELETE | Returns 204, no body |

Do not use POST for reads. Do not tunnel operations through GET query parameters.

---

## 4. Response Codes

Use standard HTTP status codes. Do not invent application-level success/failure wrappers.

| Scenario | Code |
|----------|------|
| Created | 201 |
| No content (delete, action) | 204 |
| Bad request (validation) | 400 |
| Unauthenticated | 401 |
| Forbidden | 403 |
| Not found | 404 |
| Conflict (state violation) | 409 |
| Unprocessable entity (business rule) | 422 |
| Internal error | 500 |
| Downstream unavailable | 503 |

---

## 5. Error Response Format

All error responses must follow this structure:

```json
{
  "code": "ORDER_NOT_FOUND",
  "message": "No order found with id f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "correlationId": "3d6f4aa0-1c3a-4b8e-9df2-7e1a3c5f9b2d"
}
```

- `code`: machine-readable uppercase snake-case string, stable across versions
- `message`: human-readable, safe to display in logs
- `correlationId`: propagated from the incoming request header `X-Correlation-ID`; generated if absent

No stack traces, no internal class names, no database error messages in API responses.

---

## 6. Request and Response Bodies

- Content type is always `application/json`
- Field names use **camelCase**: `customerId`, `placedAt`, `estimatedReadyAt`
- Dates and times use **ISO 8601** with UTC timezone: `2025-08-14T14:32:00Z`
- UUIDs use lowercase hyphenated format: `f47ac10b-58cc-4372-a567-0e02b2c3d479`
- Money amounts use integer **minor units** (pence, cents) with a currency code field
- Nullable fields must be explicitly listed — do not omit optional fields from the schema

---

## 7. Pagination

All list endpoints returning more than one resource must support cursor-based pagination.

```json
{
  "data": [...],
  "pagination": {
    "nextCursor": "eyJpZCI6IjEyMyJ9",
    "hasMore": true
  }
}
```

- `limit` query parameter controls page size (default 20, max 100)
- `cursor` query parameter accepts the `nextCursor` from the previous response
- Offset-based pagination (`?page=2`) is not permitted for new endpoints

---

## 8. OpenAPI Specification Requirement

Every service must maintain an OpenAPI 3.1 specification committed to its repository at:

```
src/main/resources/openapi.yaml
```

The spec is the contract. Code must match the spec. The spec is linted in CI using the
platform Spectral ruleset before merge. Services without a spec fail the API catalogue gate.

---

## 9. PII in APIs

- Do not include PII (email, phone, full name, address) in path segments or query parameters — these appear in access logs
- Request and response bodies that include PII must be marked in the OpenAPI spec using `x-pii: true` on the field
- PII fields must not appear in error messages or correlation trace attributes

---

## 10. Deprecation Process

1. Add `Deprecation` and `Sunset` headers to deprecated endpoint responses
2. Publish a deprecation notice to the API catalogue with the sunset date
3. Notify all known consumers via the service's Slack channel and the platform changelog
4. Sunset date must be at least 90 days from the deprecation announcement
5. After sunset, the endpoint returns 410 Gone for a further 30 days before removal
