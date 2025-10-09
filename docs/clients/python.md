# Python Client (requests)

This minimal client shows how to:
- Check auth state and retrieve a CSRF token
- Build a login URL for manual redirection (useful in non-browser contexts)
- Send CSRF-protected requests
- Refresh the session
- Log out

> Sessions use **HttpOnly** cookies, persisted by `requests.Session()`.

## Minimal Client

```python
from typing import Optional, Dict, Any
from urllib.parse import urlencode
import requests

class AuthClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.csrf_token: Optional[str] = None

    def me(self) -> Dict[str, Any]:
        r = self.session.get(f"{self.base_url}/auth/web/me")
        r.raise_for_status()
        data = r.json()
        self.csrf_token = data.get("csrf_token")
        return data

    def login_url(self, provider: str = "default", return_to: Optional[str] = None) -> str:
        params = {}
        if provider != "default":
            params["provider"] = provider
        if return_to:
            params["return_to"] = return_to  # relative path recommended
        qs = f"?{urlencode(params)}" if params else ""
        return f"{self.base_url}/auth/web/login{qs}"

    def request(self, path: str, method: str = "GET", **kwargs) -> requests.Response:
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            if not self.csrf_token:
                self.me()
            headers = kwargs.get("headers", {})
            if self.csrf_token:
                headers["X-CSRF-Token"] = self.csrf_token
            headers.setdefault("Origin", self.base_url)
            kwargs["headers"] = headers
        return self.session.request(method, f"{self.base_url}{path}", **kwargs)

    def refresh(self) -> bool:
        r = self.request("/auth/web/refresh", method="POST")
        if r.ok:
            data = r.json()
            self.csrf_token = data.get("csrf_token", self.csrf_token)
            return True
        return False

    def logout(self) -> bool:
        r = self.request("/auth/web/logout", method="POST")
        if not r.ok:
            return False
        self.csrf_token = None
        # Optionally inspect r.json().get("provider_logout_url")
        return True
````

## Usage

```python
client = AuthClient()

state = client.me()
if not state.get("authenticated"):
    print("Open this URL in a browser:", client.login_url("default", "/dashboard"))
else:
    r = client.request("/api/v1/protected", method="POST", json={"hello": "world"})
    print(r.status_code, r.text)
```