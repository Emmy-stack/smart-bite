import os
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole

# Reusable security scheme to extract Bearer token
http_bearer = HTTPBearer(auto_error=False)

# Cached PyJWKClient instance
_jwks_client: Optional[PyJWKClient] = None

def get_jwks_client() -> PyJWKClient:
    """
    Returns a cached PyJWKClient instance for Clerk.
    Validates required Clerk configuration and caches keys for 1 hour.
    """
    global _jwks_client
    if _jwks_client is None:
        settings.validate_auth_config()
        _jwks_client = PyJWKClient(
            settings.jwks_url,
            cache_keys=True,
            max_cached_keys=16,
            lifespan=3600
        )
    return _jwks_client


def verify_clerk_token(token: str, client: Optional[PyJWKClient] = None) -> Dict[str, Any]:
    """
    Verifies a Clerk session JWT:
    1. Extracts signing key using Clerk's published JWKS.
    2. Validates RS256 signature.
    3. Validates issuer, expiration, and required 'sub' claim.
    4. Returns verified claims.
    """
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing or empty",
            headers={"WWW-Authenticate": "Bearer"}
        )

    jwks = client or get_jwks_client()
    try:
        signing_key = jwks.get_signing_key_from_jwt(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token header or signing key: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "require": ["sub", "exp", "iss"],
            }
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject ('sub') claim",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return payload


def get_current_clerk_claims(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer)
) -> Dict[str, Any]:
    """
    Dependency that extracts the Bearer token from the Authorization header
    and verifies it against Clerk's JWKS.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization Bearer token required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return verify_clerk_token(credentials.credentials)


def get_current_user_optional(
    claims: Dict[str, Any] = Depends(get_current_clerk_claims),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Looks up the application user associated with the verified Clerk identity.
    Returns None if the user has not completed onboarding.
    """
    clerk_id = claims.get("sub")
    if not clerk_id:
        return None
    return db.query(User).filter(User.clerk_id == clerk_id).first()


def get_current_user(
    claims: Dict[str, Any] = Depends(get_current_clerk_claims),
    db: Session = Depends(get_db)
) -> User:
    """
    Ensures the caller has a verified Clerk token AND has completed onboarding
    in the local database. Returns the User model instance.
    """
    clerk_id = claims.get("sub")
    user = db.query(User).filter(User.clerk_id == clerk_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has not completed onboarding. Please onboard at /auth/onboard/restaurant or /auth/onboard/ngo"
        )
    return user


def get_current_restaurant_user(
    user: User = Depends(get_current_user)
) -> User:
    """
    Ensures the authenticated user has the 'restaurant' role and an active restaurant profile.
    """
    if user.role != UserRole.RESTAURANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Restaurant role required"
        )
    if not user.restaurant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restaurant profile not found for this account"
        )
    return user


def get_current_ngo_user(
    user: User = Depends(get_current_user)
) -> User:
    """
    Ensures the authenticated user has the 'ngo' role and an active NGO profile.
    """
    if user.role != UserRole.NGO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: NGO role required"
        )
    if not user.ngo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NGO profile not found for this account"
        )
    return user
