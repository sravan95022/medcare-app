from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Appointment, Bill, Patient, Payment, AppointmentStatus, BillStatus, User
from schemas import DailyAppointmentReport, RevenueReport, PatientStats
from dependencies.auth import require_admin
from datetime import date, datetime, timedelta
from typing import List

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/appointments/daily", response_model=DailyAppointmentReport)
def daily_appointment_report(
    report_date: date = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not report_date:
        report_date = date.today()

    day_start = datetime.combine(report_date, datetime.min.time())
    day_end = datetime.combine(report_date, datetime.max.time())

    base = db.query(Appointment).filter(
        Appointment.appointment_date >= day_start,
        Appointment.appointment_date <= day_end,
    )

    return DailyAppointmentReport(
        date=report_date,
        total=base.count(),
        completed=base.filter(Appointment.status == AppointmentStatus.COMPLETED).count(),
        cancelled=base.filter(Appointment.status == AppointmentStatus.CANCELLED).count(),
        pending=base.filter(Appointment.status == AppointmentStatus.PENDING).count(),
    )


@router.get("/revenue", response_model=RevenueReport)
def revenue_report(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    bills = db.query(Bill).filter(Bill.created_at >= start_dt, Bill.created_at <= end_dt)
    paid = bills.filter(Bill.status == BillStatus.PAID)

    total_revenue = db.query(func.sum(Payment.amount_paid)).join(Bill).filter(
        Bill.created_at >= start_dt, Bill.created_at <= end_dt,
        Bill.status == BillStatus.PAID,
    ).scalar() or 0.0

    return RevenueReport(
        period=f"{start_date} to {end_date}",
        total_revenue=total_revenue,
        total_bills=bills.count(),
        paid_bills=paid.count(),
    )


@router.get("/patients/stats", response_model=PatientStats)
def patient_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    from models import Admission

    total = db.query(Patient).count()

    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
    new_this_month = db.query(Patient).filter(Patient.created_at >= month_start).count()
    active_admissions = db.query(Admission).filter(Admission.discharged_at == None).count()

    return PatientStats(
        total_patients=total,
        new_this_month=new_this_month,
        active_admissions=active_admissions,
    )
