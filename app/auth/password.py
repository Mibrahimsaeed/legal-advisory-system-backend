from passlib.context import CryptContext

# bcrypt: industry-standard for password hashing. Never store plain-text passwords.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Turn a plain password into an irreversible hash, safe to store in the DB."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a login attempt's password against the stored hash."""
    return _pwd_context.verify(plain_password, hashed_password)
