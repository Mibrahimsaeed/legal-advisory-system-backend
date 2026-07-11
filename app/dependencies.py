"""
Shared FastAPI Depends() used across multiple routers.

Phase 1 only wires up the DB session dependency (re-exported here for
convenience). get_current_user and get_redis will be added in Phase 2
once auth and caching exist.
"""

from db.session import get_db  # re-exported: `from app.dependencies import get_db`

__all__ = ["get_db"]
