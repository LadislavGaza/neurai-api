from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
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
    authorized_drive: bool
    authorized_email: EmailStr


class ChangePassword(BaseModel):
    password: str = Field(..., title="Plain text password")


class PatientSummary(BaseModel):
    id: str = Field(..., title="Patient unique identifier")
    forename: str
    surname: str
    created_at: datetime

    class Config:
        orm_mode = True


class AuthorizationURL(BaseModel):
    autorization_url: str


class AuthorizationCode(BaseModel):
    message: str


class MRIFile(BaseModel):
    id: str
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
