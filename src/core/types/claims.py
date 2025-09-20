from typing import Optional, Set

from pydantic import BaseModel


class JwtClaims(BaseModel):
    """Canonical representation of JWT claims used across the app."""

    iss: str
    sub: str
    aud: Optional[str] = None
    exp: Optional[int] = None
    nbf: Optional[int] = None
    scope: Optional[str] = None
    scp: Optional[list[str]] = None
    roles: Optional[list[str]] = None
    realm_access: Optional[dict] = None

    def scopes(self) -> Set[str]:
        scopes: Set[str] = set()
        if self.scope:
            scopes.update(self.scope.split())
        if self.scp:
            scopes.update(self.scp)
        return scopes

    def roles_list(self) -> Set[str]:
        roles: Set[str] = set(self.roles or [])
        realm = self.realm_access or {}
        if isinstance(realm.get("roles"), list):
            roles.update(realm["roles"])
        return roles
