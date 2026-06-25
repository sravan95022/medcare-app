import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from dotenv import load_dotenv
from jose import JWTError, jwt

load_dotenv()

# Import all models so SQLAlchemy registers them before create_all
import models  # noqa: F401

# Import routers
from routes.auth import router as auth_router
from routes.patients import router as patients_router
from routes.doctors import router as doctors_router
from routes.appointments import router as appointments_router
from routes.billing import router as billing_router
from routes.lab import router as lab_router
from routes.admin import router as admin_router
from routes.reports import router as reports_router
from routes.notifications import router as notifications_router
from routes.bonus import router as bonus_router

# ─── Create DB Tables ─────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MedCare – Hospital & Patient Management System",
    description=(
        "Enterprise-grade hospital management backend with RBAC, "
        "appointment workflows, billing, prescriptions, lab management, and reporting."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS (FIX: origin list from env; defaults to localhost for dev) ──────────
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register Routers ─────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(doctors_router)
app.include_router(appointments_router)
app.include_router(billing_router)
app.include_router(lab_router)
app.include_router(admin_router)
app.include_router(reports_router)
app.include_router(notifications_router)
app.include_router(bonus_router)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "MedCare API",
        "version": "1.0.0",
    }
