from datetime import datetime, date
from typing import List

from pydantic import BaseModel, Field, EmailStr


class UserCredential(BaseModel):
    email: EmailStr
    username: str
    password: str

    class Config:
        orm_mode = True


class UserLoginCredentials(BaseModel):
    email: EmailStr
    password: str = Field(..., title="Plain text password")


class ResetPassword(BaseModel):
    email: EmailStr


class UserProfile(BaseModel):
    email: str
    username: str
    authorized: bool
    authorized_email: EmailStr | None


class ChangePassword(BaseModel):
    password: str = Field(..., title="Plain text password")


class Patient(BaseModel):
    id: str
    birth_date: date

    class Config:
        orm_mode = True


class AuthorizationURL(BaseModel):
    autorization_url: str


class AuthorizationCode(BaseModel):
    message: str


class MRIFile(BaseModel):
    id: int
    name: str
    series_uid: str
    created_at: datetime
    modified_at: datetime


class Annotation(BaseModel):
    id: int
    name: str
    is_ai: bool
    ready: bool

    class Config:
        orm_mode = True


class MRIFileAnnotations(MRIFile):
    annotation_files: List[Annotation]


class AnnotationFiles(BaseModel):
    id: str


class RenameMRI(BaseModel):
    name: str


class AnnotationEdit(BaseModel):
    name: str | None
    visible: bool | None


class PatientFiles(BaseModel):
    mri_files: List[MRIFile]


class ScreeningFiles(BaseModel):
    mri_files: List[MRIFileAnnotations]


class Login(BaseModel):
    token: str
    email: str
    username: str
    authorized: bool
    authorized_email: str


class GoogleFile(BaseModel):
    id: str
    name: str
    patient_name: str
    modified_at: datetime


class GoogleFiles(BaseModel):
    files: List[GoogleFile]


class Screening(BaseModel):
    name: str | None
    uid: str | None


class ScreeningInfo(BaseModel):
    id: int
    name: str
    study_uid: str | None
    created_at: datetime
    modified_at: datetime
    annotation_in_progress: bool


class PatientDetailScreenings(BaseModel):
    patient: Patient
    screenings: List[ScreeningInfo]


class ExistingSeries(BaseModel):
    id: int
    file_id: str
    series_uid: str | None


class ExistingStudies(BaseModel):
    study_uid: str | None
    mri_files: List[ExistingSeries]
