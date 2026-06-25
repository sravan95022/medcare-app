from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey, Enum, Date, Time
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"
    RECEPTIONIST = "RECEPTIONIST"
    PATIENT = "PATIENT"

class AppointmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class SlotStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"

class BillStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"

class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    CARD = "CARD"
    UPI = "UPI"
    INSURANCE = "INSURANCE"

class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class LabTestStatus(str, enum.Enum):
    ORDERED = "ORDERED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class RoomType(str, enum.Enum):
    GENERAL = "GENERAL"
    PRIVATE = "PRIVATE"
    ICU = "ICU"
    EMERGENCY = "EMERGENCY"

class RoomStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    MAINTENANCE = "MAINTENANCE"

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"

class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


# ─── Core Models ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    patient = relationship("Patient", back_populates="user", uselist=False)
    doctor = relationship("Doctor", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    staff_tasks = relationship("StaffTask", back_populates="assignee")


class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)
    description = Column(Text)

    specializations = relationship("Specialization", back_populates="department")


class Specialization(Base):
    __tablename__ = "specializations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)

    department = relationship("Department", back_populates="specializations")
    doctors = relationship("Doctor", back_populates="specialization")


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    full_name = Column(String(200), nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    blood_group = Column(String(10))
    phone = Column(String(20), nullable=False)
    dob = Column(Date)
    address = Column(Text)
    emergency_contact = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="patient")
    appointments = relationship("Appointment", back_populates="patient")
    medical_records = relationship("MedicalRecord", back_populates="patient")
    prescriptions = relationship("Prescription", back_populates="patient")
    bills = relationship("Bill", back_populates="patient")
    lab_tests = relationship("LabTest", back_populates="patient")
    admissions = relationship("Admission", back_populates="patient")


class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    specialization_id = Column(Integer, ForeignKey("specializations.id"), nullable=False)
    experience = Column(Integer, default=0)
    consultation_fee = Column(Float, nullable=False)
    is_available = Column(Boolean, default=True)

    user = relationship("User", back_populates="doctor")
    specialization = relationship("Specialization", back_populates="doctors")
    appointments = relationship("Appointment", back_populates="doctor")
    slots = relationship("AppointmentSlot", back_populates="doctor")
    medical_records = relationship("MedicalRecord", back_populates="created_by_doctor")
    prescriptions = relationship("Prescription", back_populates="doctor")
    lab_tests = relationship("LabTest", back_populates="doctor")


# ─── Appointment Models ───────────────────────────────────────────────────────

class AppointmentSlot(Base):
    __tablename__ = "appointment_slots"
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    slot_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    availability_status = Column(Enum(SlotStatus), default=SlotStatus.AVAILABLE)

    doctor = relationship("Doctor", back_populates="slots")
    appointment = relationship("Appointment", back_populates="slot", uselist=False)


class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("appointment_slots.id"), unique=True, nullable=False)
    appointment_date = Column(DateTime, nullable=False)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING)
    symptoms = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    slot = relationship("AppointmentSlot", back_populates="appointment")
    prescription = relationship("Prescription", back_populates="appointment", uselist=False)
    bill = relationship("Bill", back_populates="appointment", uselist=False)


# ─── Medical Records ──────────────────────────────────────────────────────────

class MedicalRecord(Base):
    __tablename__ = "medical_records"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    diagnosis = Column(Text, nullable=False)
    treatment = Column(Text)
    notes = Column(Text)
    record_date = Column(DateTime, server_default=func.now())

    patient = relationship("Patient", back_populates="medical_records")
    created_by_doctor = relationship("Doctor", back_populates="medical_records")


class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    appointment = relationship("Appointment", back_populates="prescription")
    doctor = relationship("Doctor", back_populates="prescriptions")
    patient = relationship("Patient", back_populates="prescriptions")
    items = relationship("PrescriptionItem", back_populates="prescription")


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False)
    medicine_name = Column(String(200), nullable=False)
    dosage = Column(String(100), nullable=False)
    duration = Column(String(100), nullable=False)
    instructions = Column(Text)

    prescription = relationship("Prescription", back_populates="items")


