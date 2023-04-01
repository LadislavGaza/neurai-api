from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List


class PatientDetail(BaseModel):
    id: str
    forename: str
    surname: str

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


class Annotation(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class MRIFileAnnotations(MRIFile):
    annotation_files: List[Annotation]


class ScreeningInfo(BaseModel):
    id: int
    name: str
    created_at: datetime
    modified_at: datetime


class PatientDetailScreenings(BaseModel):
    patient: Patient
    screenings: List[ScreeningInfo]
