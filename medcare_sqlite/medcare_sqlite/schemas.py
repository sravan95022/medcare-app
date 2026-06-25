from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional, List
from datetime import datetime, date, time
from models import (
    UserRole, AppointmentStatus, SlotStatus, BillStatus,
    PaymentMethod, PaymentStatus, LabTestStatus, RoomType,
    RoomStatus, TaskStatus, Gender
)


# ─── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    # Self-registration is restricted to PATIENT only.
    # ADMIN/DOCTOR/RECEPTIONIST accounts must be created by an admin via /admin/users.
    role: UserRole = UserRole.PATIENT

    @model_validator(mode="after")
    def restrict_self_registration(self):
        if self.role != UserRole.PATIENT:
            raise ValueError(
                "Self-registration is only allowed for PATIENT role. "
                "Contact an administrator to create staff accounts."
            )
        return self

class AdminUserCreate(BaseModel):
    """Used by admins to create DOCTOR / RECEPTIONIST / ADMIN accounts."""
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: UserRole

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[UserRole] = None


# ─── User ─────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Patient ──────────────────────────────────────────────────────────────────

class PatientCreate(BaseModel):
    user_id: int                          # FIX: receptionist must supply the patient's user_id
    full_name: str
    gender: Gender
    blood_group: Optional[str] = None
    phone: str
    dob: Optional[date] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None

class PatientOut(BaseModel):
    id: int
    user_id: int
    full_name: str
    gender: Gender
    blood_group: Optional[str]
    phone: str
    dob: Optional[date]
    address: Optional[str]
    emergency_contact: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Department & Specialization ─────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None

class DepartmentOut(DepartmentCreate):
    id: int

    class Config:
        from_attributes = True

class SpecializationCreate(BaseModel):
    name: str
    department_id: int

class SpecializationOut(SpecializationCreate):
    id: int

    class Config:
        from_attributes = True


# ─── Doctor ───────────────────────────────────────────────────────────────────

class DoctorCreate(BaseModel):
    user_id: int                          # FIX: admin must supply the target user's id
    specialization_id: int
    experience: int = 0
    consultation_fee: float

class DoctorOut(BaseModel):
    id: int
    user_id: int
    specialization_id: int
    experience: int
    consultation_fee: float
    is_available: bool

    class Config:
        from_attributes = True


# ─── Appointment Slot ─────────────────────────────────────────────────────────

class SlotCreate(BaseModel):
    slot_date: date
    start_time: time
    end_time: time

class SlotOut(SlotCreate):
    id: int
    doctor_id: int
    availability_status: SlotStatus

    class Config:
        from_attributes = True


# ─── Appointment ──────────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    doctor_id: int
    slot_id: int
    patient_id: Optional[int] = None     # Required when receptionist books on behalf of patient
    symptoms: Optional[str] = None

class AppointmentUpdate(BaseModel):
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = None

class AppointmentReschedule(BaseModel):
    new_slot_id: int

class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    slot_id: int
    appointment_date: datetime
    status: AppointmentStatus
    symptoms: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Medical Record ───────────────────────────────────────────────────────────

class MedicalRecordCreate(BaseModel):
    patient_id: int
    diagnosis: str
    treatment: Optional[str] = None
    notes: Optional[str] = None

class MedicalRecordOut(MedicalRecordCreate):
    id: int
    created_by: int
    record_date: datetime

    class Config:
        from_attributes = True


# ─── Prescription ─────────────────────────────────────────────────────────────

class PrescriptionItemCreate(BaseModel):
    medicine_name: str
    dosage: str
    duration: str
    instructions: Optional[str] = None

class PrescriptionCreate(BaseModel):
    appointment_id: int
    patient_id: int
    notes: Optional[str] = None
    items: List[PrescriptionItemCreate]

class PrescriptionItemOut(PrescriptionItemCreate):
    id: int
    prescription_id: int

    class Config:
        from_attributes = True

class PrescriptionOut(BaseModel):
    id: int
    appointment_id: int
    doctor_id: int
    patient_id: int
    notes: Optional[str]
    created_at: datetime
    items: List[PrescriptionItemOut] = []

    class Config:
        from_attributes = True


