from sqlalchemy.exc import IntegrityError
from typing import List

from dicom2nifti.exceptions import ConversionValidationError
from google.auth.api_key import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from nibabel.spatialimages import HeaderDataError
from nibabel.wrapstruct import WrapStructError
from pydicom import dcmread
from pydicom.errors import InvalidDicomError
import dicom2nifti

from buffered_encryption.aesctr import EncryptionIterator, ReadOnlyEncryptedFile

from gzip import compress
import tempfile
from pathlib import Path

import logging
from random import choice, choices
import string

from api.db import crud
from api.deps import const
from api.deps.mri_file import MRIFile

from fastapi import status, UploadFile


class APIException(Exception):
    status_code = None
    content = None

    def __init__(self, content, status_code: int):
        self.content = content
        self.status_code = status_code


def get_drive_folder_id(service):
    # get folder_id for NeurAI folder
    results = service.files().list(
        q=const.GoogleAPI.CONTENT_FILTER,
        fields="nextPageToken, files(id, name)"
    ).execute()
    items = results.get("files", [])

    # if NeurAI folder doesn"t exist we need to retry authorization
    if not items:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Folder NeurAI not found"},
        )

    return items[0]["id"]


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


# TO BE DELETED
async def get_mri_files_and_annotations_per_user(user, files, patient_id):
    mri_files = []
    drive_file_ids = [record["id"] for record in files]

    for file in user.mri_files:
        if file.file_id in drive_file_ids and file.patient.id == patient_id:
            annotations = await crud.get_annotations_by_mri_and_user(
                mri_id = file.id, user_id = user.id
            )

            # verify annotation presence in drive 
            annotations = get_annotations_per_user(annotations, files)
            mri_files.append({
                "id": file.id,
                "name": file.filename,
                "created_at": file.created_at,
                "modified_at": file.modified_at,
                "annotation_files": annotations
            })

    return mri_files


async def get_mri_files_and_annotations_per_screening(user, files, screening_id):
    mri_files = []
    drive_file_ids = [record["id"] for record in files]

    for file in user.mri_files:
        if file.file_id in drive_file_ids and file.screening.id == screening_id:
            annotations = await crud.get_annotations_by_mri_and_user(
                mri_id = file.id, user_id = user.id
            )

            # verify annotation presence in drive 
            annotations = get_annotations_per_user(annotations, files)
            mri_files.append({
                "id": file.id,
                "name": file.filename,
                "created_at": file.created_at,
                "modified_at": file.modified_at,
                "annotation_files": annotations
            })

    return mri_files


async def file_uploader(
        files: List[UploadFile],
        creds: Credentials,
        patient_id: str,
        user_id: int,
        scan_type: str,
        mri_id,
        name: str,
        screening_id: int | None
):
    if scan_type == 'annotation':
        try:
            id = await crud.create_annotation_file(
                name=name,
                mri_id=mri_id,
                patient_id=patient_id,
                user_id=user_id,
            )
        except IntegrityError:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"message": "Annotation name already exists"},
            )

    service = build("drive", "v3", credentials=creds)

    folder_id = get_drive_folder_id(service)
    new_files = []
    dicom_files = []
    nifti_file = None
    try:
        for input_file in files:
            file = MRIFile(filename=input_file.filename, content=input_file.file)

            nifti_file, dicom_files = file.create_valid_series(
                files_length=len(files), nifti_file=nifti_file, dicom_files=dicom_files
            )

        upload_file = MRIFile(filename="", content=None)
        upload_file.prepare_zipped_nifti(nifti_file=nifti_file, dicom_files=dicom_files)
        new_file = upload_file.upload_encrypted(service=service, folder_id=folder_id)
        new_files.append(new_file)

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

    if scan_type == 'mri':
        id = await crud.create_mri_file(
            filename=new_file["name"],
            file_id=new_file["id"],
            patient_id=patient_id,
            screening_id=screening_id,
            user_id=user_id,
        )
    else:
        await crud.update_annotation_file(
            id=id,
            filename=new_file["name"],
            file_id=new_file["id"]
        )
    new_files[0]['id'] = id
    return new_files


def generate_unique_patient_id():
    return ''.join(choices(string.ascii_uppercase + string.digits, k=10))


def get_annotations_per_user(annotations, files):
    annotation_files = []
    drive_file_ids = [record["id"] for record in files]
    for file in annotations:
        if file.file_id in drive_file_ids:
            annotation_files.append({
                    "id": file.id,
                    "name": file.name
                })
    
    return annotation_files


async def verify_annotaion_creator(annotation_id, user_id):
    annotation = await crud.get_annotation_by_id(annotation_id)
    if not annotation:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "File doesn't exists"},
        )
    if annotation.created_by != user_id:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": "Activity not allowed for current user"},
        )
    return annotation


async def get_logger():
    return logging.getLogger(const.APP_NAME)

