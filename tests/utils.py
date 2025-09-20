import base64
import time
from typing import Dict
from authlib.jose import jwt


def oct_jwk(key: bytes, kid: str) -> Dict[str, str]:
    return {
        "kty": "oct",
        "k": base64.urlsafe_b64encode(key).rstrip(b"=").decode("ascii"),
        "alg": "HS256",
        "kid": kid,
    }


def encode_token(
    *, issuer: str, audience: str, key: bytes, kid: str, extra_claims: Dict[str, object]
) -> str:
    payload = {
        "iss": issuer,
        "aud": audience,
        "exp": int(time.time()) + 60,
        "nbf": int(time.time()) - 5,
        **extra_claims,
    }
    token_bytes = jwt.encode({"alg": "HS256", "kid": kid}, payload, key)
    return token_bytes.decode("ascii")