# ─── Bill ─────────────────────────────────────────────────────────────────────

class BillCreate(BaseModel):
    patient_id: int
    appointment_id: int
    lab_charges: float = 0.0
    medicine_charges: float = 0.0
    room_charges: float = 0.0

class BillOut(BaseModel):
    id: int
    patient_id: int
    appointment_id: int
    consultation_fee: float
    lab_charges: float
    medicine_charges: float
    room_charges: float
    total_amount: float
    status: BillStatus
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Payment ──────────────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    bill_id: int
    payment_method: PaymentMethod
    amount_paid: float

class PaymentOut(PaymentCreate):
    id: int
    payment_status: PaymentStatus
    transaction_id: Optional[str]
    paid_at: datetime

    class Config:
        from_attributes = True


# ─── Lab Test ─────────────────────────────────────────────────────────────────

class LabTestCreate(BaseModel):
    patient_id: int
    test_name: str

class LabTestOut(LabTestCreate):
    id: int
    doctor_id: int
    status: LabTestStatus
    ordered_at: datetime

    class Config:
        from_attributes = True

class TestReportCreate(BaseModel):
    lab_test_id: int
    report_url: str
    findings: Optional[str] = None

class TestReportOut(TestReportCreate):
    id: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


# ─── Room & Admission ─────────────────────────────────────────────────────────

class RoomCreate(BaseModel):
    room_number: str
    room_type: RoomType
    floor: Optional[int] = None
    charges_per_day: float = 0.0

class RoomOut(RoomCreate):
    id: int
    status: RoomStatus

    class Config:
        from_attributes = True

class AdmissionCreate(BaseModel):
    patient_id: int
    room_id: int
    reason: Optional[str] = None

class AdmissionOut(AdmissionCreate):
    id: int
    admitted_at: datetime
    discharged_at: Optional[datetime]

    class Config:
        from_attributes = True


# ─── Staff Task ───────────────────────────────────────────────────────────────

class StaffTaskCreate(BaseModel):
    assigned_to: int
    task_title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None

class StaffTaskOut(StaffTaskCreate):
    id: int
    status: TaskStatus
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Notification ─────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Announcement ─────────────────────────────────────────────────────────────

class AnnouncementCreate(BaseModel):
    title: str
    message: str

class AnnouncementOut(AnnouncementCreate):
    id: int
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Reports ──────────────────────────────────────────────────────────────────

class DailyAppointmentReport(BaseModel):
    date: date
    total: int
    completed: int
    cancelled: int
    pending: int

class RevenueReport(BaseModel):
    period: str
    total_revenue: float
    total_bills: int
    paid_bills: int

class PatientStats(BaseModel):
    total_patients: int
    new_this_month: int
    active_admissions: int


# ─── Bonus Model Schemas ──────────────────────────────────────────────────────

class AmbulanceRequestCreate(BaseModel):
    patient_id: int
    pickup_address: str

class AmbulanceRequestOut(AmbulanceRequestCreate):
    id: int
    status: str
    requested_at: datetime

    class Config:
        from_attributes = True

class InsuranceClaimCreate(BaseModel):
    patient_id: int
    bill_id: int
    provider_name: str
    claim_amount: float

class InsuranceClaimOut(InsuranceClaimCreate):
    id: int
    status: str
    submitted_at: datetime

    class Config:
        from_attributes = True

class PharmacyInventoryCreate(BaseModel):
    medicine_name: str
    quantity: int
    unit_price: float
    expiry_date: Optional[date] = None

class PharmacyInventoryOut(PharmacyInventoryCreate):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True

class PharmacyInventoryUpdate(BaseModel):
    quantity: Optional[int] = None
    unit_price: Optional[float] = None
    expiry_date: Optional[date] = None

class EmergencyCaseCreate(BaseModel):
    patient_id: int
    description: str
    severity: str
    handled_by: Optional[int] = None

class EmergencyCaseOut(EmergencyCaseCreate):
    id: int
    reported_at: datetime

    class Config:
        from_attributes = True


# ─── Pagination ───────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    total: int
    page: int
    per_page: int
    data: list
