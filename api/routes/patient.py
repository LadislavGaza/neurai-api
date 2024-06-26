from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, status
from googleapiclient.discovery import build
from sqlalchemy.exc import IntegrityError

import api.deps.schema as s
from api.db import crud
from api.deps import utils, upload, const
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
            content={"message": translation["patient_not_exists"]}
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
            content={"message": translation["patient_not_exists"]},
        )

    screenings = await crud.get_screenings_by_patient_and_user(
        patient_id=patient_id,
        user_id=user_id
    )
    screenings_out = []
    for (screening, in_progress) in screenings:
        item = vars(screening)
        item["annotation_in_progress"] = in_progress
        screenings_out.append(item)

    return {
        "patient": patient,
        "screenings": screenings_out
    }


@router.get(
    "/patient/{patient_id}/study",
    # response_model=List[s.ExistingStudies]
)
async def patient_studies(
    patient_id: str,
    creds=Depends(validate_drive_token),
    user_id: int = Depends(validate_api_token),
    translation=Depends(get_localization_data)
):
    screenings = await crud.get_screenings_series_by_patient_and_user(
        patient_id=patient_id,
        user_id=user_id
    )

    service = build("drive", "v3", credentials=creds)
    folder_id = upload.get_drive_folder_id(service, translation)
    files = upload.get_drive_folder_content(service, folder_id)

    studies_series = utils.get_screenings_and_mri_files_per_patient(
        screenings=screenings,
        files=files
    )

    return studies_series


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
    folder_id = upload.get_drive_folder_id(service, translation)
    # list the folder content
    files = upload.get_drive_folder_content(service, folder_id)

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
    try:
        new_screening = await crud.create_screening(
            name=screening.name,
            uid=screening.uid,
            patient_id=patient_id,
            user_id=user_id
        )
        new_screening = vars(new_screening)
        new_screening["annotation_in_progress"] = False
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
    mri = await pacs_mri_upload(
        screening_id=screening_id,
        user_id=user_id,
        creds=creds,
        files=files,
        translation=translation
    )

    return {"mri_files": [mri]}


@router.post(
    "/screening/{screening_id}/files/{series_uid}",
    response_model=s.PatientFiles
)
async def upload_mri(
    screening_id: int,
    series_uid: str,
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token),
    files: List[UploadFile] = File(...),
    translation=Depends(get_localization_data)
):
    mri = await pacs_mri_upload(
        screening_id=screening_id,
        series_uid=series_uid,
        user_id=user_id,
        creds=creds,
        files=files,
        translation=translation
    )

    return {"mri_files": [mri]}


async def pacs_mri_upload(
    screening_id: int,
    user_id,
    creds,
    files,
    translation,
    series_uid: str = None,
):
    screening = await crud.get_screening_by_id_and_user(screening_id, user_id)
    if screening is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["screening_not_found"]},
        )

    mri = await upload.mri_upload(
        files,
        creds,
        screening.patient_id, 
        screening_id, 
        user_id, 
        translation,
        series_uid
    )

    if const.AZUREML.ENABLED is True:
        await upload.mri_auto_annotate(
            mri, screening.patient_id, user_id, translation
        )

    return mri