import base64

from fastapi import (
    APIRouter,
    Depends,
    Response,
    status
)
from googleapiclient.discovery import build

from app import utils
from app import schema as s
from app.db import crud
from app.dependencies import validate_api_token, validate_drive_token


router = APIRouter(
    prefix="/mri",
    tags=["mri"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/{file_id}",
    dependencies=[Depends(validate_api_token)]
)
async def load_mri_file(file_id: str, creds=Depends(validate_drive_token)):
    service = build("drive", "v3", credentials=creds)
    f_e = utils.MRIFile(filename="", content="")
    f_e.download_decrypted(service, file_id)

    return base64.b64encode(f_e.content)


@router.post("/{file_id}/annotations", response_model=s.AnnotationFiles)
async def upload_annotation(
    file_id: str,
    annotation: s.AnnotationFilesUpload,
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token),
):
    mri = await crud.get_mri_file_by_file_id(mri_file_id=file_id)
    new_file = await utils.file_uploader(
        files=[annotation.file],
        creds=creds,
        mri_id=mri.id,
        patient_id=mri.patient.id,
        user_id=user_id,
        scan_type='annotation',
        name=annotation.name
    )

    return {"id": new_file[0].id}


@router.delete(
    "/{mri_ID}/annotations/{annotation_ID}",
    dependencies=[Depends(validate_api_token)]
)
async def drive_remove_authorization(
    annotation_ID: str,
    creds=Depends(validate_drive_token)
):
    service = build("drive", "v3", credentials=creds)
    await crud.delete_annotations_by_file_id(file_id=annotation_ID)
    service.files().delete(fileId=annotation_ID).execute()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
