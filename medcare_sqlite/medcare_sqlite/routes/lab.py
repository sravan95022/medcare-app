from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import LabTest, TestReport, Doctor, Patient, User, LabTestStatus
from schemas import LabTestCreate, LabTestOut, TestReportCreate, TestReportOut
from dependencies.auth import get_current_user, require_doctor, require_staff
from utils.audit import log_action
from utils.notifications import send_notification
from typing import List

router = APIRouter(prefix="/lab", tags=["Lab"])


@router.post("/tests", response_model=LabTestOut, status_code=201)
def create_lab_test(
    payload: LabTestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    lab_test = LabTest(doctor_id=doctor.id, **payload.model_dump())
    db.add(lab_test)
    db.commit()
    db.refresh(lab_test)
    log_action(db, current_user.id, "CREATE_LAB_TEST", "LabTest", lab_test.id)
    return lab_test


@router.get("/tests", response_model=List[LabTestOut])
def list_lab_tests(
    patient_id: int = None,
    status_filter: LabTestStatus = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    query = db.query(LabTest)
    if patient_id:
        query = query.filter(LabTest.patient_id == patient_id)
    if status_filter:
        query = query.filter(LabTest.status == status_filter)
    return query.offset(skip).limit(limit).all()


@router.post("/reports", response_model=TestReportOut, status_code=201)
def upload_test_report(
    payload: TestReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    lab_test = db.query(LabTest).filter(LabTest.id == payload.lab_test_id).first()
    if not lab_test:
        raise HTTPException(status_code=404, detail="Lab test not found")
    if db.query(TestReport).filter(TestReport.lab_test_id == payload.lab_test_id).first():
        raise HTTPException(status_code=400, detail="Report already uploaded for this test")

    lab_test.status = LabTestStatus.COMPLETED

    report = TestReport(**payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)

    patient = db.query(Patient).filter(Patient.id == lab_test.patient_id).first()
    if patient:
        send_notification(
            db, patient.user_id,
            "Lab Report Ready",
            f"Your {lab_test.test_name} report is now available.",
        )

    log_action(db, current_user.id, "UPLOAD_LAB_REPORT", "TestReport", report.id)
    return report


@router.get("/reports/{report_id}", response_model=TestReportOut)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(TestReport).filter(TestReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
