from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List


class PatientDetail(BaseModel):
    id: str
    forename: str
    surname: str

    class Config:
        orm_mode = True


class PatientAnonymous(BaseModel):
    id: str
    birth_date: date

    class Config:
        orm_mode = True


class Patient(BaseModel):
    id: str
    forename: str
    surname: str
    birth_date: date

    class Config:
        orm_mode = True


class NewPatient(BaseModel):
    id: str
    forename: str = Field(..., min_length=1)
    surname: str = Field(..., min_length=1)
    birth_date: date


class MRIFile(BaseModel):
    id: int
    name: str
    created_at: datetime
    modified_at: datetime


class PatientFiles(BaseModel):
    mri_files: List[MRIFile]


class PatientFilesPatientDetail(PatientFiles):
    patient: Patient
