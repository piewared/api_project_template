# JavaScript / TypeScript Client (Browser)

This minimal client shows how to:
- Check auth state and retrieve a CSRF token
- Initiate the login flow (`/auth/web/login`)
- Send CSRF-protected requests
- Refresh the session
- Log out

> Sessions use **HttpOnly** cookies. Include `credentials: 'include'` in fetch calls.  
> Cross-site apps require `SameSite=None` and HTTPS (`Secure=true`).

## Minimal Client

```ts
export class AuthClient {
  private csrfToken: string | null = null;
  constructor(private baseUrl = "http://localhost:8000") {}

  async me() {
    const res = await fetch(`${this.baseUrl}/auth/web/me`, { credentials: "include" });
    if (!res.ok) throw new Error("Failed to fetch auth state");
    const data = await res.json();
    this.csrfToken = data.csrf_token ?? null;
    return data;
  }

  login(provider = "default", returnTo?: string) {
    const p = new URLSearchParams();
    if (provider !== "default") p.set("provider", provider);
    if (returnTo) p.set("return_to", returnTo); // relative path recommended
    window.location.href = `${this.baseUrl}/auth/web/login${p.size ? `?${p}` : ""}`;
  }

  async request(path: string, init: RequestInit = {}) {
    const method = (init.method || "GET").toUpperCase();
    const headers = new Headers(init.headers || {});
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      if (!this.csrfToken) await this.me();
      if (this.csrfToken) headers.set("X-CSRF-Token", this.csrfToken);
      headers.set("Origin", window.location.origin);
    }
    return fetch(`${this.baseUrl}${path}`, { ...init, headers, credentials: "include" });
  }

  async refresh() {
    const res = await this.request("/auth/web/refresh", { method: "POST" });
    if (res.ok) {
      const data = await res.json().catch(() => ({}));
      this.csrfToken = data.csrf_token ?? this.csrfToken;
      return true;
    }
    return false;
  }

  async logout() {
    const res = await this.request("/auth/web/logout", { method: "POST" });
    if (!res.ok) return false;
    const data = await res.json().catch(() => ({}));
    this.csrfToken = null;
    if (data.provider_logout_url) window.location.href = data.provider_logout_url;
    return true;
  }
}
````

## Usage

```ts
const auth = new AuthClient();

// Check state
const state = await auth.me();
if (!state.authenticated) {
  auth.login("default", "/dashboard");
} else {
  // Make CSRF-protected request
  const res = await auth.request("/api/v1/protected", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hello: "world" }),
  });
}
```