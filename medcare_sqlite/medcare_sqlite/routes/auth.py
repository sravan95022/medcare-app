from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole
from schemas import RegisterRequest, AdminUserCreate, LoginRequest, Token, UserOut
from utils.security import hash_password, verify_password, create_access_token
from utils.audit import log_action
from dependencies.auth import require_admin

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Public self-registration. Restricted to PATIENT role only.
    Staff accounts (ADMIN / DOCTOR / RECEPTIONIST) must be created via POST /auth/create-user by an admin.
    """
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.PATIENT,           # FIX: always force PATIENT regardless of payload
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, user.id, "REGISTER", "User", user.id)
    return user


@router.post("/create-user", response_model=UserOut, status_code=201)
def admin_create_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin-only endpoint to create staff accounts with any role
    (ADMIN, DOCTOR, RECEPTIONIST, PATIENT).
    """
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, current_user.id, "ADMIN_CREATE_USER", "User", user.id, f"role={payload.role}")
    return user


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email, User.is_active == True).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"user_id": user.id, "role": user.role.value})
    log_action(db, user.id, "LOGIN", "User", user.id)
    return {"access_token": token, "token_type": "bearer"}
