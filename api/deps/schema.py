from fastapi import File, UploadFile, Form
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, date
from typing import List


class UserCredential(BaseModel):
    email: EmailStr = Field(..., title="Email address")
    username: str
    password: str = Field(..., title="Plain text password")

    class Config:
        orm_mode = True


class UserLoginCredentials(BaseModel):
    email: EmailStr = Field(..., title="Email address")
    password: str = Field(..., title="Plain text password")


class ResetPassword(BaseModel):
    email: EmailStr = Field(..., title="Email address")


class UserProfile(BaseModel):
    email: str
    username: str
    authorized: bool
    authorized_email: EmailStr | None


class ChangePassword(BaseModel):
    password: str = Field(..., title="Plain text password")


class PatientSummary(BaseModel):
    id: str = Field(..., title="Patient unique identifier")
    forename: str
    surname: str
    birth_date: date
    created_at: datetime

    class Config:
        orm_mode = True


class NewPatient(BaseModel):
    id: str = Field(..., title="Patient unique identifier")
    forename: str = Field(..., min_length=1)
    surname: str = Field(..., min_length=1)
    birth_date: date = Field(...)


class AuthorizationURL(BaseModel):
    autorization_url: str


class AuthorizationCode(BaseModel):
    message: str


class MRIFile(BaseModel):
    id: int
    name: str
    created_at: datetime
    modified_at: datetime


class PatientFiles(BaseModel):
    mri_files: List[MRIFile]


class PatientFilesPatientDetail(PatientFiles):
    patient: PatientSummary


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


class AnnotationFiles(BaseModel):
    id: str


class Annotation(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class RenameAnnotation(BaseModel):
    name: str
