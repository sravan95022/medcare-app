"""
Billing business logic.
Handles bill creation, payment processing, and related validations.
"""
import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import Bill, Payment, Patient, Doctor, Appointment, BillStatus, PaymentStatus
from utils.notifications import send_notification
from utils.audit import log_action


def create_bill(db: Session, appointment: Appointment, extra_charges: dict = None) -> Bill:
    """
    Generate a bill for a completed appointment.
    extra_charges: dict with optional keys lab_charges, medicine_charges, room_charges.
    """
    if db.query(Bill).filter(Bill.appointment_id == appointment.id).first():
        raise HTTPException(status_code=400, detail="Bill already exists for this appointment")

    doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
    consultation_fee = doctor.consultation_fee if doctor else 0.0
    charges = extra_charges or {}
    lab = charges.get("lab_charges", 0.0)
    med = charges.get("medicine_charges", 0.0)
    room = charges.get("room_charges", 0.0)
    total = consultation_fee + lab + med + room

    bill = Bill(
        patient_id=appointment.patient_id,
        appointment_id=appointment.id,
        consultation_fee=consultation_fee,
        lab_charges=lab,
        medicine_charges=med,
        room_charges=room,
        total_amount=total,
    )
    db.add(bill)
    db.flush()

    patient = db.query(Patient).filter(Patient.id == appointment.patient_id).first()
    if patient:
        send_notification(
            db, patient.user_id,
            "Bill Generated",
            f"Your bill of \u20b9{total:.2f} is ready. Please proceed with payment.",
        )
    return bill


def process_payment(db: Session, bill: Bill, payment_method, amount_paid: float) -> Payment:
    """Validate and record a payment; mark bill as PAID."""
    if bill.status == BillStatus.PAID:
        raise HTTPException(status_code=400, detail="Bill already paid")
    if amount_paid < bill.total_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient payment. Bill total is \u20b9{bill.total_amount:.2f}",
        )

    payment = Payment(
        bill_id=bill.id,
        payment_method=payment_method,
        payment_status=PaymentStatus.SUCCESS,
        transaction_id=str(uuid.uuid4()),
        amount_paid=amount_paid,
    )
    db.add(payment)
    bill.status = BillStatus.PAID
    db.flush()

    patient = db.query(Patient).filter(Patient.id == bill.patient_id).first()
    if patient:
        send_notification(
            db, patient.user_id,
            "Payment Successful",
            f"Payment of \u20b9{amount_paid:.2f} received. Transaction ID: {payment.transaction_id}",
        )
    return payment
