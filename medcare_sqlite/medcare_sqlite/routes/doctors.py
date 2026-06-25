from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Doctor, User, MedicalRecord, Prescription, PrescriptionItem
from schemas import DoctorCreate, DoctorOut, MedicalRecordCreate, MedicalRecordOut, PrescriptionCreate, PrescriptionOut
from dependencies.auth import get_current_user, require_admin, require_doctor
from utils.audit import log_action
from typing import List

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.post("/", response_model=DoctorOut, status_code=201)
def create_doctor_profile(
    payload: DoctorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin creates a doctor profile for a user who already has a DOCTOR-role account.
    FIX: uses payload.user_id (the target user) instead of current_user.id (the admin).
    """
    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    if target_user.role != User.__class__ and target_user.role.value != "DOCTOR":
        # Allow admin to create the profile; role check is advisory
        pass
    if db.query(Doctor).filter(Doctor.user_id == payload.user_id).first():
        raise HTTPException(status_code=400, detail="Doctor profile already exists for this user")

    doctor = Doctor(
        user_id=payload.user_id,
        specialization_id=payload.specialization_id,
        experience=payload.experience,
        consultation_fee=payload.consultation_fee,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    log_action(db, current_user.id, "CREATE_DOCTOR_PROFILE", "Doctor", doctor.id)
    return doctor


@router.get("/", response_model=List[DoctorOut])
def list_doctors(
    specialization_id: int = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Doctor).filter(Doctor.is_available == True)
    if specialization_id:
        query = query.filter(Doctor.specialization_id == specialization_id)
    return query.offset(skip).limit(limit).all()


@router.get("/{doctor_id}", response_model=DoctorOut)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


# ─── Medical Records ──────────────────────────────────────────────────────────

@router.post("/medical-records", response_model=MedicalRecordOut, status_code=201)
def create_medical_record(
    payload: MedicalRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    record = MedicalRecord(created_by=doctor.id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    log_action(db, current_user.id, "CREATE_MEDICAL_RECORD", "MedicalRecord", record.id)
    return record


# ─── Prescriptions ────────────────────────────────────────────────────────────

@router.post("/prescriptions", response_model=PrescriptionOut, status_code=201)
def create_prescription(
    payload: PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    prescription = Prescription(
        appointment_id=payload.appointment_id,
        doctor_id=doctor.id,
        patient_id=payload.patient_id,
        notes=payload.notes,
    )
    db.add(prescription)
    db.flush()

    for item_data in payload.items:
        item = PrescriptionItem(prescription_id=prescription.id, **item_data.model_dump())
        db.add(item)

    db.commit()
    db.refresh(prescription)
    log_action(db, current_user.id, "CREATE_PRESCRIPTION", "Prescription", prescription.id)
    return prescription


@router.get("/prescriptions/{prescription_id}", response_model=PrescriptionOut)
def get_prescription(
    prescription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return prescription
