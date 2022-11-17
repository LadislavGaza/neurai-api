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
from sqlalchemy.sql.functions import now
from sqlalchemy.ext.asyncio import create_async_engine


engine = create_async_engine(os.environ.get('DB_URL'), future=True)
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    refresh_token = Column(String(512))


class Patient(Base):
    __tablename__ = 'patients'

    id = Column(String(20), primary_key=True, index=True)
    forename = Column(String, nullable=False)
    surname = Column(String, nullable=False)

    created_at = Column(DateTime, nullable=False, default=now)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    modified_at = Column(DateTime, default=now, onupdate=now)
    modified_by = Column(Integer, ForeignKey("users.id"))

    creator = relationship(User, foreign_keys=[created_by])
    editor = relationship(User, foreign_keys=[modified_by])


class MRIFile(Base):
    __tablename__ = 'MRI_files'

    id = Column(BigInteger, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    patient_id = Column(String(20), ForeignKey("patients.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=now)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    modified_at = Column(DateTime, default=now, onupdate=now)
    modified_by = Column(Integer, ForeignKey("users.id"))

    patient = relationship(Patient, back_populates='patients')
    creator = relationship(User, foreign_keys=[created_by])
    editor = relationship(User, foreign_keys=[modified_by])
