"""Security utilities — stub only. Auth is handled by Clerk on the frontend."""
import os


SECRET_KEY = os.environ.get("F1_SECRET_KEY", "f1-telemetry-super-secret-key-2025")


def hash_password(plain: str) -> str:
    """No-op stub — password auth replaced by Clerk."""
    return ""


def verify_password(plain: str, hashed: str) -> bool:
    """No-op stub — password auth replaced by Clerk."""
    return False


def create_access_token(data: dict, expires_delta=None) -> str:
    """No-op stub — tokens issued by Clerk."""
    return ""


def decode_token(token: str):
    """No-op stub — tokens verified by Clerk."""
    return None
