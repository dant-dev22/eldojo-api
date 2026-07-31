"""Modelos ORM mínimos que el backend usa para operar sobre la DB existente."""

from app.models.academy_pending_session import AcademyPendingSession
from app.models.curriculum import Discipline
from app.models.email_verification import EmailVerificationToken
from app.models.finance import Payment
from app.models.organization import Branch, Organization
from app.models.student import Student
from app.models.teaching import Attendance, ClassEnrollment, ClassSchedule, MartialClass
from app.models.user import AdminAssignment, User

__all__ = [
    "AcademyPendingSession",
    "AdminAssignment",
    "Attendance",
    "Branch",
    "ClassEnrollment",
    "ClassSchedule",
    "Discipline",
    "EmailVerificationToken",
    "MartialClass",
    "Organization",
    "Payment",
    "Student",
    "User",
]
