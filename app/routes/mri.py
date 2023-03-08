import base64

from fastapi import (
    APIRouter,
    Depends,
    Response,
    status,
    Form,
    File,
    UploadFile,
)
from sqlalchemy.exc import IntegrityError

from typing import List
from googleapiclient.discovery import build

from app import utils
from app import schema as s
from app.db import crud
from app.utils import APIException
from app.dependencies import validate_api_token, validate_drive_token


router = APIRouter(
    prefix="/mri",
    tags=["mri"],
    responses={404: {"description": "Not found"}},
)


@router.get("/{id}", dependencies=[Depends(validate_api_token)])
async def load_mri_file(id: int, creds=Depends(validate_drive_token)):

    service = build("drive", "v3", credentials=creds)
    f_e = utils.MRIFile(filename="", content="")
    mri = await crud.get_mri_file_by_id(id)
    f_e.download_decrypted(service, mri.file_id)

    return base64.b64encode(f_e.content)


@router.post("/{id}/annotations", response_model=s.AnnotationFiles)
async def upload_annotation(
    id: int,
    name: None | str = Form(default=None),
    files: List[UploadFile] = File(...),
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token)
):
    mri = await crud.get_mri_file_by_id(id)
    new_file = await utils.file_uploader(
        files=files,
        creds=creds,
        mri_id=mri.id,
        patient_id=mri.patient.id,
        user_id=user_id,
        scan_type="annotation",
        name=name
    )
    return {"id": new_file[0]["id"]}


@router.get(
    "/{id}/annotations",
    response_model=List[s.Annotation]
)
async def annotations(
    id: int,
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token),
):
    service = build("drive", "v3", credentials=creds)
    folder_id = utils.get_drive_folder_id(service)
    # get gdrive folder content
    files = utils.get_drive_folder_content(service, folder_id)

    annotations_list = await crud.get_annotations_by_mri_and_user(id, user_id)

    return utils.get_annotations_per_user(annotations_list, files)


@router.delete(
    "/{id}/annotations/{annotation_id}",
)
async def remove_annotation(
    annotation_id: int,
    creds=Depends(validate_drive_token),
    user_id: int = Depends(validate_api_token),

):
    service = build("drive", "v3", credentials=creds)

    annotation = await utils.verify_annotaion_creator(annotation_id, user_id)

    try:
        await crud.delete_annotation(annotation_id)
        service.files().delete(fileId=annotation.file_id).execute()
    except Exception:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": "File does not exist"},
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
        "/{mri_id}/annotations/{annotation_id}", 
        response_model=s.AnnotationFiles, 
        dependencies=[Depends(validate_api_token)]
    )
async def rename_annotation(
    mri_id: int,
    annotation_id: int,
    annotation: s.RenameAnnotation,
    user_id: int = Depends(validate_api_token),
):
    annot = await utils.verify_annotaion_creator(annotation_id, user_id)

    try:
        await crud.update_annotation_name(annotation_id, annotation.name)
    except IntegrityError:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": "Annotation name already exists"},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
