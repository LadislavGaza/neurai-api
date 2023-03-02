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
    name: str | None = Form(),
    files: List[UploadFile] = File(...),
    user_id: int = Depends(validate_api_token),
    creds = Depends(validate_drive_token),
):
    mri = await crud.get_mri_file_by_id(id)
    new_file = await utils.file_uploader(
        files=files,
        creds=creds,
        mri_id=mri.id,
        patient_id=mri.patient.id,
        user_id=user_id,
        scan_type='annotation',
        name=name
    )
    return {"id": new_file[0]["id"]}


@router.get(
    "/{id}/annotations",
    dependencies=[Depends(validate_api_token)],
    response_model=List[s.Annotation]
)
async def annotations(id: int, creds=Depends(validate_drive_token)):
    return (await crud.get_annotations(id)).all()


@router.delete(
    "/{id}/annotations/{annotation_id}",
    dependencies=[Depends(validate_api_token)]
)
async def remove_annotation(
    annotation_id: int,
    creds=Depends(validate_drive_token)
):
    service = build("drive", "v3", credentials=creds)
    try:
        annotation = await crud.get_annotation_by_id(annotation_id)
        await crud.delete_annotation(annotation_id)
        service.files().delete(fileId=annotation.file_id).execute()
    except Exception:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": "File does not exist"},
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
