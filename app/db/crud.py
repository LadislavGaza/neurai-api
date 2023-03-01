from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import subqueryload

from typing import Iterable
from datetime import date

import app.db.model as m
import app.schema as s


async def create_user(user: s.UserCredential):
    user_model = m.User(
        email=user.email, username=user.username, password=user.password
    )
    async with AsyncSession(m.engine) as session:
        session.add(user_model)
        await session.commit()


async def get_user(user: s.UserCredential) -> m.User:
    async with AsyncSession(m.engine) as session:
        query = select(m.User).where(m.User.email == user.email)
        result = await session.execute(query)

    return result.scalars().first()


async def get_user_by_mail(email: str) -> m.User:
    async with AsyncSession(m.engine) as session:
        query = select(m.User).where(m.User.email == email)
        result = await session.execute(query)

    return result.scalars().first()


async def update_user_password(user_id: str, password: str):
    async with AsyncSession(m.engine) as session:
        stmt = (
            update(m.User)
            .where(m.User.id == user_id)
            .values(password=password)
        )
        await session.execute(stmt)
        await session.commit()


async def get_patients() -> Iterable[m.Patient]:
    async with AsyncSession(m.engine) as session:
        query = select(m.Patient)
        result = await session.execute(query)

    return result.scalars()


async def update_user_refresh_token(user_id: int, refresh_token: str | None):
    async with AsyncSession(m.engine) as session:
        stmt = (
            update(m.User)
            .where(m.User.id == user_id)
            .values(refresh_token=refresh_token)
        )
        await session.execute(stmt)
        await session.commit()


async def update_user_associated_drive(user_id: int, email: str | None):
    async with AsyncSession(m.engine) as session:
        stmt = (
            update(m.User)
            .where(m.User.id == user_id)
            .values(authorized_email=email)
        )
        await session.execute(stmt)
        await session.commit()


async def get_user_by_id(user_id: int) -> m.User:
    async with AsyncSession(m.engine) as session:
        query = (
            select(m.User)
            .where(m.User.id == user_id)
            .options(subqueryload(m.User.mri_files).subqueryload(m.MRIFile.patient))
        )
        result = await session.execute(query)

    return result.scalars().first()


async def get_patient_by_id(patient_id: str) -> m.Patient:
    async with AsyncSession(m.engine) as session:
        query = select(m.Patient).where(m.Patient.id == patient_id)
        result = await session.execute(query)

    return result.scalars().first()


async def create_mri_file(filename: str, file_id: str, patient_id: str, user_id: int):
    mri_file_model = m.MRIFile(
        filename=filename,
        file_id=file_id,
        patient_id=patient_id,
        created_by=user_id,
        modified_by=user_id,
    )
    async with AsyncSession(m.engine) as session:
        session.add(mri_file_model)
        await session.commit()


async def create_patient(
    patient: s.NewPatient,
    user_id: int
):
    patient_model = m.Patient(
        id=patient.id,
        forename=patient.forename,
        surname=patient.surname,
        birth_date=patient.birth_date,
        created_by=user_id,
        modified_by=user_id,
    )
    async with AsyncSession(m.engine) as session:
        session.add(patient_model)
        await session.commit()
