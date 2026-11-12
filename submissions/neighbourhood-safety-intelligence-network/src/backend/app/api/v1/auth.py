from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.core.audit import client_ip, record_audit
from backend.app.core.config import settings
from backend.app.core.rate_limit import LoginThrottle
from backend.app.core.security import (
    DUMMY_PASSWORD_HASH, create_access_token, get_password_hash, verify_password,
)
from backend.app.database.base import get_db
from backend.app.models.entities import Responder, User
from backend.app.schemas.safety_schemas import TokenResponse, UserLogin, UserRegister

router = APIRouter(prefix="/auth", tags=["Authentication"])

login_throttle = LoginThrottle(settings.LOGIN_MAX_ATTEMPTS, settings.LOGIN_WINDOW_SECONDS)


def _token_response(user: User) -> TokenResponse:
    token = create_access_token({"sub": user.email, "role": user.role, "id": user.id})
    return TokenResponse(
        access_token=token,
        token_type="bearer",  # nosec B106 - OAuth token type label, not a credential
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegister, request: Request, db: Session = Depends(get_db)):
    if db.query(User.id).filter(User.email == req.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address is already registered.",
        )

    is_responder = req.role == "responder"
    user = User(
        email=req.email,
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name.strip(),
        phone=req.phone,
        role=req.role,
        is_active=True,
        # Responders can act on incidents only after an admin verifies them.
        is_verified=not is_responder,
        emergency_notes=req.emergency_notes,
        address=req.address,
    )
    db.add(user)
    db.flush()

    if is_responder:
        db.add(Responder(
            user_id=user.id,
            badge_number=f"VOL-{user.id:04d}",
            service_type="community_patrol",
            is_available=False,
            rating=5.0,
            is_verified_by_admin=False,
        ))

    record_audit(db, "user_registered", "user", user.id, user_id=user.id, request=request,
                 details={"role": user.role})
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(req: UserLogin, request: Request, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    throttle_key = f"{client_ip(request)}|{email}"

    retry_after = login_throttle.retry_after(throttle_key)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Please wait and try again.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.email == email).first()
    # Always run one bcrypt check so unknown and known emails take the same time.
    password_ok = verify_password(req.password, user.hashed_password if user else DUMMY_PASSWORD_HASH)

    if not user or not password_ok:
        login_throttle.record_failure(throttle_key)
        record_audit(db, "login_failed", "user", user.id if user else None,
                     user_id=user.id if user else None, request=request)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account has been deactivated.")

    login_throttle.reset(throttle_key)
    record_audit(db, "login_succeeded", "user", user.id, user_id=user.id, request=request)
    db.commit()
    return _token_response(user)
