from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole
from utils.security import decode_token
from typing import List

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload:
        raise credentials_exception

    user_id: int = payload.get("user_id")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise credentials_exception
    return user


def require_roles(*roles: UserRole):
    """Factory to create role-based dependency."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return role_checker


# Shorthand role dependencies
require_admin = require_roles(UserRole.ADMIN)
require_doctor = require_roles(UserRole.DOCTOR, UserRole.ADMIN)
require_receptionist = require_roles(UserRole.RECEPTIONIST, UserRole.ADMIN)
require_patient = require_roles(UserRole.PATIENT)
require_staff = require_roles(UserRole.ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST)
