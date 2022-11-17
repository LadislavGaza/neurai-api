from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.model as m
import app.schema as s


async def create_user(user: s.UserCredential):
    user_model = m.User(
        email=user.email,
        password=user.password
    )
    async with AsyncSession(m.engine) as session:
        session.add(user_model)
        await session.commit()


async def get_user(user: s.UserCredential) -> m.User:
    async with AsyncSession(m.engine) as session:
        query = select(m.User).where(m.User.email == user.email)
        result = await session.execute(query)

    return result.scalars().first()


async def update_user_refresh_token(user_id: int, refresh_token: str):
    async with AsyncSession(m.engine) as session:
        stmt = (
            update(m.User)
            .where(m.User.id == user_id)
            .values(refresh_token=refresh_token)
        )
        await session.execute(stmt)
        await session.commit()


async def get_user_by_id(user_id: int) -> m.User:
    async with AsyncSession(m.engine) as session:
        query = select(m.User).where(m.User.id == user_id)
        result = await session.execute(query)

    return result.scalars().first()
