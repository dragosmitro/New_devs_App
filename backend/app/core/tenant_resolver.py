"""
Tenant resolver for authentication.

Resolution priority:
  1. JWT token claims
  2. Database lookup (user_tenants table)
  3. Known email mapping (seed/test users)
"""
from typing import Optional
import logging

from jose import JWTError, jwt
from sqlalchemy import text

from app.config import settings
from app.core.database_pool import db_pool

logger = logging.getLogger(__name__)

# Known test/seed user mappings — only used as a last resort
_EMAIL_TENANT_MAP = {
    "sunset@propertyflow.com": "tenant-a",
    "ocean@propertyflow.com": "tenant-b",
    "candidate@propertyflow.com": "tenant-a",
}


class TenantResolver:
    """Resolves tenant_id from JWT claims, database, or known email mapping."""

    @staticmethod
    def resolve_tenant_from_token(token_payload: dict) -> Optional[str]:
        """Extract tenant_id from a decoded JWT payload."""
        for key in ("user_metadata", "app_metadata"):
            tenant_id = token_payload.get(key, {}).get("tenant_id")
            if tenant_id:
                return tenant_id

        return token_payload.get("tenant_id")

    @staticmethod
    def resolve_tenant_from_user(user_data: dict) -> Optional[str]:
        """Extract tenant_id from user data dictionary."""
        if tenant_id := user_data.get("tenant_id"):
            return tenant_id

        for key in ("user_metadata", "app_metadata"):
            tenant_id = user_data.get(key, {}).get("tenant_id")
            if tenant_id:
                return tenant_id

        return None

    @staticmethod
    async def resolve_tenant_id(user_id: str, user_email: str, token: Optional[str] = None) -> str:
        """
        Resolve tenant ID for a user.

        Tries JWT claims, then database, then known email map.
        Raises ValueError if no tenant can be determined.
        """
        # 1. JWT token claims
        if token:
            try:
                payload = jwt.decode(
                    token, settings.secret_key,
                    algorithms=["HS256"],
                    options={"verify_aud": False},
                )
                tenant_id = TenantResolver.resolve_tenant_from_token(payload)
                if tenant_id:
                    return tenant_id
            except JWTError:
                pass

        # 2. Database lookup
        try:
            await db_pool.initialize()
            if db_pool.session_factory:
                async with db_pool.get_session() as session:
                    result = await session.execute(
                        text("SELECT tenant_id FROM user_tenants WHERE user_id = :uid AND is_active = true LIMIT 1"),
                        {"uid": user_id},
                    )
                    row = result.fetchone()
                    if row:
                        return row.tenant_id
        except Exception as e:
            logger.warning(f"Database tenant lookup failed for {user_email}: {e}")

        # 3. Known email mapping
        tenant_id = _EMAIL_TENANT_MAP.get(user_email)
        if tenant_id:
            return tenant_id

        raise ValueError(f"No tenant found for user {user_email} ({user_id})")

    @staticmethod
    async def update_user_tenant_metadata(user_id: str, tenant_id: str) -> None:
        """Update user metadata with tenant_id (no-op in this implementation)."""
        pass
