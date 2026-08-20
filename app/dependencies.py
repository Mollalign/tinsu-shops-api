"""
Global FastAPI dependencies shared across modules.
"""
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import UserRole
from app.common.exceptions import (
    InactiveAccountError,
    NotAuthenticatedError,
    UnauthorizedShopAccessError,
)
from app.common.security import decode_access_token
from app.database import get_db

http_bearer = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    """Decoded JWT payload surfaced as a dependency."""

    def __init__(self, payload: dict):
        self.id: UUID = UUID(payload["sub"])
        self.role: UserRole = UserRole(payload["role"])
        self.name: str = payload.get("name", "")
        self.shop_id: UUID | None = (
            UUID(payload["shop_id"]) if payload.get("shop_id") else None
        )
        self.is_active: bool = payload.get("is_active", True)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(http_bearer)
    ] = None,
) -> AuthenticatedUser:
    if not credentials:
        raise NotAuthenticatedError()
    payload = decode_access_token(credentials.credentials)
    user = AuthenticatedUser(payload)
    if not user.is_active:
        raise InactiveAccountError()
    return user


async def require_owner(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if current_user.role != UserRole.OWNER:
        from app.common.exceptions import OwnerOnlyError
        raise OwnerOnlyError()
    return current_user


async def require_worker(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if current_user.role != UserRole.WORKER:
        from app.common.exceptions import OwnerOnlyError
        raise OwnerOnlyError()  # worker-only, reuse pattern
    return current_user


async def require_authenticated(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    return current_user


def require_shop_access(shop_id_param: str = "shop_id"):
    """
    Factory that returns a dependency verifying the authenticated user
    has access to the given shop_id path parameter.
    """
    async def _check(
        shop_id: UUID,
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if current_user.role == UserRole.OWNER:
            # Owner access is verified in each service by checking shop.owner_id
            pass
        elif current_user.role == UserRole.WORKER:
            if current_user.shop_id != shop_id:
                raise UnauthorizedShopAccessError()
        return current_user

    return _check
