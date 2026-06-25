from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Patient, User, MedicalRecord, Prescription, Appointment, UserRole
from schemas import PatientCreate, PatientOut, MedicalRecordOut, PrescriptionOut, AppointmentOut
from dependencies.auth import get_current_user, require_receptionist, require_staff
from typing import List
from utils.audit import log_action

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post("/", response_model=PatientOut, status_code=201)
def register_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_receptionist),
):
    """
    Receptionist creates a patient profile for an existing user account.
    FIX: user_id comes from the request payload (the patient's user), not current_user.id.
    """
    # Ensure the target user exists
    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found. The patient must have a registered account first.")

    # Prevent duplicate patient profile for the same user
    if db.query(Patient).filter(Patient.user_id == payload.user_id).first():
        raise HTTPException(status_code=400, detail="A patient profile already exists for this user")

    # Prevent duplicate phone
    if db.query(Patient).filter(Patient.phone == payload.phone).first():
        raise HTTPException(status_code=400, detail="Patient with this phone number already exists")

    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    log_action(db, current_user.id, "CREATE_PATIENT", "Patient", patient.id)
    return patient


@router.get("/", response_model=List[PatientOut])
def list_patients(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    return db.query(Patient).offset(skip).limit(limit).all()


@router.get("/me", response_model=PatientOut)
def my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/{patient_id}/medical-history", response_model=List[MedicalRecordOut])
def get_medical_history(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient or patient.id != patient_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return db.query(MedicalRecord).filter(MedicalRecord.patient_id == patient_id).all()


@router.get("/{patient_id}/prescriptions", response_model=List[PrescriptionOut])
def get_prescriptions(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient or patient.id != patient_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return db.query(Prescription).filter(Prescription.patient_id == patient_id).all()


@router.get("/{patient_id}/appointments", response_model=List[AppointmentOut])
def get_appointments(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient or patient.id != patient_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return db.query(Appointment).filter(Appointment.patient_id == patient_id).all()
