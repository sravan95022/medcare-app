from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import (
    Appointment, AppointmentSlot, Patient, Doctor, Bill, User,
    AppointmentStatus, SlotStatus, BillStatus, UserRole
)
from schemas import AppointmentCreate, AppointmentOut, AppointmentUpdate, AppointmentReschedule, SlotCreate, SlotOut
from dependencies.auth import get_current_user, require_doctor, require_receptionist, require_staff
from utils.audit import log_action
from utils.notifications import send_notification
from typing import List
from datetime import datetime

router = APIRouter(prefix="/appointments", tags=["Appointments"])


# ─── Slot Management ──────────────────────────────────────────────────────────

@router.post("/slots", response_model=SlotOut, status_code=201)
def create_slot(
    payload: SlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    conflict = db.query(AppointmentSlot).filter(
        AppointmentSlot.doctor_id == doctor.id,
        AppointmentSlot.slot_date == payload.slot_date,
        AppointmentSlot.start_time == payload.start_time,
    ).first()
    if conflict:
        raise HTTPException(status_code=400, detail="Slot already exists at this time")

    slot = AppointmentSlot(doctor_id=doctor.id, **payload.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


@router.get("/slots", response_model=List[SlotOut])
def list_available_slots(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(AppointmentSlot).filter(
        AppointmentSlot.doctor_id == doctor_id,
        AppointmentSlot.availability_status == SlotStatus.AVAILABLE,
    ).all()


# ─── Appointment Booking ──────────────────────────────────────────────────────

@router.post("/", response_model=AppointmentOut, status_code=201)
def book_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Resolve patient: patient books for themselves; receptionist/admin supplies patient_id
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient profile not found")
    elif current_user.role in (UserRole.RECEPTIONIST, UserRole.ADMIN):
        if not payload.patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required when booking on behalf of a patient")
        patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
    else:
        raise HTTPException(status_code=403, detail="Only patients, receptionists, or admins can book appointments")

    # Validate & lock slot
    slot = db.query(AppointmentSlot).filter(
        AppointmentSlot.id == payload.slot_id,
        AppointmentSlot.doctor_id == payload.doctor_id,
    ).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.availability_status != SlotStatus.AVAILABLE:
        raise HTTPException(status_code=409, detail="Slot is already booked or blocked")

    # Prevent double-booking: same patient + same doctor + same time
    duplicate = db.query(Appointment).filter(
        Appointment.patient_id == patient.id,
        Appointment.doctor_id == payload.doctor_id,
        Appointment.appointment_date == datetime.combine(slot.slot_date, slot.start_time),
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Patient already has an appointment with this doctor at this time")

    slot.availability_status = SlotStatus.BOOKED

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=payload.doctor_id,
        slot_id=payload.slot_id,
        appointment_date=datetime.combine(slot.slot_date, slot.start_time),
        symptoms=payload.symptoms,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    send_notification(
        db, patient.user_id,
        "Appointment Booked",
        f"Your appointment is confirmed for {appointment.appointment_date.strftime('%Y-%m-%d %H:%M')}.",
    )
    if doctor:
        send_notification(
            db, doctor.user_id,
            "New Appointment",
            f"A new appointment has been scheduled on {appointment.appointment_date.strftime('%Y-%m-%d %H:%M')}.",
        )

    log_action(db, current_user.id, "BOOK_APPOINTMENT", "Appointment", appointment.id)
    return appointment


@router.get("/", response_model=List[AppointmentOut])
def list_appointments(
    skip: int = 0,
    limit: int = 20,
    status_filter: AppointmentStatus = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    query = db.query(Appointment)
    if status_filter:
        query = query.filter(Appointment.status == status_filter)
    return query.offset(skip).limit(limit).all()


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appt


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    old_status = appt.status
    if payload.status:
        appt.status = payload.status
    if payload.notes:
        appt.notes = payload.notes

    # Auto-generate bill when appointment is COMPLETED
    if payload.status == AppointmentStatus.COMPLETED and old_status != AppointmentStatus.COMPLETED:
        doctor = db.query(Doctor).filter(Doctor.id == appt.doctor_id).first()
        bill = Bill(
            patient_id=appt.patient_id,
            appointment_id=appt.id,
            consultation_fee=doctor.consultation_fee if doctor else 0,
            total_amount=doctor.consultation_fee if doctor else 0,
        )
        db.add(bill)

        patient = db.query(Patient).filter(Patient.id == appt.patient_id).first()
        if patient:
            send_notification(
                db, patient.user_id,
                "Appointment Completed",
                "Your appointment is completed. A bill has been generated.",
            )

    # Free slot if cancelled
    if payload.status == AppointmentStatus.CANCELLED:
        slot = db.query(AppointmentSlot).filter(AppointmentSlot.id == appt.slot_id).first()
        if slot:
            slot.availability_status = SlotStatus.AVAILABLE
        patient = db.query(Patient).filter(Patient.id == appt.patient_id).first()
        if patient:
            send_notification(db, patient.user_id, "Appointment Cancelled", "Your appointment has been cancelled.")

    db.commit()
    db.refresh(appt)
    log_action(db, current_user.id, f"UPDATE_APPOINTMENT_{payload.status}", "Appointment", appt.id)
    return appt


@router.patch("/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule_appointment(
    appointment_id: int,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reschedule an appointment to a new slot (atomically frees old slot and locks new one).
    Accessible by the patient (own), receptionist, or admin.
    """
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # RBAC: patient can only reschedule their own appointment
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient or patient.id != appt.patient_id:
            raise HTTPException(status_code=403, detail="Access denied")

    if appt.status in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Cannot reschedule a completed or cancelled appointment")

    if appt.slot_id == payload.new_slot_id:
        raise HTTPException(status_code=400, detail="New slot is the same as the current slot")

    # Lock and validate the new slot
    new_slot = db.query(AppointmentSlot).filter(
        AppointmentSlot.id == payload.new_slot_id,
        AppointmentSlot.doctor_id == appt.doctor_id,   # must be same doctor
    ).first()
    if not new_slot:
        raise HTTPException(status_code=404, detail="New slot not found for the same doctor")
    if new_slot.availability_status != SlotStatus.AVAILABLE:
        raise HTTPException(status_code=409, detail="New slot is not available")

    # Free old slot
    old_slot = db.query(AppointmentSlot).filter(AppointmentSlot.id == appt.slot_id).first()
    if old_slot:
        old_slot.availability_status = SlotStatus.AVAILABLE

    # Lock new slot
    new_slot.availability_status = SlotStatus.BOOKED
    appt.slot_id = new_slot.id
    appt.appointment_date = datetime.combine(new_slot.slot_date, new_slot.start_time)

    db.commit()
    db.refresh(appt)

    patient = db.query(Patient).filter(Patient.id == appt.patient_id).first()
    if patient:
        send_notification(
            db, patient.user_id,
            "Appointment Rescheduled",
            f"Your appointment has been rescheduled to {appt.appointment_date.strftime('%Y-%m-%d %H:%M')}.",
        )
    doctor = db.query(Doctor).filter(Doctor.id == appt.doctor_id).first()
    if doctor:
        send_notification(
            db, doctor.user_id,
            "Appointment Rescheduled",
            f"An appointment has been rescheduled to {appt.appointment_date.strftime('%Y-%m-%d %H:%M')}.",
        )

    log_action(db, current_user.id, "RESCHEDULE_APPOINTMENT", "Appointment", appt.id,
               f"new_slot_id={payload.new_slot_id}")
    return appt


@router.delete("/{appointment_id}", status_code=204)
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt.status in [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Cannot cancel a completed or already cancelled appointment")

    appt.status = AppointmentStatus.CANCELLED
    slot = db.query(AppointmentSlot).filter(AppointmentSlot.id == appt.slot_id).first()
    if slot:
        slot.availability_status = SlotStatus.AVAILABLE

    patient = db.query(Patient).filter(Patient.id == appt.patient_id).first()
    if patient:
        send_notification(db, patient.user_id, "Appointment Cancelled", "Your appointment has been cancelled.")

    db.commit()
    log_action(db, current_user.id, "CANCEL_APPOINTMENT", "Appointment", appt.id)
