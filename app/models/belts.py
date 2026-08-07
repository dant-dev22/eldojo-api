"""Modelos ORM para catálogo de cinturones, stripes e historial de promociones."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BeltLevel(Base):
    """Catálogo de niveles/cinturones configurables por organización."""

    __tablename__ = "belt_levels"
    __table_args__ = (
        UniqueConstraint("organization_id", "order_index", name="uq_belt_levels_org_order"),
        UniqueConstraint("organization_id", "name", name="uq_belt_levels_org_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)
    text_color_hex: Mapped[str] = mapped_column(String(7), nullable=False, server_default=text("'#FFFFFF'"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
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

    organization = relationship("Organization", back_populates="belt_levels")
    stripes = relationship("BeltStripe", back_populates="belt_level", cascade="all, delete-orphan")
    student_current_belts = relationship("Student", back_populates="current_belt_level")
    belt_histories = relationship("StudentBeltHistory", back_populates="belt_level")


class BeltStripe(Base):
    """Catálogo de stripes/puntos intermedios asociados a un nivel de cinta."""

    __tablename__ = "belt_stripes"
    __table_args__ = (
        UniqueConstraint("belt_level_id", "order_index", name="uq_belt_stripes_level_order"),
        UniqueConstraint("belt_level_id", "name", name="uq_belt_stripes_level_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    belt_level_id: Mapped[int] = mapped_column(
        ForeignKey("belt_levels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
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

    belt_level = relationship("BeltLevel", back_populates="stripes")
    student_current_stripes = relationship("Student", back_populates="current_stripe")
    stripe_histories = relationship("StudentBeltHistory", back_populates="stripe")


class StudentBeltHistory(Base):
    """Historial auditado de promociones o cambios de cinta de un alumno."""

    __tablename__ = "student_belt_histories"
    __table_args__ = (
        CheckConstraint(
            "awarded_at IS NOT NULL",
            name="chk_student_belt_histories_awarded_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    belt_level_id: Mapped[int] = mapped_column(
        ForeignKey("belt_levels.id", ondelete="RESTRICT"),
        nullable=False,
    )
    stripe_id: Mapped[int | None] = mapped_column(
        ForeignKey("belt_stripes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    awarded_at: Mapped[date] = mapped_column(Date(), nullable=False)
    awarded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    student = relationship("Student", back_populates="belt_histories")
    belt_level = relationship("BeltLevel", back_populates="belt_histories")
    stripe = relationship("BeltStripe", back_populates="stripe_histories")
    awarded_by_user = relationship("User", foreign_keys=[awarded_by_user_id])
