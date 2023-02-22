from fastapi import APIRouter, Depends, File, UploadFile, status
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


from nibabel.spatialimages import HeaderDataError
from nibabel.wrapstruct import WrapStructError
from dicom2nifti.exceptions import ConversionValidationError

from typing import List

from app import utils
import app.schema as s
from app.db import crud
from app.dependencies import validate_api_token, validate_drive_token
from app.utils import APIException

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
async def upload(
    patientID: str,
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token),
    files: List[UploadFile] = File(...),
):

    service = build("drive", "v3", credentials=creds)

    folder_id = utils.get_drive_folder_id(service)

    new_files = []
    dicom_files = []
    nifti_file = None
    try:
        for input_file in files:

            file = utils.MRIFile(filename=input_file.filename, content=input_file.file)

            nifti_file, dicom_files = file.create_valid_series(
                files_length=len(files), nifti_file=nifti_file, dicom_files=dicom_files
            )

        upload_file = utils.MRIFile(filename="", content=None)
        upload_file.prepare_zipped_nifti(nifti_file=nifti_file, dicom_files=dicom_files)
        new_file = upload_file.upload_encrypted(service=service, folder_id=folder_id)
        new_files.append(new_file)

        await crud.create_mri_file(
            filename=new_file["name"],
            file_id=new_file["id"],
            patient_id=patientID,
            user_id=user_id,
        )

    except (HeaderDataError, WrapStructError, ConversionValidationError):
        # Unable to process files for upload
        # For Nifti: invalid header data or wrong block size
        # For Dicom: not enough slices (<4) or inconsistent slice increment
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "File(s) must be valid dicom or nifti format"},
        )
    except APIException as excep:
        raise excep
    except HttpError as e:
        status_code = (
            e.status_code if e.status_code else status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        raise APIException(
            status_code=status_code,
            content={"message": "Google Drive upload failed"},
        )

    return {"mri_files": new_files}


@router.get("/patient/{patientID}/files", response_model=s.PatientFilesPatientDetail)
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
        "created_at": patient.created_at,
    }

    return {"patient": patient_info, "mri_files": mri_files}
