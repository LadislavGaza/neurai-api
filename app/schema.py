from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from typing import List


class UserCredential(BaseModel):
    email: EmailStr = Field(..., title='Email address')
    password: str = Field(..., title='Plain text password')

    class Config:
        orm_mode = True


class PatientSummary(BaseModel):
    id: str = Field(..., title='Patient unique identifier')
    forename: str
    surname: str
    created_at: datetime

    class Config:
        orm_mode = True


class AuthorizationURL(BaseModel):
    autorization_url: str


class AuthorizationCode(BaseModel):
    message: str


class UserProfile(BaseModel):
    email: str
    authorized_drive: bool


class MRIFile(BaseModel):
    id: str
    name: str
    created_at: datetime
    modified_at: datetime


class PatientFilesUpload(BaseModel):
    files: List[MRIFile]


class PatientFiles(BaseModel):
    mri_files: List[MRIFile]


class Login(BaseModel):
    token: str
