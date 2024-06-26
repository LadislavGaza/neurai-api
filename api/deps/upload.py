import uuid
from typing import List

from fastapi import status, UploadFile
from sqlalchemy.exc import IntegrityError

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from api.db import crud
from api.deps import const
from api.deps import utils
from api.deps.inference import MLInference
from api.deps.mri_file import MRIFile
from api.deps.utils import APIException


def drive_folder_id(service):
    # get folder_id for NeurAI folder
    results = service.files().list(
        q=const.GoogleAPI.CONTENT_FILTER,
        fields="nextPageToken, files(id, name)"
    ).execute()
    items = results.get("files", [])
    if not items:
        return None

    folder_id = items[0]["id"]
    return folder_id


def drive_upload(mri: MRIFile, refresh_token: str) -> dict:
    web_creds = const.GoogleAPI.CREDS["web"]
    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri=web_creds["token_uri"],
        client_id=web_creds["client_id"],
        client_secret=web_creds["client_secret"],
        scopes=const.GoogleAPI.SCOPES,
    )
    service = build("drive", "v3", credentials=creds)
    folder_id = drive_folder_id(service)
    uploaded_file = mri.upload_encrypted(service, folder_id)

    return uploaded_file


def get_drive_folder_id(service, translation):
    folder_id = drive_folder_id(service)

    # if NeurAI folder doesn't exist we need to retry authorization
    if folder_id is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["drive_folder_not_found"]},
        )

    return folder_id


def get_drive_folder_content(service, folder_id):
    files = []
    page_token = None

    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name)",
            pageToken=page_token
        ).execute()

        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken", None)

        if page_token is None:
            break

    return files


def create_nifti(files: List[UploadFile], translation) -> MRIFile:
    # Upload either 1 DICOM sequence or 1 NIfTI file
    # Check for one NIfti
    if len(files) == 1:
        f = files[0]
        mri = MRIFile(filename=str(uuid.uuid4()), content=f.file)
        result = mri.from_nifti()
        if result is False:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": translation["mri_files_invalid"]},
            )
    else:
        # Check for DICOM only series
        dicom_files = []
        for f in files:
            mri = MRIFile(filename=f.filename, content=f.file)
            if not mri.is_dicom():
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message": translation["more_than_one_scanning_uploaded"]
                    },
                )
            dicom_files.append(mri)

        mri = MRIFile(filename=str(uuid.uuid4()), content=None)
        result = mri.from_dicom(dicom_files)
        if result is False:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": translation["mri_files_invalid"]},
            )

    return mri


def file_upload(files: List[UploadFile], creds: Credentials, translation) -> dict:
    mri = create_nifti(files, translation)
    service = build("drive", "v3", credentials=creds)
    folder_id = get_drive_folder_id(service, translation)

    try:
        uploaded_file = mri.upload_encrypted(service, folder_id)

    except HttpError as e:
        status_code = (
            e.status_code if e.status_code else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise APIException(
            status_code=status_code,
            content={"message": translation["drive_upload_failed"]},
        )

    return uploaded_file


async def annotation_upload(
    files: List[UploadFile],
    creds: Credentials,
    patient_id: str,
    user_id: int,
    mri_id: int,
    name: str,
    translation
):
    try:
        annotation_id = await crud.create_annotation_file(
            name=name,
            mri_id=mri_id,
            patient_id=patient_id,
            user_id=user_id,
            is_ai=False
        )
    except IntegrityError:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": translation["annotation_name_exists"]}
        )

    new_file = file_upload(files, creds, translation)
    await crud.update_annotation_file(
        id=annotation_id,
        filename=new_file["name"],
        file_id=new_file["id"],
        visible=True
    )
    new_file["id"] = annotation_id

    return new_file


async def mri_upload(
    files: List[UploadFile],
    creds: Credentials,
    patient_id: str,
    screening_id: int,
    user_id: int,
    translation,
    series_uid: str = None
):
    new_file = file_upload(files, creds, translation)
    new_file["id"] = await crud.create_mri_file(
        filename=new_file["name"],
        file_id=new_file["id"],
        patient_id=patient_id,
        screening_id=screening_id,
        user_id=user_id,
        series_uid=series_uid
    )

    return new_file


async def mri_auto_annotate(
    upload_file: dict,
    patient_id: int,
    user_id: int,
    translation
):
    mri_id = upload_file["id"]

    try:
        annotation_id = await crud.create_annotation_file(
            name=const.ANNOT_MASK_AI,
            mri_id=mri_id,
            patient_id=patient_id,
            user_id=user_id,
            is_ai=True
        )
    except IntegrityError:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": translation["annotation_name_exists"]}
        )

    ml = MLInference()
    job_name = ml.launch(upload_file["content"])

    await crud.start_inference(annotation_id, job_name)
