import base64
import time

from authlib.jose import jwt


def oct_jwk(key: bytes, kid: str) -> dict[str, str]:
    return {
        "kty": "oct",
        "k": base64.urlsafe_b64encode(key).rstrip(b"=").decode("ascii"),
        "alg": "HS256",
        "kid": kid,
    }
