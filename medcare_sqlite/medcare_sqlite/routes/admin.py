from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import (
    Department, Specialization, Room, Admission, StaffTask,
    Announcement, User, UserRole, RoomStatus
)
from schemas import (
    DepartmentCreate, DepartmentOut, SpecializationCreate, SpecializationOut,
    RoomCreate, RoomOut, AdmissionCreate, AdmissionOut,
    StaffTaskCreate, StaffTaskOut, AnnouncementCreate, AnnouncementOut, UserOut
)
from dependencies.auth import get_current_user, require_admin, require_receptionist, require_staff
from utils.audit import log_action
from typing import List
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["Admin"])


# ─── Departments ──────────────────────────────────────────────────────────────

@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    dept = Department(**payload.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.get("/departments", response_model=List[DepartmentOut])
def list_departments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Department).all()


# ─── Specializations ──────────────────────────────────────────────────────────

@router.post("/specializations", response_model=SpecializationOut, status_code=201)
def create_specialization(
    payload: SpecializationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    spec = Specialization(**payload.model_dump())
    db.add(spec)
    db.commit()
    db.refresh(spec)
    return spec


@router.get("/specializations", response_model=List[SpecializationOut])
def list_specializations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Specialization).all()


# ─── Rooms ────────────────────────────────────────────────────────────────────

@router.post("/rooms", response_model=RoomOut, status_code=201)
def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if db.query(Room).filter(Room.room_number == payload.room_number).first():
        raise HTTPException(status_code=400, detail="Room number already exists")
    room = Room(**payload.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/rooms", response_model=List[RoomOut])
def list_rooms(
    available_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    query = db.query(Room)
    if available_only:
        query = query.filter(Room.status == RoomStatus.AVAILABLE)
    return query.all()


# ─── Admissions ───────────────────────────────────────────────────────────────

@router.post("/admissions", response_model=AdmissionOut, status_code=201)
def admit_patient(
    payload: AdmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_receptionist),
):
    room = db.query(Room).filter(Room.id == payload.room_id).first()
    if not room or room.status != RoomStatus.AVAILABLE:
        raise HTTPException(status_code=400, detail="Room is not available")

    room.status = RoomStatus.OCCUPIED
    admission = Admission(**payload.model_dump())
    db.add(admission)
    db.commit()
    db.refresh(admission)
    log_action(db, current_user.id, "ADMIT_PATIENT", "Admission", admission.id)
    return admission


@router.patch("/admissions/{admission_id}/discharge", response_model=AdmissionOut)
def discharge_patient(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_receptionist),
):
    admission = db.query(Admission).filter(Admission.id == admission_id).first()
    if not admission:
        raise HTTPException(status_code=404, detail="Admission not found")
    if admission.discharged_at:
        raise HTTPException(status_code=400, detail="Patient already discharged")

    admission.discharged_at = datetime.utcnow()
    room = db.query(Room).filter(Room.id == admission.room_id).first()
    if room:
        room.status = RoomStatus.AVAILABLE

    db.commit()
    db.refresh(admission)
    log_action(db, current_user.id, "DISCHARGE_PATIENT", "Admission", admission.id)
    return admission


# ─── Staff Tasks ──────────────────────────────────────────────────────────────

@router.post("/tasks", response_model=StaffTaskOut, status_code=201)
def create_task(
    payload: StaffTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    task = StaffTask(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks", response_model=List[StaffTaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    return db.query(StaffTask).all()


# ─── Announcements ────────────────────────────────────────────────────────────

@router.post("/announcements", response_model=AnnouncementOut, status_code=201)
def create_announcement(
    payload: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    ann = Announcement(created_by=current_user.id, **payload.model_dump())
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


@router.get("/announcements", response_model=List[AnnouncementOut])
def list_announcements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Announcement).order_by(Announcement.created_at.desc()).all()


# ─── User Management ──────────────────────────────────────────────────────────

@router.get("/users", response_model=List[UserOut])
def list_users(
    role: UserRole = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.all()


@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    db.refresh(user)
    log_action(db, current_user.id, "DEACTIVATE_USER", "User", user_id)
    return user
