"""Modelos ORM mínimos que el backend usa para operar sobre la DB existente."""

from app.models.academy_pending_session import AcademyPendingSession
from app.models.belts import BeltLevel, BeltStripe, StudentBeltHistory
from app.models.curriculum import Discipline
from app.models.email_verification import EmailVerificationToken
from app.models.fight_record import FightRecordType, StudentFightRecord
from app.models.finance import Payment
from app.models.organization import Branch, Organization
from app.models.session_sync_ticket import SessionSyncTicket
from app.models.student import Student
from app.models.teaching import Attendance, ClassEnrollment, ClassSchedule, MartialClass
from app.models.trajectory import TrajectoryEvent
from app.models.user import AdminAssignment, User

__all__ = [
    "AcademyPendingSession",
    "AdminAssignment",
    "Attendance",
    "BeltLevel",
    "BeltStripe",
    "Branch",
    "ClassEnrollment",
    "ClassSchedule",
    "Discipline",
    "EmailVerificationToken",
    "FightRecordType",
    "MartialClass",
    "Organization",
    "Payment",
    "SessionSyncTicket",
    "Student",
    "StudentBeltHistory",
    "StudentFightRecord",
    "TrajectoryEvent",
    "User",
]
