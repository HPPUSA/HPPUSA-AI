# HPPUSA-AI — Origin Trust Deployment Prerequisites
**Status:** Isolated implementation proposal / NOT configured / NOT production-approved  
**Branch:** `orchestra/phase1-hardening`  
**Purpose:** Prevent direct requests to the public Render origin from being treated as trusted Cloudflare traffic merely because they supply a spoofed `CF-Connecting-IP` header.

## 1. Design

The isolated application now requires both:
1. A valid `X-HPPUSA-Origin-Auth` request header whose value matches the server-side `HPPUSA_ORIGIN_AUTH_TOKEN` environment variable; and
2. A syntactically valid `CF-Connecting-IP` address for the application rate limiter.

The production token comparison uses constant-time `hmac.compare_digest`. If the Render environment variable is absent, `/chat` fails closed with HTTP 503. If the header is absent or incorrect, `/chat` returns HTTP 403. No production token value is included in source code, responses, logs, or this document. The isolated test harness and CI workflow contain a clearly test-only placeholder value; it is not a production credential and must never be reused in Cloudflare or Render.

This is an origin-authentication control, not proof of a complete network-level private origin. The Render public web service and homepage remain publicly reachable. The protected resource is the `/chat` endpoint.

## 2. Required account-side configuration — NOT performed

The owner must first confirm:
- A custom HPPUSA hostname already exists and is attached to the Render HPPUSA-AI web service.
- Its DNS record is proxied through a Cloudflare zone controlled by HPPUSA.
- The owner can access both Cloudflare DNS/Rules and the Render service Environment settings.
- The Render GitHub integration remains functional if any repository-visibility decision is later considered. Do not change repository visibility as part of this setup.

Cloudflare's official documentation states that Request Header Transform Rules are available on all Cloudflare plans, including Free (10 active Transform Rules), and require proxied DNS. Confirm the current account interface and rule quota before setup.

## 3. Cloudflare request-header rule — owner configuration required

Create one Request Header Transform Rule scoped narrowly to the verified custom hostname, POST method, and exact `/chat` path.

Expression template (replace the hostname only after verifying the real HPPUSA hostname):

```
http.host eq "VERIFIED-HPPUSA-HOSTNAME"
and http.request.method eq "POST"
and http.request.uri.path eq "/chat"
```

Action:
- Operation: **Set static**
- Header name: `X-HPPUSA-Origin-Auth`
- Header value: a newly generated, high-entropy random secret known only to the owner, Cloudflare rule, and Render environment.

A Set operation must overwrite any client-supplied value of this header at Cloudflare's edge. Do not use a `CF-` or `X-CF-` header name. Do not place the secret in a URL, repository, workflow, commit, screenshot, chat, or log.

Generate the secret locally using a password manager or a cryptographically secure random generator. Do not ask the owner to paste it into ChatGPT.

## 4. Render environment — owner configuration required

Add the exact same secret as a Render environment variable:
- Name: `HPPUSA_ORIGIN_AUTH_TOKEN`
- Value: the locally generated secret.

Do not replace all existing environment variables. Add/merge this single variable only after the isolated code has passed CI and owner approves a staged deployment. Never expose the value in screenshots or support logs.

## 5. Required verification before production release

Use a separate staging service or a deliberately approved maintenance window; do not test by changing the live service without owner authorization.

Acceptance checks:
1. Request to the proxied custom hostname's `POST /chat` receives the Cloudflare-injected header at the origin and passes the origin-authentication gate.
2. Direct request to `https://hppusa-ai.onrender.com/chat` without the secret receives HTTP 403 (or HTTP 503 if the Render token variable is deliberately absent).
3. Direct request with a spoofed `CF-Connecting-IP` but without the origin token still receives HTTP 403.
4. A wrong token receives HTTP 403.
5. A missing server-side token fails closed with HTTP 503.
6. A valid token with a missing or malformed Cloudflare client-IP header still fails closed with HTTP 503.
7. Normal proxied homepage and chat behavior work after the edge rule is active.
8. No secret appears in logs, response bodies, Git history, build artifacts, or client-side HTML/JavaScript.

Record actual request/response evidence and the exact tested hostname. A local Flask test is not a substitute for the direct-origin/proxied-host integration test.

## 6. Rollback and recovery

If the Cloudflare rule or Render environment is incomplete, do not deploy the isolated branch. If a separately authorized staged rollout fails, restore the previous staged application version and remove/rotate the staged token as appropriate. Never disable the production gate or weaken the main branch to make a test pass.

## 7. Current limitations

- HPPUSA's actual custom hostname and Cloudflare zone ownership were not verified during this isolated implementation.
- No Cloudflare rule was created.
- No Render environment variable was added.
- No production or staging request was made.
- The token is not generated or stored in this repository.
- This design does not hide the public Render hostname or protect the homepage from direct viewing; it prevents unauthenticated direct-origin access to `/chat` if configured correctly.
- This is not a substitute for WAF rules, DDoS protection, distributed rate limiting, secret rotation procedures, or independent security testing.


## 8. Isolated implementation and CI update — 2026-11-22

- Added the shared-origin-token gate to the isolated `App.py` branch only.
- Added unit tests for missing and incorrect origin tokens.
- Updated the isolated workflow's localhost Gunicorn smoke test to supply a CI-only placeholder token.
- Added this deployment-prerequisites document.
- Latest isolated workflow run #53 completed successfully: five of five jobs passed. Python regression suite: 30 passed on each of Python 3.11, 3.13 and 3.14.8 (90 test executions across the matrix). Frontend XSS suite passed. Node dependency lockfile generation and clean `npm ci` validation passed.
- The workflow generated a temporary review artifact; it is not committed to the branch. Artifact ID: `14769741639`, ZIP SHA-256: `60b458466317cb5e3cc5c7455c57870e924219b3e4b6daa5c96a72be874497bb`. The extracted `package-lock.json` has 45 dependency entries, all with `resolved` and `integrity` fields; SHA-256: `53cc60cdefd03ad270a8c3b1a84c883b78cfe6e42712bf7bb949b35ed10fe80a`. The artifact expires 2026-11-29.
- Two earlier runs (#51 and #52) failed during the sequential code/workflow update because they ran against intermediate commits with mismatched test/CI token configuration. The final run #53 passed after the workflow and tests were aligned. Do not count the intermediate failures as current unresolved failures, but retain them in the audit trail.
- No Cloudflare rule, Render environment variable, live request, merge, production setting change, or deployment was performed.
