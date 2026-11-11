from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database.base import get_db
from backend.app.models.entities import User, Responder
from backend.app.schemas.safety_schemas import UserRegister, UserLogin, TokenResponse
from backend.app.core.security import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address is already registered."
        )
    
    hashed_pw = get_password_hash(req.password)
    user = User(
        email=req.email.lower(),
        hashed_password=hashed_pw,
        full_name=req.full_name,
        phone=req.phone,
        role=req.role,
        is_active=True,
        is_verified=(req.role == "resident"),  # responders need admin verification unless self-demonstrating
        emergency_notes=req.emergency_notes,
        address=req.address
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # If registered as responder, provision profile
    if req.role == "responder":
        resp = Responder(
            user_id=user.id,
            badge_number=f"VOL-{user.id:04d}",
            service_type="community_patrol",
            is_available=True,
            rating=5.0,
            is_verified_by_admin=True
        )
        db.add(resp)
        db.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "id": user.id})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role
    )

@router.post("/login", response_model=TokenResponse)
def login(req: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated."
        )

    token = create_access_token({"sub": user.email, "role": user.role, "id": user.id})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role
    )
