"""Router principal de la versión 1 de la API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.attendance import router as attendance_router
from app.api.routes.branches import router as branches_router
from app.api.routes.class_enrollments import router as class_enrollments_router
from app.api.routes.class_schedules import router as class_schedules_router
from app.api.routes.classes import router as classes_router
from app.api.routes.health import router as health_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.students import router as students_router
from app.api.routes.users import router as users_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(organizations_router)
api_router.include_router(users_router)
api_router.include_router(branches_router)
api_router.include_router(classes_router)
api_router.include_router(class_schedules_router)
api_router.include_router(class_enrollments_router)
api_router.include_router(attendance_router)
api_router.include_router(students_router)
