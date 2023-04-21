import os
from datetime import datetime, date

from sqlalchemy import (
    String,
    ForeignKey,
    UniqueConstraint
)
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
    screenings = relationship(
        'Screening',
        foreign_keys='[Screening.created_by]',
        back_populates='creator'
    )


class Patient(Base):
    __tablename__ = 'patients'

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    birth_date: Mapped[date]

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
    screenings = relationship('Screening', back_populates='patient')
    annotations = relationship('Annotation', back_populates='patient')
    creator = relationship(User, foreign_keys=[created_by])
    editor = relationship(User, foreign_keys=[modified_by])


class Screening(Base):
    __tablename__ = 'screenings'
    __table_args__ = (UniqueConstraint('name', 'patient_id'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    patient_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.id")
    )
    study_uid: Mapped[str] = mapped_column(nullable=True)
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
        Patient, foreign_keys=[patient_id], back_populates='screenings'
    )
    creator = relationship(
        User, foreign_keys=[created_by], back_populates='screenings'
    )
    editor = relationship(User, foreign_keys=[modified_by])

    mri_files = relationship('MRIFile', back_populates='screening')


class MRIFile(Base):
    __tablename__ = 'mri_files'
    __table_args__ = (UniqueConstraint('filename', 'screening_id'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str]
    file_id: Mapped[str]
    description: Mapped[str] = mapped_column(nullable=True)
    series_uid: Mapped[str] = mapped_column(nullable=True)
    patient_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.id")
    )
    screening_id: Mapped[int] = mapped_column(
         ForeignKey("screenings.id", ondelete='CASCADE')
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

    annotations = relationship('Annotation', back_populates='mri_file')

    screening = relationship(
        Screening, foreign_keys=[screening_id], back_populates='mri_files'
    )


class Annotation(Base):
    __tablename__ = 'annotations'
    __table_args__ = (UniqueConstraint('name', 'mri_file_id'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    filename: Mapped[str] = mapped_column(nullable=True)
    file_id: Mapped[str] = mapped_column(nullable=True)
    mri_file_id: Mapped[int] = mapped_column(
        ForeignKey("mri_files.id", ondelete="CASCADE")
    )
    patient_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.id")
    )
    is_ai: Mapped[bool] = mapped_column(default=False)
    visible: Mapped[bool] = mapped_column(default=False)
    job_name: Mapped[str] = mapped_column(nullable=True)

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

    mri_file = relationship(
        MRIFile, foreign_keys=[mri_file_id], back_populates='annotations'
    )

    @property
    def ready(self):
        return self.job_name == None
