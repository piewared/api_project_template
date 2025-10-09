# 🔐 Keycloak Development Environment

This directory provides the **local Keycloak service** used for OIDC authentication during development and testing.  
It runs Keycloak in **development mode** with **automatic realm, client, and user configuration** through a lightweight setup script container.

---

## ✨ Features

- **Keycloak 24.0** running in dev mode (HTTP, no TLS)
- **Automatic setup** via the `keycloak-setup` container (runs once after Keycloak is healthy)
- **Preconfigured OIDC Realm** (`test-realm`) with client and test users
- **Persistent data** stored in a Docker volume
- **Compatible with** your local FastAPI backend and CLI

---

## ⚙️ Usage

### Start Keycloak with auto-configuration

From the project root:
```bash
./setup_dev.sh
````

Or directly:

```bash
cd dev_env/keycloak
docker compose up -d
```

The `keycloak-setup` container automatically:

* Waits for Keycloak’s health check
* Installs `requests`
* Runs [`setup_script.py`](../../dev_env/keycloak/setup_script.py)
  → which configures the test realm, client, and users

---

## 🧩 OIDC Configuration

Automatically created during setup:

| Setting           | Value                                     |
| ----------------- | ----------------------------------------- |
| **Realm**         | `test-realm`                              |
| **Client ID**     | `test-client`                             |
| **Client Secret** | `test-client-secret`                      |
| **Redirect URI**  | `http://localhost:8000/auth/web/callback` |
| **Issuer**        | `http://localhost:8080/realms/test-realm` |

### Default OIDC Endpoints

| Type          | URL                                                                        |
| ------------- | -------------------------------------------------------------------------- |
| Authorization | `http://localhost:8080/realms/test-realm/protocol/openid-connect/auth`     |
| Token         | `http://localhost:8080/realms/test-realm/protocol/openid-connect/token`    |
| Userinfo      | `http://localhost:8080/realms/test-realm/protocol/openid-connect/userinfo` |
| JWKS          | `http://localhost:8080/realms/test-realm/protocol/openid-connect/certs`    |
| End Session   | `http://localhost:8080/realms/test-realm/protocol/openid-connect/logout`   |

---

## 👥 Test Users

| Username    | Email                   | Password      |
| ----------- | ----------------------- | ------------- |
| `testuser1` | `testuser1@example.com` | `password123` |
| `testuser2` | `testuser2@example.com` | `password123` |

---

## 🧾 Environment Variables

Your application can use these local defaults (preloaded in `.env`):

```bash
OIDC_KEYCLOAK_CLIENT_ID=test-client
OIDC_KEYCLOAK_CLIENT_SECRET=test-client-secret
OIDC_KEYCLOAK_ISSUER=http://localhost:8080/realms/test-realm
OIDC_KEYCLOAK_AUTHORIZATION_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/auth
OIDC_KEYCLOAK_TOKEN_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/token
OIDC_KEYCLOAK_USERINFO_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/userinfo
OIDC_KEYCLOAK_JWKS_URI=http://localhost:8080/realms/test-realm/protocol/openid-connect/certs
OIDC_KEYCLOAK_END_SESSION_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/logout
OIDC_KEYCLOAK_REDIRECT_URI=http://localhost:8000/auth/web/callback
```

> In production, replace these with credentials from your real OIDC provider (e.g., Okta, Auth0, Azure AD).

---

## 🧠 Manual Setup (if auto-setup fails)

You can re-run the setup manually:

```bash
# From the project root
docker compose run --rm keycloak-setup
# or directly using Python (requires Keycloak running)
python src/dev/setup_keycloak.py
```

---

## 🧩 Troubleshooting

### ❌ `keycloak-setup` container fails

1. Check Keycloak logs:

   ```bash
   docker compose logs keycloak
   ```
2. Check setup container logs:

   ```bash
   docker compose logs keycloak-setup
   ```
3. Retry setup:

   ```bash
   docker compose run --rm keycloak-setup
   ```

### 🚫 Keycloak won’t start

1. Ensure Docker is running.
2. Check if port `8080` is in use:

   ```bash
   lsof -i :8080
   ```
3. Remove existing containers/volumes:

   ```bash
   docker compose down -v
   docker compose up -d
   ```

### 🔄 Reset Keycloak completely

```bash
docker compose down -v
docker compose up -d
```

This will delete all local realm, user, and client data.

---

## 📁 Files

| File                                         | Purpose                                                  |
| -------------------------------------------- | -------------------------------------------------------- |
| [`docker-compose.yml`](../../dev_env/keycloak/docker-compose.yml) | Keycloak service definition                              |
| [`setup_script.py`](../../dev_env/keycloak/setup_script.py)       | Runs automatically to configure realm, client, and users |
| [`README.md`](./README.md)                   | This documentation                                       |
| `keycloak-data/`                             | Docker volume mount for persistent storage               |

---

## ⚠️ Notes

* **Admin credentials:** `admin / admin`
* **Mode:** development (no HTTPS, relaxed security)
* **Port:** 8080
* **Volume:** `keycloak_data`

> This service is designed **only for local development**.
> In production, configure your app to use an external or managed OIDC provider.

