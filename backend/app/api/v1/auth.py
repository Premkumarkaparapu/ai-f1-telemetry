"""Auth endpoints — register, login, profile."""
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.app.core.security import (
    hash_password, verify_password, create_access_token, decode_token
)
from backend.app.database.db import get_db
from backend.app.database.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer(auto_error=False)

F1_TEAMS = [
    "Red Bull Racing", "Ferrari", "Mercedes", "McLaren", "Aston Martin",
    "Alpine", "Williams", "RB (Racing Bulls)", "Haas", "Sauber/Audi",
    "Other / No Team",
]

AVATAR_COLORS = [
    "#e8002d", "#1e41ff", "#27f4d2", "#ff8000", "#006f62",
    "#0093cc", "#005aff", "#b6babd", "#ffffff", "#52e252",
]

# ── Schemas ────────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    team_affiliation: Optional[str] = None
    bio: Optional[str] = None
    avatar_color: Optional[str] = "#e8002d"

    @field_validator("username")
    @classmethod
    def username_valid(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(v) > 40:
            raise ValueError("Username must be at most 40 characters")
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", v):
            raise ValueError("Username may only contain letters, numbers, _ - .")
        return v

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def password_strong(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    team_affiliation: Optional[str] = None
    bio: Optional[str] = None
    avatar_color: Optional[str] = None
    avatar_initials: Optional[str] = None


class UserOut(BaseModel):
    user_id: int
    username: str
    email: str
    full_name: Optional[str]
    team_affiliation: Optional[str]
    bio: Optional[str]
    avatar_color: Optional[str]
    avatar_initials: Optional[str]
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── Helpers ────────────────────────────────────────────────────────────────────

def _initials(full_name: Optional[str], username: str) -> str:
    if full_name:
        parts = full_name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return parts[0][:2].upper()
    return username[:2].upper()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns current user from JWT — None if not authenticated."""
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    uid = payload.get("sub")
    if not uid:
        return None
    return db.query(User).filter(User.user_id == int(uid)).first()


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Raises 401 if not authenticated."""
    user = get_current_user(credentials, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new account."""
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    initials = _initials(req.full_name, req.username)
    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        team_affiliation=req.team_affiliation,
        bio=req.bio,
        avatar_color=req.avatar_color or "#e8002d",
        avatar_initials=initials,
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.user_id)})
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login with email + password, returns JWT token."""
    user = db.query(User).filter(User.email == req.email.strip().lower()).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.user_id)})
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(require_auth)):
    """Return current user profile."""
    return UserOut.model_validate(user)


@router.put("/me", response_model=UserOut)
def update_me(
        req: ProfileUpdateRequest,
        user: User = Depends(require_auth),
        db: Session = Depends(get_db)):
    """Update profile fields."""
    if req.full_name is not None:
        user.full_name = req.full_name
    if req.team_affiliation is not None:
        user.team_affiliation = req.team_affiliation
    if req.bio is not None:
        user.bio = req.bio
    if req.avatar_color is not None:
        user.avatar_color = req.avatar_color
    if req.avatar_initials is not None:
        user.avatar_initials = req.avatar_initials
    elif req.full_name is not None:
        user.avatar_initials = _initials(req.full_name, user.username)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/teams")
def get_teams():
    """Return list of F1 teams for registration dropdown."""
    return {"teams": F1_TEAMS, "avatar_colors": AVATAR_COLORS}
