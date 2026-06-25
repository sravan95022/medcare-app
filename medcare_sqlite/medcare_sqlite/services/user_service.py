"""
User & patient/doctor profile creation logic.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import User, Patient, Doctor, UserRole
from utils.security import hash_password
from utils.audit import log_action


def create_user(db: Session, username: str, email: str, password: str, role: UserRole) -> User:
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def create_patient_profile(db: Session, user_id: int, data: dict) -> Patient:
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if db.query(Patient).filter(Patient.user_id == user_id).first():
        raise HTTPException(status_code=400, detail="Patient profile already exists for this user")
    if db.query(Patient).filter(Patient.phone == data.get("phone")).first():
        raise HTTPException(status_code=400, detail="Patient with this phone already exists")

    patient = Patient(user_id=user_id, **data)
    db.add(patient)
    db.flush()
    return patient


def create_doctor_profile(db: Session, user_id: int, data: dict) -> Doctor:
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    if db.query(Doctor).filter(Doctor.user_id == user_id).first():
        raise HTTPException(status_code=400, detail="Doctor profile already exists for this user")

    doctor = Doctor(user_id=user_id, **data)
    db.add(doctor)
    db.flush()
    return doctor
