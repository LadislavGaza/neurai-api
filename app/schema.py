from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class UserCredential(BaseModel):
    email: EmailStr = Field(..., title='Email address')
    password: str = Field(..., title='Plain text password')

    class Config:
        orm_mode = True


class PatientSummary(BaseModel):
    id: str = Field(..., title='Patient unique identifier')
    firstname: str
    surname: str
    created_at: datetime

    class Config:
        orm_mode = True