# ─── Billing & Payments ───────────────────────────────────────────────────────

class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    consultation_fee = Column(Float, default=0.0)
    lab_charges = Column(Float, default=0.0)
    medicine_charges = Column(Float, default=0.0)
    room_charges = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    status = Column(Enum(BillStatus), default=BillStatus.PENDING)
    created_at = Column(DateTime, server_default=func.now())

    patient = relationship("Patient", back_populates="bills")
    appointment = relationship("Appointment", back_populates="bill")
    payment = relationship("Payment", back_populates="bill", uselist=False)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    transaction_id = Column(String(200), unique=True)
    amount_paid = Column(Float, nullable=False)
    paid_at = Column(DateTime, server_default=func.now())

    bill = relationship("Bill", back_populates="payment")


# ─── Lab & Test Management ────────────────────────────────────────────────────

class LabTest(Base):
    __tablename__ = "lab_tests"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    test_name = Column(String(200), nullable=False)
    status = Column(Enum(LabTestStatus), default=LabTestStatus.ORDERED)
    ordered_at = Column(DateTime, server_default=func.now())

    patient = relationship("Patient", back_populates="lab_tests")
    doctor = relationship("Doctor", back_populates="lab_tests")
    report = relationship("TestReport", back_populates="lab_test", uselist=False)


class TestReport(Base):
    __tablename__ = "test_reports"
    id = Column(Integer, primary_key=True, index=True)
    lab_test_id = Column(Integer, ForeignKey("lab_tests.id"), nullable=False)
    report_url = Column(String(500), nullable=False)
    findings = Column(Text)
    uploaded_at = Column(DateTime, server_default=func.now())

    lab_test = relationship("LabTest", back_populates="report")


# ─── Hospital Operations ──────────────────────────────────────────────────────

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String(20), unique=True, nullable=False)
    room_type = Column(Enum(RoomType), nullable=False)
    floor = Column(Integer)
    status = Column(Enum(RoomStatus), default=RoomStatus.AVAILABLE)
    charges_per_day = Column(Float, default=0.0)

    admissions = relationship("Admission", back_populates="room")


class Admission(Base):
    __tablename__ = "admissions"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    admitted_at = Column(DateTime, server_default=func.now())
    discharged_at = Column(DateTime, nullable=True)
    reason = Column(Text)

    patient = relationship("Patient", back_populates="admissions")
    room = relationship("Room", back_populates="admissions")


class StaffTask(Base):
    __tablename__ = "staff_tasks"
    id = Column(Integer, primary_key=True, index=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    assignee = relationship("User", back_populates="staff_tasks")


# ─── Communication & Alerts ───────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="notifications")


class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    author = relationship("User")


# ─── Audit & Reporting ────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255), nullable=False)
    entity = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="audit_logs")


# ─── Bonus Models ─────────────────────────────────────────────────────────────

class AmbulanceRequest(Base):
    __tablename__ = "ambulance_requests"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    pickup_address = Column(Text, nullable=False)
    status = Column(String(50), default="REQUESTED")
    requested_at = Column(DateTime, server_default=func.now())

    patient = relationship("Patient")


class InsuranceClaim(Base):
    __tablename__ = "insurance_claims"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    provider_name = Column(String(200), nullable=False)
    claim_amount = Column(Float, nullable=False)
    status = Column(String(50), default="SUBMITTED")
    submitted_at = Column(DateTime, server_default=func.now())

    patient = relationship("Patient")
    bill = relationship("Bill")


class PharmacyInventory(Base):
    __tablename__ = "pharmacy_inventory"
    id = Column(Integer, primary_key=True, index=True)
    medicine_name = Column(String(200), nullable=False)
    quantity = Column(Integer, default=0)
    unit_price = Column(Float, nullable=False)
    expiry_date = Column(Date)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EmergencyCase(Base):
    __tablename__ = "emergency_cases"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(50), nullable=False)
    handled_by = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    reported_at = Column(DateTime, server_default=func.now())

    patient = relationship("Patient")
    doctor = relationship("Doctor")
