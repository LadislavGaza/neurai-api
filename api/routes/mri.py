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
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError

from typing import List
from googleapiclient.discovery import build

import api.deps.schema as s
from api.db import crud
from api.deps import utils
from api.deps import upload
from api.deps.mri_file import MRIFile
from api.deps.upload import annotation_upload
from api.deps.utils import APIException, get_localization_data
from api.deps.auth import validate_api_token, validate_drive_token
from api.api import app as app_fastapi


router = APIRouter(
    prefix="/mri",
    tags=["mri"],
    responses={404: {"description": "Not found"}},
)


@router.get("/{id}", dependencies=[Depends(validate_api_token)])
async def load_mri_file(id: int, creds=Depends(validate_drive_token)):

    service = build("drive", "v3", credentials=creds)
    f_e = MRIFile(filename="", content="")
    mri = await crud.get_mri_file_by_id(id)
    f_e.download_decrypted(service, mri.file_id)

    return base64.b64encode(f_e.content)


@router.patch(
    "/{mri_id}",
    dependencies=[Depends(validate_api_token)]
)
async def rename_mri(
    mri_id: int,
    mri: s.RenameMRI,
    user_id: int = Depends(validate_api_token),
    translation=Depends(get_localization_data)
):
    mri_file = await utils.verify_file_creator(mri_id, user_id, "mri", translation)

    try:
        await crud.update_mri_name(mri_id, mri.name)
    except IntegrityError:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": translation["mri_name_exists"]},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id}/annotations", response_model=s.AnnotationFiles)
async def upload_annotation(
    id: int,
    name: None | str = Form(default=None),
    files: List[UploadFile] = File(...),
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token),
    translation=Depends(get_localization_data)
):
    mri = await crud.get_mri_file_by_id(id)
    new_file = await annotation_upload(
        files=files,
        creds=creds,
        patient_id=mri.patient.id,
        user_id=user_id,
        mri_id=mri.id,
        name=name,
        translation=translation
    )
    return {"id": new_file["id"]}


@router.get(
    "/{id}/annotations",
    response_model=List[s.Annotation]
)
async def annotations(
    id: int,
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token),
    translation=Depends(get_localization_data)
):
    service = build("drive", "v3", credentials=creds)
    folder_id = upload.get_drive_folder_id(service, translation)
    # get gdrive folder content
    files = upload.get_drive_folder_content(service, folder_id)

    annotations_list = await crud.get_annotations_by_mri_and_user(id, user_id)

    return utils.get_annotations_per_user(annotations_list, files)


@router.get(
    "/{id}/annotations/{annotation_id}",
    dependencies=[Depends(validate_api_token)]
)
async def load_annotation(
    id: int,
    annotation_id: int,
    creds=Depends(validate_drive_token),
    translation=Depends(get_localization_data)
):
    service = build("drive", "v3", credentials=creds)
    f_e = MRIFile(filename="", content="")

    annotation = await crud.get_annotation_by_id(annotation_id)
    if annotation is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["annotation_not_found"]},
        )
    if annotation.ready is False:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": translation["annotation_not_ready"]},
        )

    f_e.download_decrypted(service, annotation.file_id)

    return base64.b64encode(f_e.content)


@router.delete(
    "/{id}/annotations/{annotation_id}",
)
async def remove_annotation(
    annotation_id: int,
    creds=Depends(validate_drive_token),
    user_id: int = Depends(validate_api_token),
    translation=Depends(get_localization_data)
):
    service = build("drive", "v3", credentials=creds)

    annotation = await utils.verify_file_creator(
        annotation_id,
        user_id,
        "annotation",
        translation
    )

    try:
        await crud.delete_annotation(annotation_id)
        service.files().delete(fileId=annotation.file_id).execute()
    except Exception:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["file_not_found"]}
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{mri_id}/annotations/{annotation_id}",
    response_model=s.AnnotationFiles,
    dependencies=[Depends(validate_api_token)]
)
async def change_annotation(
    mri_id: int,
    annotation_id: int,
    annotation: s.AnnotationEdit,
    user_id: int = Depends(validate_api_token),
    translation=Depends(get_localization_data)
):
    annot = await utils.verify_file_creator(
        annotation_id,
        user_id,
        "annotation",
        translation
    )
    try:
        annotation = annotation.dict(exclude_none=True, exclude_unset=True)
        await crud.update_annotation_details(annotation_id, annotation)

    except IntegrityError:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": translation["annotation_name_exists"]},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# overall logic: 2 queues
# 1. queue for annotation jobs that are in progress and requested from FE
# waiting_for_inference_queue
# 2. queue for annotation jobs that are ready and requested from FE to return to user
# finished_inference_message_queue

@router.post('/{mri_id}/annotations/ai')
async def ai_annotation_visible(
    visible: bool,
    mri_id: int,
    user_id: int = Depends(validate_api_token),
    translation=Depends(get_localization_data)
):
    if visible:

        annotation = await crud.get_ai_annotation_by_mri_id_and_user(mri_id, user_id)
        # something failed in processing the annotation from Azure
        if annotation is None:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": translation["annotation_not_found"]},
            )

        # this is method that will be called by streaming response or some other sse handler
        async def generate():
            unprocessed_mri_id_messages = []
            while True:
                mri_id_message = app_fastapi.finished_inference_message_queue.get_nowait()

                if mri_id_message['user_id'] == user_id and mri_id_message['mri_id'] == mri_id:
                    yield mri_id_message
                    app_fastapi.finished_inference_message_queue.task_done()
                    break
                else:
                    unprocessed_mri_id_messages.append(mri_id_message)
            await app_fastapi.finished_inference_message_queue.join()

            # return all not matching this request to the queue
            for message in unprocessed_mri_id_messages:
                app_fastapi.finished_inference_message_queue.put_nowait(message)

        # annotation is not ready yet, inference on Azure is still in progress
        if annotation.ready is False:
            # Return a streaming response for SSE

            return StreamingResponse(generate(), media_type="text/event-stream")
        else:
            return {
                'annotation-id': annotation.id,
                'user_id': user_id,
                'mri_id': mri_id,
                'screening_id': annotation.mri_file.screening_id,
            }
