from fastapi import APIRouter, Depends, File, UploadFile, status
from googleapiclient.discovery import build

from typing import List

from api.db import crud
from api.deps import utils
import api.deps.schema as s
from api.deps.auth import validate_api_token, validate_drive_token
from api.deps.utils import APIException

from sqlalchemy.exc import IntegrityError


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
    user_id: int = Depends(validate_api_token)
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
                content={"message": "Patient with this ID already exists"},
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
    user_id: int = Depends(validate_api_token)
):
    patient = await crud.get_patient_by_id(patient_id)
    if patient is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Patient does not exist"},
        )

    return patient


@router.get(
    "/patient/{patient_id}/files",
    response_model=s.PatientFilesPatientDetail
)
async def patient_files(
    patient_id: str,
    creds=Depends(validate_drive_token),
    user_id: int = Depends(validate_api_token),
):
    patient = await crud.get_patient_by_id(patient_id)
    if patient is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Patient does not exist"},
        )

    service = build("drive", "v3", credentials=creds)
    folder_id = utils.get_drive_folder_id(service)
    # list the folder content
    files = utils.get_drive_folder_content(service, folder_id)

    user = await crud.get_user_by_id(user_id)
    mri_files = await utils.get_mri_files_and_annotations_per_user(
        user=user, files=files, patient_id=patient_id
    )
    return {
        "patient": patient,
        "mri_files": mri_files
    }


@router.post(
    "/patient/{patient_id}/files",
    response_model=s.PatientFiles
)
async def upload_mri(
    patient_id: str,
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token),
    files: List[UploadFile] = File(...),
):
    new_files = await utils.file_uploader(
        files=files,
        creds=creds,
        patient_id=patient_id,
        user_id=user_id,
        scan_type='mri',
        mri_id=None,
        name=""
    )

    return {"mri_files": new_files}

