from fastapi import APIRouter, Depends, File, UploadFile, status
from googleapiclient.discovery import build

from typing import List
from datetime import date

from app import utils
import app.schema as s
from app.db import crud
from app.dependencies import validate_api_token, validate_drive_token
from app.utils import APIException

from sqlalchemy.exc import IntegrityError

router = APIRouter(
    tags=["patient"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/patients",
    dependencies=[Depends(validate_api_token)],
    response_model=List[s.PatientSummary],
)
async def patients_overview():
    return (await crud.get_patients()).all()


@router.post("/patient/{patientID}/files", response_model=s.PatientFiles)
async def upload_mri(
    patientID: str,
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token),
    files: List[UploadFile] = File(...),
):
    new_files = await utils.file_uploader(
        files=files,
        creds=creds,
        patient_id=patientID,
        user_id=user_id,
        scan_type='mri',
        mri_id=None,
        name=""
    )

    return {"mri_files": new_files}


@router.get(
    "/patient/{patientID}/files",
    response_model=s.PatientFilesPatientDetail
)
async def patient(
    patientID: str,
    creds=Depends(validate_drive_token),
    user_id: int = Depends(validate_api_token),
):
    service = build("drive", "v3", credentials=creds)

    folder_id = utils.get_drive_folder_id(service)

    # list the folder content
    files = utils.get_drive_folder_content(service, folder_id)

    user = await crud.get_user_by_id(user_id)
    mri_files = utils.get_mri_files_per_user(
        user=user, files=files, patient_id=patientID
    )

    patient = await crud.get_patient_by_id(patientID)
    patient_info = {
        "id": patient.id,
        "forename": patient.forename,
        "surname": patient.surname,
        "birth_date": patient.birth_date,
        "created_at": patient.created_at,
    }

    return {"patient": patient_info, "mri_files": mri_files}


@router.post("/patients", response_model=s.PatientSummary)
async def add_patient(
    patient: s.NewPatient,
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
