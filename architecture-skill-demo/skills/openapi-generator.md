---
name: openapi-generator
description: Use when given an API scan report, service description, and ADRs. Generates a valid OpenAPI 3.1 YAML spec. Violations of the API style guide are annotated inline with x-governance-gap extension fields.
---

# OpenAPI Generator

## Purpose

Read the API scan report and produce a complete, valid OpenAPI 3.1 YAML specification.
Every style guide violation identified in the scan must be annotated inline using the
`x-governance-gap` extension field so that gaps are visible in the spec itself.

Return only the YAML — no explanation, no markdown fences.

---

## Output Structure

```yaml
openapi: "3.1.0"
info:
  title: "{Service Name} API"
  version: "{current version or 0.1.0 if unversioned}"
  description: "{one sentence from service description}"
servers:
  - url: "http://localhost:8080"
    description: Local development
paths:
  /path/to/resource:
    get:
      summary: "{operation summary}"
      operationId: "{camelCase unique ID}"
      parameters: []
      responses:
        "200":
          description: "Success"
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ResourceName"
components:
  schemas:
    ResourceName:
      type: object
      properties:
        fieldName:
          type: string
```

---

## Governance Gap Annotations

For every violation found in the scan, add an `x-governance-gap` extension field at the
appropriate level in the spec. The value must cite the style guide section and explain the gap.

**Path-level violation (§1 versioning, §2 resource naming):**
```yaml
paths:
  /orders:
    x-governance-gap: "§1: Path must include version prefix — should be /v1/orders"
    post:
      ...
```

**Operation-level violation (§4 status codes, §5 error response, §6 DTO):**
```yaml
    post:
      x-governance-gap: "§4: POST must declare 201 Created response; §6: response schema is the domain Order object — a dedicated response DTO is required"
      responses:
        "200":
          ...
```

**Schema-level violation (§6 field naming, §9 PII):**
```yaml
components:
  schemas:
    Order:
      x-governance-gap: "§6: Response schema should be a dedicated DTO not the domain entity"
      properties:
        ...
```

Multiple violations on the same element: combine into one `x-governance-gap` string,
semicolon-separated.

---

## Rules for Valid OpenAPI 3.1

- `openapi` field must be exactly `"3.1.0"` (string, not number)
- `info.title` and `info.version` are required
- Every operation must have a unique `operationId` in camelCase
- Every `$ref` must resolve to a schema defined in `components/schemas`
- `responses` must have at least one response code
- Response codes are strings: `"200"`, `"201"`, `"404"` — not integers
- Parameter `in` values: `"path"`, `"query"`, `"header"`, `"cookie"`
- Path parameters must appear in the path string: if `{orderId}` is in the path,
  there must be a parameter with `name: orderId` and `in: path`
- Schema `type` values: `"string"`, `"number"`, `"integer"`, `"boolean"`, `"array"`, `"object"`
- Do not use `nullable: true` — use `type: ["string", "null"]` in OpenAPI 3.1
- `required` on a schema is an array of property name strings, not a boolean

---

## Critical: Do Not Invent Operations

Only generate operations for endpoints explicitly found in the scan report. Do not add
CRUD operations that were not observed. If an endpoint is incomplete in the scan, note it
with `x-governance-gap: "§8: Operation details incomplete — spec requires manual completion"`.
