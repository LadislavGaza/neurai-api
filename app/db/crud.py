from sqlalchemy import select, update, delete
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
        await session.refresh(mri_file_model)
    return mri_file_model.id

async def create_annotation_file(
        name: str,
        filename: str,
        file_id: str,
        patient_id: str,
        user_id: int,
        mri_id: int
):
    annotation_file_model = m.Annotation(
        name=name,
        filename=filename,
        file_id=file_id,
        patient_id=patient_id,
        mri_file_id=mri_id,
        created_by=user_id,
        modified_by=user_id
    )
    async with AsyncSession(m.engine) as session:
        session.add(annotation_file_model)
        await session.commit()
        await session.refresh(annotation_file_model)
    return annotation_file_model.id


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


async def get_mri_file_by_id(id: int) -> m.MRIFile:
    async with AsyncSession(m.engine) as session:
        query = (
            select(m.MRIFile)
            .where(m.MRIFile.id == id)
            .options(subqueryload(m.MRIFile.patient))
        )
        result = await session.execute(query)

    return result.scalars().first()


async def get_annotations(mri_id: int) -> Iterable[m.Annotation]:
    async with AsyncSession(m.engine) as session:
        query = (
            select(m.Annotation)
            .where(m.Annotation.mri_file_id == mri_id)
            .order_by(m.Annotation.created_at.desc())
        )
        result = await session.execute(query)

    return result.scalars()


async def get_annotation_by_id(id: int):
    async with AsyncSession(m.engine) as session:
        query = (
            select(m.Annotation).where(m.Annotation.id == id)
        )
        result = await session.execute(query)

    return result.scalars().first()


async def delete_annotation(id: int):
    async with AsyncSession(m.engine) as session:
        query = (
            delete(m.Annotation)
            .where(m.Annotation.id == id)
        )
        await session.execute(query)
        await session.commit()
