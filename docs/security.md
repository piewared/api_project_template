# 🛡️ Security Guide

This document explains the security model used by **FastAPI Production Template** — including authentication flow, CSRF protection, session handling, and best practices for secure deployments.

It builds on the [README’s Authentication section](../README.md#authentication-api) and the [Configuration Guide](./configuration.md).

---

## 🔐 Authentication Model

The template implements a **Backend-for-Frontend (BFF)** architecture using **OpenID Connect (OIDC)** with the Authorization Code + PKCE flow.  
This ensures your frontend never directly handles tokens, and your backend maintains complete control over authentication and sessions.

### Key Concepts

| Concept | Description |
|----------|-------------|
| **OIDC Provider** | External identity service (e.g., Keycloak, Okta, Google, Azure AD). |
| **PKCE** | Proof Key for Code Exchange — prevents interception of authorization codes. |
| **Nonce** | Random value to bind ID tokens to the original request. |
| **State** | Random CSRF token ensuring callback integrity. |
| **Session Cookie** | HttpOnly signed cookie identifying authenticated users. |

---

## 🧭 Authentication Flow

1. **Login Request**  
   The client (usually a browser) calls `/auth/web/login`, optionally specifying a provider.  
   The server:
   - Generates `state`, `nonce`, and a `code_verifier`.
   - Stores them in Redis (ephemeral auth state).
   - Redirects the user to the provider’s authorization endpoint with:
     ```
     response_type=code
     client_id=...
     redirect_uri=http://localhost:8000/auth/web/callback
     state=<random>
     code_challenge=<PKCE-hash>
     ```
2. **User Authenticates**  
   The user logs into the OIDC provider (e.g., Keycloak).

3. **Callback Exchange**  
   The provider redirects the user back to `/auth/web/callback` with a short-lived authorization code.

   The backend:
   - Validates the returned `state` and `nonce`.
   - Exchanges the `code` for tokens using the stored `code_verifier`.
   - Fetches user info from the OIDC provider’s userinfo endpoint.
   - Issues a **signed session cookie** containing session metadata and expiration.

4. **Authenticated Session**  
   The browser now carries a secure, HttpOnly session cookie on subsequent requests.

5. **Logout / Refresh**  
   - `/auth/web/logout`: Invalidates the session and clears cookies.
   - `/auth/web/refresh`: Rotates the session and CSRF tokens (server-side).

---

## 🍪 Session Management

Sessions are **server-managed** using signed cookies and Redis for fast lookups.

| Property | Description |
|-----------|--------------|
| **HttpOnly** | Prevents JavaScript access to cookies. |
| **Secure** | Enforced automatically in production (requires HTTPS). |
| **SameSite** | Defaults to `Lax`; set `None` for cross-origin SPAs. |
| **Expiration** | Configurable via `SESSION_MAX_AGE` (default: 1 hour). |
| **Rotation** | Sessions rotate on refresh to limit replay window. |

### Redis Session Store

- Stores ephemeral authentication state during the OIDC flow (`state`, `nonce`, PKCE verifier).
- Can optionally store session fingerprints or refresh tokens.
- TTLs are automatically managed to prevent buildup of expired sessions.

---

## 🧩 CSRF Protection

Cross-Site Request Forgery (CSRF) protection is implemented using **double-submit tokens** and **Origin header validation**.

| Mechanism | Description |
|------------|-------------|
| **CSRF Token** | Generated and returned by `/auth/web/me`. Required for any state-changing request. |
| **Header Validation** | The frontend must include the token in `X-CSRF-Token` and send the correct `Origin` header. |
| **Session Binding** | CSRF tokens are tied to specific sessions. |

### Example

```bash
# Get CSRF token
CSRF=$(curl -s -b cookies.txt http://localhost:8000/auth/web/me | jq -r '.csrf_token')

# Use it in a state-changing request
curl -X POST -b cookies.txt \
  -H "Origin: http://localhost:8000" \
  -H "X-CSRF-Token: $CSRF" \
  http://localhost:8000/api/v1/products/
````

### Failure Conditions

* Missing or mismatched CSRF token → `403 Forbidden`
* Missing or mismatched `Origin` header → `403 Forbidden`
* Invalid session cookie → `401 Unauthorized`

---

## 🕵️ Client Fingerprinting

Each session is bound to a lightweight **client fingerprint**, derived from:

* User-agent hash
* IP subnet (configurable)
* Session creation timestamp

This reduces risk from stolen cookies reused on different devices.
Fingerprint verification occurs during each authenticated request.

---

## 🔑 JWT & Token Security

JWT validation occurs when integrating with external APIs or when the OIDC provider returns tokens.

| Validation Step      | Description                              |
| -------------------- | ---------------------------------------- |
| **Signature Check**  | Verifies JWT using JWKS from provider.   |
| **Nonce Validation** | Ensures ID token matches original login. |
| **Audience Check**   | Confirms intended API audience.          |
| **Expiration Check** | Rejects expired tokens.                  |

The backend **never stores access tokens** long-term — only session metadata.

---

## 🚦 Rate Limiting & Abuse Prevention

Implemented via Redis with configurable rate windows.

| Policy         | Default | Description             |
| -------------- | ------- | ----------------------- |
| `requests`     | 10      | Max requests per window |
| `window_ms`    | 5000    | Time window (ms)        |
| `per_endpoint` | true    | Limit by route          |
| `per_method`   | true    | Separate GET vs POST    |

Requests exceeding the limit receive a `429 Too Many Requests`.

---

## 🧰 Security Best Practices

### ✅ Development

* Use provided local Keycloak instance only for **testing**.
* Never use its credentials or realm in production.
* Use HTTPS with a self-signed cert if testing cross-origin flows.

### ✅ Production

* Always use a managed IdP (Azure AD, Okta, Auth0, Google, etc.).
* Enforce HTTPS and secure cookies.
* Rotate `SESSION_SIGNING_SECRET` regularly.
* Monitor Redis session TTLs and rate-limiter behavior.
* Configure proper CORS origins (no wildcards).
* Disable debug mode (`APP_ENVIRONMENT=production`).

---

## 🧠 Security Responsibilities

| Layer               | Responsibility                                                           |
| ------------------- | ------------------------------------------------------------------------ |
| **Template**        | Provides secure defaults and validated auth/session flow.                |
| **You (Developer)** | Configure secrets, CORS, and IdP credentials properly.                   |
| **Ops / Infra**     | Enforce HTTPS, handle certificate management, and secure Redis/Postgres. |

---

## 🧩 See Also

* [Configuration Guide](./configuration.md)
* [README — Authentication API](../README.md#authentication-api)
* [docs/clients/javascript.md](javascript.md)
* [docs/clients/python.md](python.md)

