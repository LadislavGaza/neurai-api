from pydantic import BaseModel, Field, EmailStr


class UserCreate(BaseModel):
    email: EmailStr = Field(..., title='Email address')
    password: str = Field(..., title='Plain text password')

    class Config:
        orm_mode = True
