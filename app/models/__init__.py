"""Modelos ORM mínimos que el backend usa para operar sobre la DB existente."""

from app.models.academy_pending_session import AcademyPendingSession
from app.models.authorized_person import AuthorizedPerson
from app.models.belts import BeltLevel, BeltStripe, StudentBeltHistory
from app.models.curriculum import Discipline
from app.models.email_verification import EmailVerificationToken
from app.models.emergency_contact import EmergencyContact
from app.models.fight_record import FightRecordType, StudentFightRecord
from app.models.finance import Payment
from app.models.medical_record import MedicalRecord
from app.models.organization import Branch, Organization
from app.models.session_sync_ticket import SessionSyncTicket
from app.models.student import Student
from app.models.student_document import StudentDocument
from app.models.teaching import Attendance, ClassEnrollment, ClassSchedule, MartialClass
from app.models.trajectory import TrajectoryEvent
from app.models.user import AdminAssignment, User

__all__ = [
    "AcademyPendingSession",
    "AdminAssignment",
    "Attendance",
    "AuthorizedPerson",
    "BeltLevel",
    "BeltStripe",
    "Branch",
    "ClassEnrollment",
    "ClassSchedule",
    "Discipline",
    "EmailVerificationToken",
    "EmergencyContact",
    "FightRecordType",
    "MartialClass",
    "MedicalRecord",
    "Organization",
    "Payment",
    "SessionSyncTicket",
    "Student",
    "StudentBeltHistory",
    "StudentDocument",
    "StudentFightRecord",
    "TrajectoryEvent",
    "User",
]
