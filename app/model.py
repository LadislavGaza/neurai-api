import os
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    BigInteger
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine


engine = create_async_engine(os.environ.get('DB_URL'), future=True)
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    refresh_token = Column(String(512))
    mri_files = relationship('MRIFile', foreign_keys='[MRIFile.created_by]', back_populates='creator')


class Patient(Base):
    __tablename__ = 'patients'

    id = Column(String(20), primary_key=True, index=True)
    forename = Column(String, nullable=False)
    surname = Column(String, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.now)
    created_by = Column(Integer, ForeignKey("users.id", ondelete='CASCADE'), nullable=False)
    modified_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    modified_by = Column(Integer, ForeignKey("users.id", ondelete='CASCADE'))

    mri_files = relationship('MRIFile', back_populates='patient')
    creator = relationship(User, foreign_keys=[created_by])
    editor = relationship(User, foreign_keys=[modified_by])


class MRIFile(Base):
    __tablename__ = 'mri_files'

    id = Column(BigInteger, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_id = Column(String, nullable=False)
    patient_id = Column(String(20), ForeignKey("patients.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    modified_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    modified_by = Column(Integer, ForeignKey("users.id"))

    patient = relationship(Patient, foreign_keys=[patient_id], back_populates='mri_files')
    creator = relationship(User, foreign_keys=[created_by], back_populates='mri_files')
    editor = relationship(User, foreign_keys=[modified_by])
