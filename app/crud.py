from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.hash import argon2

import app.model as m
import app.schema as s


async def create_user(user: s.UserCreate):
    hashed_password = argon2.hash(user.email)
    user_model = m.User(
        email=user.email,
        password=hashed_password
    )

    async_session = sessionmaker(
        m.engine, expire_on_commit=False, class_=AsyncSession
    )

    async with async_session() as session:
        async with session.begin():
            session.add(user_model)
            await session.commit()

