---
name: codebase-scanner
description: Use when given Java source files and asked to produce a structured architecture scan. Extracts package inventory, cross-boundary imports, third-party SDK locations, banned library usage, and credential risks. Output feeds the archunit-generator skill.
---

# Codebase Scanner

## Purpose

Read a set of Java source files and produce a structured, factual summary of what is
actually in the code — not what the architecture intends. This summary is the input
to the ArchUnit Generator skill.

Do not make recommendations here. Do not evaluate good or bad. Only report what you observe.

---

## What to Extract

Work through the source files systematically. For each file record:
- Full package name
- Class name and type (determined by suffix and annotations: `*Controller`, `*Service`, `*Repository`, `*Client`, `*Entity`, `*Event`, other)
- All import statements

Then aggregate across all files to produce the sections below.

---

## Output Format

Produce exactly this structure. Every section is required even if empty.

---

### SECTION 1: Package Inventory

List every unique package found, grouped by bounded context (the third segment of the
package path, e.g. `com.example.order`, `com.example.loyalty`).

```
com.example.order
  com.example.order.controller
  com.example.order.application
  com.example.order.domain
  com.example.order.infrastructure
  com.example.order.repository

com.example.loyalty
  ...
```

---

### SECTION 2: Cross-Boundary Import Violations

List every import where a class in one bounded context imports a class from another
bounded context's `domain`, `infrastructure`, or `repository` package.

Format each violation as:
```
VIOLATION: {importing class (full path)} → imports → {imported class (full path)}
  File: {filename}:{line number if available}
```

If none found, write: `None detected.`

---

### SECTION 3: Layer Violations

List every import that violates standard layering within a single bounded context:
- `*.controller.*` importing from `*.repository.*` directly
- `*.domain.*` importing from `*.infrastructure.*` or `*.application.*`
- `*.application.*` importing concrete infrastructure classes (not interfaces)

Format same as Section 2.

If none found, write: `None detected.`

---

### SECTION 4: Third-Party SDK Usage by Layer

For every third-party import (anything not `java.*`, `javax.*`, `jakarta.*`,
`org.springframework.*`, `com.example.*`), record:
- The third-party package
- Which class uses it
- Which layer that class is in (domain / application / infrastructure / controller / unknown)

```
SDK: com.doordash.sdk.*
  Used by: com.example.delivery.domain.DeliveryJob  [layer: domain]
  Used by: com.example.delivery.application.DeliveryCoordinationService  [layer: application]
```

Flag any SDK usage in `domain` or `application` layers as `[CONCERN: should be infrastructure only]`.

---

### SECTION 5: Banned Library Usage

Check for the following and list every occurrence with class name and layer:

- `org.springframework.web.client.RestTemplate`
- `okhttp3.*`
- `io.jsonwebtoken.*` (JJWT — custom JWT parsing)
- Any `*AuthFilter`, `*JwtParser`, `*TokenValidator` classes using non-platform security libs

```
BANNED: org.springframework.web.client.RestTemplate
  Used by: com.example.order.infrastructure.PaymentGatewayClient  [layer: infrastructure]
```

If none found, write: `None detected.`

---

### SECTION 6: Hardcoded Credential Risk

Flag any string literals that match credential patterns:
- Strings matching `*apikey*`, `*api_key*`, `*secret*`, `*password*`, `*token*` (case-insensitive) assigned to variables
- High-entropy string literals (long alphanumeric strings) assigned to fields

Do not print the credential value. Print the variable name, class, and file.

```
RISK: Potential hardcoded credential
  Variable: apiKey  Class: DeliveryConfig  File: DeliveryConfig.java
```

If none found, write: `None detected.`

---

### SECTION 7: Summary Counts

```
Total Java files scanned:     N
Total packages found:         N
Bounded contexts identified:  N  [list them]
Cross-boundary violations:    N
Layer violations:             N
Third-party SDKs in wrong layer: N
Banned library usages:        N
Credential risks:             N
```
