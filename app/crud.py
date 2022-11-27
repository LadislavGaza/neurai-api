from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import subqueryload
from typing import Iterable

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


async def get_patients() -> Iterable[m.Patient]:
    async with AsyncSession(m.engine) as session:
        query = select(m.Patient)
        result = await session.execute(query)

    return result.scalars()


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
        query = select(m.User).where(m.User.id == user_id).options(subqueryload(m.User.mri_files))
        result = await session.execute(query)

    return result.scalars().first()


async def create_mri_file(filename: str, patient_id: str, user_id: int):
    mri_file_model = m.MRIFile(
        filename=filename,
        patient_id=patient_id,
        created_by=user_id,
        modified_by=user_id
    )
    async with AsyncSession(m.engine) as session:
        session.add(mri_file_model)
        await session.commit()


async def create_patient(id: str, forename: str, surname: str, user_id: int):
    patient_model = m.Patient(
        id=id,
        forename=forename,
        surname=surname,
        created_by=user_id,
        modified_by=user_id
    )
    async with AsyncSession(m.engine) as session:
        session.add(patient_model)
        await session.commit()
