# MedCare – Hospital & Patient Management System

Enterprise-grade FastAPI backend for hospital management with full RBAC, appointment workflows, billing, and reporting.

---

## Tech Stack

- **FastAPI** – REST API framework
- **MySQL** – Relational database
- **SQLAlchemy ORM** – Database layer (ORM-only queries)
- **Pydantic v2** – Request/response validation
- **JWT (python-jose)** – Authentication
- **bcrypt (passlib)** – Password hashing

---

## Project Structure

```
medcare/
├── main.py               # App entry point, router registration
├── database.py           # DB engine and session setup
├── models.py             # 24 SQLAlchemy models
├── schemas.py            # Pydantic request/response schemas
├── requirements.txt
├── .env.example
├── routes/
│   ├── auth.py           # Register, Login
│   ├── patients.py       # Patient CRUD, medical history
│   ├── doctors.py        # Doctor profiles, prescriptions, medical records
│   ├── appointments.py   # Slot management, booking, cancel/reschedule
│   ├── billing.py        # Bill generation, payment processing
│   ├── lab.py            # Lab tests, report upload
│   ├── admin.py          # Departments, rooms, admissions, staff tasks
│   ├── reports.py        # Daily appointments, revenue, patient stats
│   └── notifications.py  # User notifications
├── dependencies/
│   └── auth.py           # JWT dependency, RBAC role guards
└── utils/
    ├── security.py       # JWT encode/decode, bcrypt hashing
    ├── audit.py          # Audit log utility
    └── notifications.py  # Notification creation utility
```

---

## Setup

### 1. Create MySQL Database
```sql
CREATE DATABASE medcare_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your MySQL credentials and a strong SECRET_KEY
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Access API Docs
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Models (24 total)

| # | Model | Category |
|---|-------|----------|
| 1 | User | Core |
| 2 | Patient | Core |
| 3 | Doctor | Core |
| 4 | Department | Core |
| 5 | Specialization | Core |
| 6 | Appointment | Appointments |
| 7 | AppointmentSlot | Appointments |
| 8 | MedicalRecord | Medical |
| 9 | Prescription | Medical |
| 10 | PrescriptionItem | Medical |
| 11 | Bill | Billing |
| 12 | Payment | Billing |
| 13 | LabTest | Lab |
| 14 | TestReport | Lab |
| 15 | Room | Operations |
| 16 | Admission | Operations |
| 17 | StaffTask | Operations |
| 18 | Notification | Communication |
| 19 | Announcement | Communication |
| 20 | AuditLog | Audit |
| 21 | AmbulanceRequest | Bonus |
| 22 | InsuranceClaim | Bonus |
| 23 | PharmacyInventory | Bonus |
| 24 | EmergencyCase | Bonus |

---

## Role-Based Access Control

| Endpoint Group | ADMIN | DOCTOR | RECEPTIONIST | PATIENT |
|---|---|---|---|---|
| Auth (register/login) | ✅ | ✅ | ✅ | ✅ |
| Patient management | ✅ | ✅ read | ✅ | self only |
| Doctor management | ✅ | self | read | read |
| Appointments | ✅ | ✅ | ✅ | own |
| Prescriptions | ✅ | ✅ create | read | own |
| Medical Records | ✅ | ✅ create | ❌ | own |
| Billing | ✅ | ❌ | ✅ | view own |
| Lab Tests | ✅ | ✅ order | ✅ upload | view own |
| Rooms / Admissions | ✅ | ❌ | ✅ | ❌ |
| Reports | ✅ | ❌ | ❌ | ❌ |
| Notifications | ✅ | ✅ | ✅ | ✅ |

---

## Core Business Flow

```
1. Patient registers (POST /auth/register)
2. Receptionist creates patient profile (POST /patients/)
3. Doctor creates appointment slots (POST /appointments/slots)
4. Patient books appointment (POST /appointments/)
   → Slot locked, notifications sent
5. Doctor completes appointment (PATCH /appointments/{id})
   → Bill auto-generated, patient notified
6. Doctor creates prescription (POST /doctors/prescriptions)
7. Receptionist processes payment (POST /billing/payments)
   → Bill marked PAID, payment notification sent
8. Optional: Doctor orders lab test (POST /lab/tests)
   → Staff uploads report (POST /lab/reports)
   → Patient notified
```

---

## Security

- All passwords hashed with **bcrypt**
- All endpoints protected by **JWT Bearer tokens**
- **RBAC** enforced via FastAPI `Depends()` guards
- All sensitive queries use **ORM only** (no raw SQL)
- Environment secrets via `.env` (never committed)
- Critical actions logged to **AuditLog** table

---

## Key Business Logic

- **Double-booking prevention**: `with_for_update()` lock on slot + duplicate check
- **Slot lifecycle**: AVAILABLE → BOOKED on appointment creation; freed on cancellation
- **Auto-billing**: Bill generated automatically when appointment status → COMPLETED
- **Payment validation**: Underpayment rejected; transaction ID auto-generated (UUID)
- **Audit logging**: Register, login, create patient, book appointment, process payment, etc.
- **Notifications**: Triggered on booking, completion, cancellation, payment, lab report ready
