# ADR-017: Approved HTTP Client Libraries

**Status:** Accepted  
**Date:** 2024-09-15  
**Deciders:** Platform Engineering, SRE

---

## Context

Multiple services on the platform use different HTTP client libraries — some use
Spring's `RestTemplate`, others use `OkHttp` directly, and some have rolled their
own wrappers. This creates three problems:

1. **Resilience gaps:** Platform-standard circuit breaker, retry, and timeout configuration
   is applied through the WebClient pipeline. Services using other libraries bypass this
   entirely. SRE cannot diagnose or remediate incidents in services using libraries they
   do not own.

2. **Maintenance burden:** `RestTemplate` is in maintenance mode as of Spring 6. It will
   not receive new features and may be removed in a future Spring version.

3. **Observability gaps:** The platform distributed tracing configuration instruments
   WebClient automatically. Services using other libraries produce incomplete traces,
   making incident investigation harder.

## Decision

The only approved HTTP client library for service-to-service and external API calls is:

- `org.springframework.web.reactive.function.client.WebClient`

The following are **banned** from all new code and must be removed from existing code
on a rolling basis:

- `org.springframework.web.client.RestTemplate` — maintenance mode, does not support reactive
- `okhttp3.*` used directly — bypasses platform resilience and tracing configuration

Existing uses of banned libraries must be tracked and migrated. New code using banned
libraries will fail the CI build.

## Naming Conventions

HTTP client wrapper classes are expected to reside in `*.infrastructure.*` or
`*.infrastructure.client.*` packages and have a suffix of `Client`.

## Consequences

**Positive:** Uniform circuit breaker and retry behaviour across the platform.
SRE can reason about and configure all service HTTP behaviour consistently.
Distributed traces are complete.

**Negative:** Teams using RestTemplate or OkHttp must migrate. For services with
many outbound calls this is non-trivial work.

## Enforcement

ArchUnit rule banning import of `org.springframework.web.client.RestTemplate` and
`okhttp3.*` platform-wide. Rule ID: `FF-HTTP-CLIENT`.
