from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Bill, Payment, Patient, Doctor, Appointment, User, BillStatus, PaymentStatus
from schemas import BillCreate, BillOut, PaymentCreate, PaymentOut
from dependencies.auth import get_current_user, require_receptionist, require_staff
from utils.audit import log_action
from utils.notifications import send_notification
from typing import List
import uuid

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.post("/bills", response_model=BillOut, status_code=201)
def generate_bill(
    payload: BillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_receptionist),
):
    # Verify appointment exists and is not already billed
    appt = db.query(Appointment).filter(Appointment.id == payload.appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if db.query(Bill).filter(Bill.appointment_id == payload.appointment_id).first():
        raise HTTPException(status_code=400, detail="Bill already exists for this appointment")

    doctor = db.query(Doctor).filter(Doctor.id == appt.doctor_id).first()
    consultation_fee = doctor.consultation_fee if doctor else 0.0
    total = consultation_fee + payload.lab_charges + payload.medicine_charges + payload.room_charges

    bill = Bill(
        patient_id=payload.patient_id,
        appointment_id=payload.appointment_id,
        consultation_fee=consultation_fee,
        lab_charges=payload.lab_charges,
        medicine_charges=payload.medicine_charges,
        room_charges=payload.room_charges,
        total_amount=total,
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)

    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if patient:
        send_notification(
            db, patient.user_id,
            "Bill Generated",
            f"Your bill of ₹{total:.2f} is ready. Please proceed with payment.",
        )

    log_action(db, current_user.id, "GENERATE_BILL", "Bill", bill.id)
    return bill


@router.get("/bills", response_model=List[BillOut])
def list_bills(
    skip: int = 0,
    limit: int = 20,
    status_filter: BillStatus = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    query = db.query(Bill)
    if status_filter:
        query = query.filter(Bill.status == status_filter)
    return query.offset(skip).limit(limit).all()


@router.get("/bills/{bill_id}", response_model=BillOut)
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


@router.post("/payments", response_model=PaymentOut, status_code=201)
def process_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bill = db.query(Bill).filter(Bill.id == payload.bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill.status == BillStatus.PAID:
        raise HTTPException(status_code=400, detail="Bill already paid")
    if payload.amount_paid < bill.total_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient payment. Bill total is ₹{bill.total_amount:.2f}",
        )

    payment = Payment(
        bill_id=bill.id,
        payment_method=payload.payment_method,
        payment_status=PaymentStatus.SUCCESS,
        transaction_id=str(uuid.uuid4()),
        amount_paid=payload.amount_paid,
    )
    db.add(payment)
    bill.status = BillStatus.PAID
    db.commit()
    db.refresh(payment)

    patient = db.query(Patient).filter(Patient.id == bill.patient_id).first()
    if patient:
        send_notification(
            db, patient.user_id,
            "Payment Successful",
            f"Payment of ₹{payload.amount_paid:.2f} received. Transaction ID: {payment.transaction_id}",
        )

    log_action(db, current_user.id, "PROCESS_PAYMENT", "Payment", payment.id)
    return payment


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
