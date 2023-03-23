from fastapi import File, UploadFile, Form
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, date
from typing import List


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
    created_at: datetime
    modified_at: datetime


class Annotation(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class MRIFileAnnotations(MRIFile):
    annotation_files: List[Annotation]


class AnnotationFiles(BaseModel):
    id: str
    

class RenameAnnotation(BaseModel):
    name: str


class PatientFiles(BaseModel):
    mri_files: List[MRIFile]


class PatientFilesPatientDetail(BaseModel):
    patient: Patient
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


class CreateScreening(BaseModel):
    id: int


class Screening(BaseModel):
    name: str | None


class ScreeningInfo(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class PatientDetailScreenings(BaseModel):
    patient: Patient
    screenings: List[ScreeningInfo]
