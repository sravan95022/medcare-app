from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import (
    AmbulanceRequest, InsuranceClaim, PharmacyInventory, EmergencyCase,
    Patient, Doctor, Bill, User
)
from schemas import (
    AmbulanceRequestCreate, AmbulanceRequestOut,
    InsuranceClaimCreate, InsuranceClaimOut,
    PharmacyInventoryCreate, PharmacyInventoryOut, PharmacyInventoryUpdate,
    EmergencyCaseCreate, EmergencyCaseOut,
)
from dependencies.auth import get_current_user, require_admin, require_staff, require_receptionist
from utils.audit import log_action
from typing import List

router = APIRouter(tags=["Bonus"])


# ─── Ambulance Requests ───────────────────────────────────────────────────────

@router.post("/ambulance/requests", response_model=AmbulanceRequestOut, status_code=201)
def request_ambulance(
    payload: AmbulanceRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    req = AmbulanceRequest(**payload.model_dump())
    db.add(req)
    db.commit()
    db.refresh(req)
    log_action(db, current_user.id, "REQUEST_AMBULANCE", "AmbulanceRequest", req.id)
    return req


@router.get("/ambulance/requests", response_model=List[AmbulanceRequestOut])
def list_ambulance_requests(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    return db.query(AmbulanceRequest).order_by(AmbulanceRequest.requested_at.desc()).offset(skip).limit(limit).all()


@router.patch("/ambulance/requests/{request_id}/status", response_model=AmbulanceRequestOut)
def update_ambulance_status(
    request_id: int,
    new_status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    req = db.query(AmbulanceRequest).filter(AmbulanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Ambulance request not found")
    req.status = new_status
    db.commit()
    db.refresh(req)
    log_action(db, current_user.id, "UPDATE_AMBULANCE_STATUS", "AmbulanceRequest", req.id)
    return req


# ─── Insurance Claims ─────────────────────────────────────────────────────────

@router.post("/insurance/claims", response_model=InsuranceClaimOut, status_code=201)
def submit_insurance_claim(
    payload: InsuranceClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not db.query(Patient).filter(Patient.id == payload.patient_id).first():
        raise HTTPException(status_code=404, detail="Patient not found")
    if not db.query(Bill).filter(Bill.id == payload.bill_id).first():
        raise HTTPException(status_code=404, detail="Bill not found")

    claim = InsuranceClaim(**payload.model_dump())
    db.add(claim)
    db.commit()
    db.refresh(claim)
    log_action(db, current_user.id, "SUBMIT_INSURANCE_CLAIM", "InsuranceClaim", claim.id)
    return claim


@router.get("/insurance/claims", response_model=List[InsuranceClaimOut])
def list_insurance_claims(
    patient_id: int = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    query = db.query(InsuranceClaim)
    if patient_id:
        query = query.filter(InsuranceClaim.patient_id == patient_id)
    return query.offset(skip).limit(limit).all()


@router.patch("/insurance/claims/{claim_id}/status", response_model=InsuranceClaimOut)
def update_claim_status(
    claim_id: int,
    new_status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    claim = db.query(InsuranceClaim).filter(InsuranceClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Insurance claim not found")
    claim.status = new_status
    db.commit()
    db.refresh(claim)
    log_action(db, current_user.id, "UPDATE_CLAIM_STATUS", "InsuranceClaim", claim.id)
    return claim


# ─── Pharmacy Inventory ───────────────────────────────────────────────────────

@router.post("/pharmacy/inventory", response_model=PharmacyInventoryOut, status_code=201)
def add_medicine(
    payload: PharmacyInventoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = db.query(PharmacyInventory).filter(
        PharmacyInventory.medicine_name == payload.medicine_name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Medicine already exists in inventory. Use PATCH to update stock.")

    medicine = PharmacyInventory(**payload.model_dump())
    db.add(medicine)
    db.commit()
    db.refresh(medicine)
    log_action(db, current_user.id, "ADD_MEDICINE", "PharmacyInventory", medicine.id)
    return medicine


@router.get("/pharmacy/inventory", response_model=List[PharmacyInventoryOut])
def list_inventory(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    return db.query(PharmacyInventory).offset(skip).limit(limit).all()


@router.patch("/pharmacy/inventory/{medicine_id}", response_model=PharmacyInventoryOut)
def update_medicine(
    medicine_id: int,
    payload: PharmacyInventoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    medicine = db.query(PharmacyInventory).filter(PharmacyInventory.id == medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(medicine, field, value)

    db.commit()
    db.refresh(medicine)
    log_action(db, current_user.id, "UPDATE_MEDICINE", "PharmacyInventory", medicine.id)
    return medicine


@router.delete("/pharmacy/inventory/{medicine_id}", status_code=204)
def delete_medicine(
    medicine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    medicine = db.query(PharmacyInventory).filter(PharmacyInventory.id == medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")
    db.delete(medicine)
    db.commit()
    log_action(db, current_user.id, "DELETE_MEDICINE", "PharmacyInventory", medicine_id)


# ─── Emergency Cases ──────────────────────────────────────────────────────────

@router.post("/emergency/cases", response_model=EmergencyCaseOut, status_code=201)
def report_emergency(
    payload: EmergencyCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not db.query(Patient).filter(Patient.id == payload.patient_id).first():
        raise HTTPException(status_code=404, detail="Patient not found")
    if payload.handled_by and not db.query(Doctor).filter(Doctor.id == payload.handled_by).first():
        raise HTTPException(status_code=404, detail="Doctor not found")

    case = EmergencyCase(**payload.model_dump())
    db.add(case)
    db.commit()
    db.refresh(case)
    log_action(db, current_user.id, "REPORT_EMERGENCY", "EmergencyCase", case.id,
               f"severity={payload.severity}")
    return case


@router.get("/emergency/cases", response_model=List[EmergencyCaseOut])
def list_emergency_cases(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    return db.query(EmergencyCase).order_by(EmergencyCase.reported_at.desc()).offset(skip).limit(limit).all()


@router.patch("/emergency/cases/{case_id}/assign", response_model=EmergencyCaseOut)
def assign_doctor_to_emergency(
    case_id: int,
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    case = db.query(EmergencyCase).filter(EmergencyCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Emergency case not found")
    if not db.query(Doctor).filter(Doctor.id == doctor_id).first():
        raise HTTPException(status_code=404, detail="Doctor not found")

    case.handled_by = doctor_id
    db.commit()
    db.refresh(case)
    log_action(db, current_user.id, "ASSIGN_EMERGENCY_DOCTOR", "EmergencyCase", case.id)
    return case
