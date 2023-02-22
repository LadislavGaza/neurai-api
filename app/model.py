import os
from sqlalchemy import (
    String,
    ForeignKey
)
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship
)


DB_URL = os.environ.get("DB_URL")
engine = create_async_engine(DB_URL)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    username: Mapped[str]
    password: Mapped[str]
    refresh_token: Mapped[str] = mapped_column(String(512), nullable=True)
    authorized_email: Mapped[str] = mapped_column(nullable=True)

    mri_files = relationship(
        'MRIFile',
        foreign_keys='[MRIFile.created_by]',
        back_populates='creator'
    )
    annotations = relationship(
        'Annotation',
        foreign_keys='[Annotation.created_by]',
        back_populates='creator'
    )


class Patient(Base):
    __tablename__ = 'patients'

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    forename: Mapped[str]
    surname: Mapped[str]

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete='CASCADE')
    )
    modified_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=True
    )
    modified_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete='CASCADE'), nullable=True
    )

    mri_files = relationship('MRIFile', back_populates='patient')
    annotations = relationship('Annotation', back_populates='patient')
    creator = relationship(User, foreign_keys=[created_by])
    editor = relationship(User, foreign_keys=[modified_by])


class MRIFile(Base):
    __tablename__ = 'mri_files'

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str]
    file_id: Mapped[str]
    patient_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.id")
    )

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete='CASCADE')
    )
    modified_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=True
    )
    modified_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete='CASCADE'), nullable=True
    )

    patient = relationship(
        Patient, foreign_keys=[patient_id], back_populates='mri_files'
    )
    creator = relationship(
        User, foreign_keys=[created_by], back_populates='mri_files'
    )
    editor = relationship(User, foreign_keys=[modified_by])


class Annotation(Base):
    __tablename__ = 'annotations'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    gdrive_filename: Mapped[str]
    file_id: Mapped[str]
    patient_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.id")
    )

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete='CASCADE')
    )
    modified_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=True
    )
    modified_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete='CASCADE'), nullable=True
    )

    patient = relationship(
        Patient, foreign_keys=[patient_id], back_populates='annotations'
    )
    creator = relationship(
        User, foreign_keys=[created_by], back_populates='annotations'
    )
    editor = relationship(User, foreign_keys=[modified_by])
