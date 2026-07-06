"""Modelos ORM de organizaciones y sucursales."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    """Tenant principal que agrupa sucursales y administradores."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(3), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("UTC_TIMESTAMP()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("UTC_TIMESTAMP()"),
    )

    branches = relationship("Branch", back_populates="organization")
    admin_assignments = relationship("AdminAssignment", back_populates="organization")
    disciplines = relationship("Discipline", back_populates="organization")
    students = relationship("Student", back_populates="organization")
    classes = relationship("MartialClass", back_populates="organization")
    payments = relationship("Payment", back_populates="organization")


class Branch(Base):
    """Sucursal operativa con zona horaria y datos de ubicación."""

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    qr_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("UTC_TIMESTAMP()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("UTC_TIMESTAMP()"),
    )

    organization = relationship("Organization", back_populates="branches")
    admin_assignments = relationship("AdminAssignment", back_populates="branch")
    students = relationship("Student", back_populates="branch")
    classes = relationship("MartialClass", back_populates="branch")
    attendance_records = relationship("Attendance", back_populates="branch")
    payments = relationship("Payment", back_populates="branch")
