import json
import logging
from random import choices
import string
from typing import List
from fastapi import status, Request

from api.db import crud
from api.deps import const

import api.main as main


class APIException(Exception):
    status_code = None
    content = None

    def __init__(self, content, status_code: int):
        self.content = content
        self.status_code = status_code


def get_drive_folder_id(service, translation):
    # get folder_id for NeurAI folder
    results = service.files().list(
        q=const.GoogleAPI.CONTENT_FILTER,
        fields="nextPageToken, files(id, name)"
    ).execute()
    items = results.get("files", [])

    # if NeurAI folder doesn't exist we need to retry authorization
    if not items:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["drive_folder_not_found"]},
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


async def get_mri_files_and_annotations_per_screening(user, files, screening_id):
    mri_files = []
    drive_file_ids = [record["id"] for record in files]

    for file in user.mri_files:
        if file.file_id in drive_file_ids and file.screening_id == screening_id:
            annotations = await crud.get_annotations_by_mri_and_user(
                mri_id=file.id, user_id=user.id
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


async def verify_file_creator(file_id, user_id, file_type, translation):
    if file_type == "annotation":
        file = await crud.get_annotation_by_id(file_id)
    elif file_type == "mri":
        file = await crud.get_mri_by_id(file_id)
    if not file:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": translation["file_not_found"]},
        )
    if file.created_by != user_id:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": translation["activity_not_allowed"]},
        )
    return file


async def get_logger():
    return logging.getLogger(const.APP_NAME)


def get_localization_data(request: Request):
    accepted_language = request.headers.get("Accept-Language")

    translation = None
    if not accepted_language or accepted_language not in main.app_languages:
        accepted_language = main.language_fallback

    if accepted_language == "en":
        translation = open("api/lang/en.json", "r")
    elif accepted_language == "sk":
        translation = open("api/lang/sk.json", "r")

    return json.load(translation)
