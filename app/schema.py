from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(
        ...,
        max_length=200,
        title='Username'
    )
    password: str = Field(
        ...,
        title='Plain text password'
    )

    class Config:
        orm_mode = True
