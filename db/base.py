from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy models.
    Import this in every models.py (e.g. app/users/models.py) so that
    Alembic autogenerate can discover all tables via Base.metadata.
    """
    pass
