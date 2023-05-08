import json
import logging
from random import choices
import string
from fastapi import status, Request

from api.db import crud
from api.deps import const


class APIException(Exception):
    status_code = None
    content = None

    def __init__(self, content, status_code: int):
        self.content = content
        self.status_code = status_code


async def get_logger():
    return logging.getLogger(const.APP_NAME)


async def get_mri_files_and_annotations_per_screening(user, files, screening_id):
    mri_files = []
    drive_file_ids = [record["id"] for record in files]

    for file in user.mri_files:
        if file.file_id in drive_file_ids and file.screening_id == screening_id:
            annotations = await crud.get_annotations_by_mri_and_user(
                mri_id=file.id, user_id=user.id
            )

            # verify annotation presence in drive
            annotations = get_existing_files_per_user(annotations, files)
            mri_files.append({
                "id": file.id,
                "name": file.filename,
                "series_uid": file.series_uid,
                "created_at": file.created_at,
                "modified_at": file.modified_at,
                "annotation_files": annotations
            })

    return mri_files


def generate_unique_patient_id():
    return ''.join(choices(string.ascii_uppercase + string.digits, k=10))


def get_existing_files_per_user(files, drive_files):
    annotation_files = []
    drive_file_ids = [record["id"] for record in drive_files]
    for file in files:
        if (file.file_id in drive_file_ids) or (file.is_ai):
            annotation_files.append(file)

    return annotation_files


async def verify_file_creator(file_id, user_id, file_type, translation):
    if file_type == "annotation":
        file = await crud.get_annotation_by_id(file_id)
    elif file_type == "mri":
        file = await crud.get_mri_file_by_id(file_id)
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


def get_localization_data(request: Request):
    accepted_language = request.headers.get("Accept-Language")

    translation = None
    if not accepted_language or accepted_language not in const.I18n.LANGUAGES:
        accepted_language = const.I18n.DEFAULT_LANGUAGE

    if accepted_language == "en":
        translation = open("api/lang/en.json", "r")
    elif accepted_language == "sk":
        translation = open("api/lang/sk.json", "r")

    return json.load(translation)


def get_screenings_and_mri_files_per_patient(
        files,
        screenings
):
    studies = []

    for study in screenings:
        series = get_existing_files_per_user(study.mri_files, files)
        studies.append({
            'study_uid': study.study_uid,
            'mri_files': series
        })

    return studies
