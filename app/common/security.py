import secrets
import string
from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.common.exceptions import InvalidRefreshTokenError, InvalidTokenError, TokenExpiredError
from app.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# --------------------------------------------------------------------------- #
# Password / PIN hashing                                                       #
# --------------------------------------------------------------------------- #


def hash_pin(pin: str) -> str:
    """Hash a plain-text PIN using Argon2."""
    return pwd_context.hash(pin)


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """Verify a plain-text PIN against a stored hash."""
    return pwd_context.verify(plain_pin, hashed_pin)


def generate_pin(length: int = 4) -> str:
    """Generate a cryptographically random numeric PIN."""
    return "".join(secrets.choice(string.digits) for _ in range(length))


# --------------------------------------------------------------------------- #
# JWT                                                                          #
# --------------------------------------------------------------------------- #


def create_access_token(payload: dict) -> str:
    """Create a signed JWT access token."""
    data = payload.copy()
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    data["exp"] = expire
    data["iat"] = datetime.now(UTC)
    return jwt.encode(data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises application-level exceptions."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as exc:
        if "expired" in str(exc).lower():
            raise TokenExpiredError() from exc
        raise InvalidTokenError() from exc


def create_refresh_token(payload: dict) -> str:
    """Create a signed JWT refresh token (30-day lifetime, type='refresh')."""
    data = payload.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    data["exp"] = expire
    data["iat"] = datetime.now(UTC)
    data["type"] = "refresh"
    return jwt.encode(data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a refresh token.

    Raises :class:`InvalidRefreshTokenError` if the token is expired,
    malformed, or has the wrong type claim.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError as exc:
        raise InvalidRefreshTokenError() from exc

    if payload.get("type") != "refresh":
        raise InvalidRefreshTokenError()

    return payload
