"""Documentos legales / consentimientos de un alumno."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentType(str):
    LIABILITY_WAIVER = "liability_waiver"
    PHOTO_CONSENT = "photo_consent"
    OTHER = "other"


class StudentDocument(Base):
    """Documentos escaneados / firmados asociados a la inscripción."""

    __tablename__ = "student_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    signed_at: Mapped[date | None] = mapped_column(Date(), nullable=True)
    signed_by_full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    witness_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date(), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    student = relationship("Student", back_populates="documents")
    organization = relationship("Organization")
