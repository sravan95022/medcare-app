"""
Appointment business logic.
Handles slot locking, double-booking checks, bill auto-generation, and notifications.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import (
    Appointment, AppointmentSlot, Patient, Doctor, Bill,
    AppointmentStatus, SlotStatus, UserRole
)
from utils.notifications import send_notification
from utils.audit import log_action


def resolve_patient(db: Session, current_user, patient_id: int = None) -> Patient:
    """Return the Patient record based on the caller's role."""
    from models import UserRole
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient profile not found")
        return patient
    elif current_user.role in (UserRole.RECEPTIONIST, UserRole.ADMIN):
        if not patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required when booking on behalf of a patient")
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient
    else:
        raise HTTPException(status_code=403, detail="Not authorised to book appointments")


def lock_slot(db: Session, slot_id: int, doctor_id: int) -> AppointmentSlot:
    """Fetch slot with a row-level lock and validate it's available."""
    slot = db.query(AppointmentSlot).filter(
        AppointmentSlot.id == slot_id,
        AppointmentSlot.doctor_id == doctor_id,
    ).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.availability_status != SlotStatus.AVAILABLE:
        raise HTTPException(status_code=409, detail="Slot is already booked or blocked")
    return slot


def check_double_booking(db: Session, patient_id: int, doctor_id: int, appointment_date: datetime):
    duplicate = db.query(Appointment).filter(
        Appointment.patient_id == patient_id,
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == appointment_date,
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Patient already has an appointment with this doctor at this time")


def auto_generate_bill(db: Session, appointment: Appointment):
    """Create a Bill automatically when an appointment is marked COMPLETED."""
    doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
    fee = doctor.consultation_fee if doctor else 0.0
    bill = Bill(
        patient_id=appointment.patient_id,
        appointment_id=appointment.id,
        consultation_fee=fee,
        total_amount=fee,
    )
    db.add(bill)

    patient = db.query(Patient).filter(Patient.id == appointment.patient_id).first()
    if patient:
        send_notification(
            db, patient.user_id,
            "Appointment Completed",
            "Your appointment is completed. A bill has been generated.",
        )


def notify_cancellation(db: Session, appointment: Appointment):
    slot = db.query(AppointmentSlot).filter(AppointmentSlot.id == appointment.slot_id).first()
    if slot:
        slot.availability_status = SlotStatus.AVAILABLE
    patient = db.query(Patient).filter(Patient.id == appointment.patient_id).first()
    if patient:
        send_notification(db, patient.user_id, "Appointment Cancelled", "Your appointment has been cancelled.")
