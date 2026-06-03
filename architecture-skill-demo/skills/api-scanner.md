---
name: api-scanner
description: Use when given source files from any language to extract the REST API surface. Produces a structured inventory of endpoints, HTTP methods, request/response shapes, versioning, error handling, and PII exposure for the OpenAPI Generator skill.
---

# API Scanner

## Purpose

Read the provided source files and produce a structured API inventory report. This report
is the input to the OpenAPI Generator and Spectral Ruleset Generator skills. Report only
what you observe — do not make recommendations.

---

## Language Patterns to Recognise

| Language | Route declaration |
|----------|-------------------|
| Java Spring | `@RequestMapping`, `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, `@PatchMapping` on class or method |
| Python FastAPI | `@app.get`, `@app.post`, `@router.get`, `@router.post`, etc. |
| Python Flask | `@app.route(path, methods=[...])` |
| Node.js Express | `router.get(path, ...)`, `app.post(path, ...)`, `router.use(path, ...)` |
| Go Gin | `r.GET(path, ...)`, `r.POST(path, ...)`, `group.GET(...)` |
| Ruby on Rails | `resources :name`, `get 'path', to: 'controller#action'` |

For Java Spring: combine the class-level `@RequestMapping` prefix with each method-level
mapping to form the full path. e.g. `@RequestMapping("/orders")` on class +
`@GetMapping("/{id}")` on method = `GET /orders/{id}`.

---

## What to Extract Per Endpoint

For each route found, extract:

1. **HTTP method** — GET, POST, PUT, PATCH, DELETE
2. **Full path** — include class-level prefix + method-level path + path variables
3. **Path parameters** — `{name}` segments in the path; note `@PathVariable` in Java
4. **Query parameters** — `@RequestParam` in Java, `Query(...)` in FastAPI, `req.query` in Node
5. **Request body** — DTO/model class name and its field names + types if accessible
6. **Response type** — return type or response class name
7. **Explicit status codes** — `@ResponseStatus(HttpStatus.CREATED)`, `return ResponseEntity.status(201)`, etc.
8. **Error handling** — is there a `@ExceptionHandler` or global error handler with a standard error class?

---

## Governance Checks Per Endpoint

After extracting, evaluate each endpoint against these checks:

| § | Check | How to detect |
|---|-------|--------------|
| §1 | Version prefix | Does the full path start with `/v` followed by an integer? e.g. `/v1/`, `/v2/` |
| §2 | Resource naming | Are path segments lowercase kebab-case? Are resource names plural nouns? Any verbs in the path (other than action suffixes on the last segment)? |
| §4 | POST → 201 | Does a POST operation explicitly declare 201 Created? |
| §5 | Standard error response | Is there a shared error class/struct with `code`, `message`, `correlationId` fields used across error responses? |
| §6 | Response DTO | Does the response type appear to be a domain entity (lives in a `domain` or `model` package) rather than a dedicated API response DTO? |
| §7 | Pagination | For GET endpoints that return a list or array — is there a pagination wrapper with `data` and `pagination` fields? |
| §9 | PII in paths | Do path or query parameter names suggest PII: `email`, `phone`, `name`, `address`, `dob`, `ssn`? |

Mark each check as PASS, FAIL, or N/A (pagination only applies to list endpoints).

---

## Output Format

Produce this exact structure:

```
# API Scan Report

**Service:** {service name from context}
**Source root:** {path}
**Files scanned:** {N}
**Language detected:** {Java Spring | Python FastAPI | Node Express | etc.}

---

## Endpoints Found

### {HTTP_METHOD} {full path}
- **Declared in:** {filename}
- **Path parameters:** {list or "none"}
- **Query parameters:** {list or "none"}
- **Request body:** {class name + fields, or "none"}
- **Response type:** {class or type name}
- **Explicit status codes:** {list, or "none — implicit 200"}
- **Governance:**
  - §1 Versioning: PASS / FAIL — {reason}
  - §2 Resource naming: PASS / FAIL — {reason}
  - §4 POST → 201: PASS / FAIL / N/A — {reason}
  - §5 Error response: PASS / FAIL — {reason}
  - §6 Response DTO: PASS / FAIL — {reason}
  - §7 Pagination: PASS / FAIL / N/A — {reason}
  - §9 PII in paths: PASS / FAIL — {reason}

(repeat for each endpoint)

---

## Summary

| Check | Endpoints scanned | Violations |
|-------|-------------------|------------|
| §1 Versioning | N | N |
| §2 Resource naming | N | N |
| §4 POST → 201 | N | N |
| §5 Error response | N | N |
| §6 Response DTO | N | N |
| §7 Pagination | N | N |
| §9 PII in paths | N | N |

```
