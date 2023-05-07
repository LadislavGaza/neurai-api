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
    birth_date: date | None

    class Config:
        orm_mode = True


class NewPatient(BaseModel):
    id: str
    forename: str = Field(..., min_length=1)
    surname: str = Field(..., min_length=1)
    birth_date: date


class ScreeningInfo(BaseModel):
    id: int
    name: str
    created_at: datetime
    modified_at: datetime


class PatientDetailScreenings(BaseModel):
    patient: Patient
    screenings: List[ScreeningInfo]


class HospitalMRI(BaseModel):  # series/snimkovanie/nifticko TBD
    series_uid: str
    filename: str | None   # ProtocolName from PACS
    description: str | None  # mri_files.description
    created_at: datetime | None
    already_downloaded: bool | None


class HospitalScreening(BaseModel):  # study/vysetrenie
    study_uid: str
    name: str | None  # screening name is study description from pacs
    created_at: datetime | None
    mri_files: List[HospitalMRI]


class HospitalStoragePatient(BaseModel):
    id: str
    name: str
    birth_date: date | None


class HospitalStorageSearch:
    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        birth_date: date | None = None
    ):
        self.PatientID = id
        self.PatientName = name
        self.PatientBirthDate = birth_date
