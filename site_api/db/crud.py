from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Iterable

import site_api.db.model as m
import site_api.deps.schema as s


async def get_patients() -> Iterable[m.Patient]:
    async with AsyncSession(m.engine) as session:
        query = select(m.Patient)
        result = await session.execute(query)

    return result.scalars()


async def get_patient_by_id(patient_id: str) -> m.Patient:
    async with AsyncSession(m.engine) as session:
        query = select(m.Patient).where(m.Patient.id == patient_id)
        result = await session.execute(query)

    return result.scalars().first()


async def create_patient(patient: s.NewPatient):
    patient_model = m.Patient(
        id=patient.id,
        forename=patient.forename,
        surname=patient.surname
    )

    async with AsyncSession(m.engine) as session:
        session.add(patient_model)
        await session.commit()