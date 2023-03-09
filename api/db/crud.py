from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import subqueryload

from typing import Iterable
from datetime import date

import api.db.model as m
import api.deps.schema as s
from api.deps import const


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
        patient_id: str,
        user_id: int,
        mri_id: int
):
    async with AsyncSession(m.engine) as session:
        if name:
            annotation_name = name
        else:
            query = (
                select(m.Annotation)
                .where(m.Annotation.mri_file_id == mri_id)
                .where(m.Annotation.name.regexp_match('^maska[0-9]+$'))
                .order_by(m.Annotation.created_at.desc()))
            result = await session.execute(query)
            annotation = result.scalars().first()

            if annotation and annotation.name[len(const.ANNOT_MASK):]:
                highest_number = int(annotation.name[len(const.ANNOT_MASK):])
                annotation_name = f'{const.ANNOT_MASK}{str(highest_number + 1)}'
            else:
                annotation_name = f'{const.ANNOT_MASK}1'

        annotation_file_model = m.Annotation(
            name=annotation_name,
            patient_id=patient_id,
            mri_file_id=mri_id,
            created_by=user_id,
            modified_by=user_id
        )

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


async def get_annotations_by_mri_and_user(mri_id: int, user_id: int) -> Iterable[m.Annotation]:
    async with AsyncSession(m.engine) as session:
        query = (
            select(m.Annotation)
            .where(m.Annotation.mri_file_id == mri_id, m.Annotation.created_by == user_id)
            .order_by(m.Annotation.created_at.desc())
        )
        result = await session.execute(query)

    return result.scalars().all()


async def get_annotation_by_id(id: int) -> m.Annotation:
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


async def update_annotation_file(
    id: int,
    filename: str,
    file_id: str
):
    async with AsyncSession(m.engine) as session:
        stmt = (
            update(m.Annotation)
            .where(m.Annotation.id == id)
            .values({
                "filename": filename,
                "file_id": file_id
            })
        )
        await session.execute(stmt)
        await session.commit()


async def update_annotation_name(
        id: int,
        name: str,
):
    async with AsyncSession(m.engine) as session:
        stmt = (
            update(m.Annotation)
            .where(m.Annotation.id == id)
            .values({
                "name": name
            })
        )
        await session.execute(stmt)
        await session.commit()
