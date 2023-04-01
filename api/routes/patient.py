from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, status
from googleapiclient.discovery import build
from sqlalchemy.exc import IntegrityError

import api.deps.schema as s
from api.db import crud
from api.deps import utils
from api.deps.auth import validate_api_token, validate_drive_token
from api.deps.utils import APIException, get_localization_data

router = APIRouter(
    tags=["patient"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/patients",
    dependencies=[Depends(validate_api_token)],
    response_model=List[s.Patient],
)
async def patients_overview():
    return (await crud.get_patients()).all()


@router.post("/patients", response_model=s.Patient)
async def add_patient(
    patient: s.Patient,
    user_id: int = Depends(validate_api_token),
    translation=Depends(get_localization_data)
):
    if not patient.id:
        patient_exists = True
        while patient_exists:
            patient.id = utils.generate_unique_patient_id()
            patient_exists = False
            try:
                await crud.create_patient(
                    patient=patient,
                    user_id=user_id
                )

            except IntegrityError:
                patient_exists = True
    else:
        try:
            await crud.create_patient(
                patient=patient,
                user_id=user_id
            )

        except IntegrityError:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"message": translation["patient_id_exists"]}
            )

    new_patient = await crud.get_patient_by_id(patient.id)
    return new_patient


@router.get(
    "/patient/{patient_id}",
    dependencies=[Depends(validate_api_token)],
    response_model=s.Patient
)
async def patient(
    patient_id: str,
    user_id: int = Depends(validate_api_token),
    translation=Depends(get_localization_data)
):
    patient = await crud.get_patient_by_id(patient_id)
    if patient is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["patient_not_exist"]}
        )

    return patient


@router.get(
    "/patient/{patient_id}/screening",
    response_model=s.PatientDetailScreenings
)
async def patient_screenings(
    patient_id: str,
    creds=Depends(validate_drive_token),
    user_id: int = Depends(validate_api_token),
    translation=Depends(get_localization_data)
):
    patient = await crud.get_patient_by_id(patient_id)
    if patient is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["patient_not_exist"]},
        )

    screenings = await crud.get_screenings_by_patient_and_user(
        patient_id=patient_id,
        user_id=user_id
    )

    return {
        "patient": patient,
        "screenings": screenings
    }


@router.get(
    "/screening/{screening_id}/files",
    response_model=s.ScreeningFiles
)
async def screening_files(
    screening_id: int,
    creds=Depends(validate_drive_token),
    user_id: int = Depends(validate_api_token),
    translation=Depends(get_localization_data)
):
    screening = await crud.get_screening_by_id_and_user(screening_id, user_id)
    if screening is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["screening_not_found"]},
        )

    service = build("drive", "v3", credentials=creds)
    folder_id = utils.get_drive_folder_id(service, translation)
    # list the folder content
    files = utils.get_drive_folder_content(service, folder_id)

    user = await crud.get_user_by_id(user_id)
    mri_files = await utils.get_mri_files_and_annotations_per_screening(
        user=user, files=files, screening_id=screening_id
    )
    return {
        "mri_files": mri_files
    }


@router.post(
    "/patient/{patient_id}/screening",
    response_model=s.ScreeningInfo
)
async def create_screening(
    patient_id: str,
    screening: s.Screening,
    user_id: int = Depends(validate_api_token),
    translation=Depends(get_localization_data)
):
    # default name for screening is actual date
    if not screening.name:
        screening.name = datetime.now().strftime('%d-%m-%Y')

    try:
        new_screening = await crud.create_screening(
            name=screening.name,
            patient_id=patient_id,
            user_id=user_id
        )
    except IntegrityError:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": translation["screening_name_exists"]}
        )

    return new_screening


@router.post(
    "/screening/{screening_id}/files",
    response_model=s.PatientFiles
)
async def upload_mri(
    screening_id: int,
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token),
    files: List[UploadFile] = File(...),
    translation=Depends(get_localization_data)
):
    screening = await crud.get_screening_by_id_and_user(screening_id, user_id)
    if screening is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["screening_not_found"]},
        )
    new_files = await utils.mri_upload(
        files=files,
        creds=creds,
        patient_id=screening.patient_id,
        user_id=user_id,
        screening_id=screening_id,
        translation=translation
    )

    return {"mri_files": new_files}
