---
name: spectral-ruleset-generator
description: Use when given an API style guide document. Generates a Spectral 6.x YAML ruleset that codifies the style guide as executable lint rules for OpenAPI specs.
---

# Spectral Ruleset Generator

## Purpose

Read the API style guide and produce a Spectral 6.x YAML ruleset. Each style guide section
becomes one or more Spectral rules. Return only the YAML — no explanation, no markdown fences.

---

## Spectral Ruleset Structure

```yaml
extends: "spectral:oas"      # inherit all built-in OpenAPI rules
rules:
  rule-id:
    message: "Human-readable message shown when rule fails. Cite the style guide section."
    description: "One sentence explaining what this rule checks."
    severity: error           # error | warn | info | hint
    given: "$JSONPath"        # what part of the OpenAPI document to check
    then:
      function: functionName  # built-in Spectral function
      functionOptions:
        match: "regex"        # options depend on function
```

---

## Built-in Spectral Functions

| Function | Use case | Key options |
|----------|----------|-------------|
| `pattern` | Value matches a regex | `match: "^regex$"` or `notMatch: "regex"` |
| `truthy` | Value is truthy (non-empty, non-null) | none |
| `falsy` | Value is falsy | none |
| `defined` | Field exists | none |
| `undefined` | Field must not exist | none |
| `length` | String/array length check | `min`, `max` |
| `enumeration` | Value is in a set | `values: [a, b, c]` |
| `casing` | Naming convention | `type: camel \| pascal \| kebab \| snake \| macro` |
| `schema` | JSON Schema validation | `schema: { type: ..., properties: ... }` |
| `xor` | Exactly one of two fields exists | `properties: [a, b]` |

The `then` block can also specify a `field` to target a child field of the `given` path:
```yaml
then:
  field: operationId
  function: truthy
```

---

## JSONPath Reference for OpenAPI Documents

| What to target | JSONPath |
|----------------|----------|
| All path keys | `$.paths[*]~` |
| All operations (any method) | `$.paths[*][get,post,put,patch,delete]` |
| All POST operations | `$.paths[*].post` |
| All operation objects | `$.paths[*][get,post,put,patch,delete]` |
| All response objects | `$.paths[*][*].responses[*]` |
| All operation IDs | `$.paths[*][*].operationId` |
| All schema properties (keys) | `$.components.schemas[*].properties[*]~` |
| All query/path parameter names | `$.paths[*][*].parameters[?(@.in=='query' || @.in=='path')].name` |
| Info object | `$.info` |

---

## Rules to Generate

Generate one rule per style guide section. Use these as templates and adapt to the
actual style guide content provided.

### §1 — Version prefix in all paths
```yaml
qsr-api-versioned-paths:
  message: "§1: API paths must include a version prefix (e.g. /v1/orders). Found: {{value}}"
  severity: error
  given: "$.paths[*]~"
  then:
    function: pattern
    functionOptions:
      match: "^/v[0-9]+/"
```

### §2 — Resource naming: kebab-case segments
```yaml
qsr-resource-kebab-case:
  message: "§2: Path segments must use lowercase kebab-case. Found: {{value}}"
  severity: warn
  given: "$.paths[*]~"
  then:
    function: pattern
    functionOptions:
      match: "^(/v[0-9]+)?(/[a-z0-9-]+(/\\{[a-zA-Z][a-zA-Z0-9]*\\})?)*(/[a-z0-9-]+)?$"
```

### §4 — POST operations must declare 201
```yaml
qsr-post-returns-201:
  message: "§4: POST operations must declare a 201 Created response."
  severity: error
  given: "$.paths[*].post.responses"
  then:
    function: schema
    functionOptions:
      schema:
        type: object
        required:
          - "201"
```

### §4 — operationId required on all operations
```yaml
qsr-operation-id-required:
  message: "§8: Every operation must have a unique operationId."
  severity: error
  given: "$.paths[*][get,post,put,patch,delete]"
  then:
    function: truthy
    field: operationId
```

### §5 — Standard error response schema on 4xx/5xx
```yaml
qsr-error-response-schema:
  message: "§5: Error responses must define a schema with code, message, and correlationId fields."
  severity: error
  given: "$.paths[*][*].responses[400,401,403,404,409,422,500,503].content['application/json'].schema"
  then:
    function: schema
    functionOptions:
      schema:
        type: object
        required:
          - code
          - message
          - correlationId
        properties:
          code:
            type: string
          message:
            type: string
          correlationId:
            type: string
```

### §6 — camelCase property names
```yaml
qsr-camel-case-properties:
  message: "§6: Schema property names must use camelCase. Found: {{value}}"
  severity: warn
  given: "$.components.schemas[*].properties[*]~"
  then:
    function: casing
    functionOptions:
      type: camel
```

### §9 — No PII in path/query parameters
```yaml
qsr-no-pii-in-paths:
  message: "§9: PII must not appear in path or query parameter names. Found: {{value}}"
  severity: error
  given: "$.paths[*][*].parameters[?(@.in=='path' || @.in=='query')].name"
  then:
    function: pattern
    functionOptions:
      notMatch: "(?i)(^email$|^phone$|^mobile$|^fullName$|^firstName$|^lastName$|^address$|^dob$|^ssn$|^password$|^secret$)"
```

---

## Output Format

```yaml
extends: "spectral:oas"
rules:
  qsr-api-versioned-paths:
    ...
  qsr-resource-kebab-case:
    ...
  # one block per style guide section
```

## Quality Rules

- All rule IDs must be prefixed with `qsr-` for traceability
- Severity must be `error` for §1, §4, §5, §8, §9 — these are hard platform requirements
- Use `warn` for §2, §6, §7 — naming and structure conventions
- Every rule must have a `message` that cites the style guide section number
- Do not use `extends` overrides that disable built-in `spectral:oas` rules
- Test your JSONPath mentally: `$.paths[*]~` gives path keys (strings like `/orders`),
  while `$.paths[*]` gives path item objects. Use `~` when you need the key value itself.
