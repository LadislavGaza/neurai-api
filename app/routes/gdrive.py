from fastapi import APIRouter, Depends, status, Response

import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


from app import utils
from app.static import const
from app.db import crud
from app.dependencies import (
    validate_api_token, validate_drive_token, get_logger
)
import app.schema as s
from app.utils import APIException


router = APIRouter(
    prefix="/google",
    tags=["google"],
)


@router.get(
    "/authorize",
    response_model=s.AuthorizationURL, dependencies=[Depends(validate_api_token)]
)
async def drive_authorize():
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        const.GoogleAPI.CREDS_FILE,
        const.GoogleAPI.SCOPES,
        redirect_uri=const.GoogleAPI.REDIRECT_URL,
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    return {"autorization_url": authorization_url}


@router.get("/authorize/code", response_model=s.AuthorizationCode)
async def drive_authorize_code(
    code: str,
    state: str,
    user_id=Depends(validate_api_token),
    log = Depends(get_logger)
):
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        const.GoogleAPI.CREDS_FILE,
        const.GoogleAPI.SCOPES,
        redirect_uri=const.GoogleAPI.REDIRECT_URL,
        state=state,
    )

    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        creds.refresh(Request())

    except Exception:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": "Google drive authorization failed", "type": "google"},
        )

    await crud.update_user_refresh_token(
        user_id=user_id, refresh_token=creds.refresh_token
    )

    service = build("drive", "v3", credentials=creds)
    about = service.about().get(
        fields="user(emailAddress)"
    ).execute()
    email = about["user"].get("emailAddress", "")
    await crud.update_user_associated_drive(user_id=user_id, email=email)

    user = await crud.get_user_by_id(user_id)
    log.info(
        f"User '{user.username}' has authorized access to Google Drive.",
        extra={"topic": "GOOGLE"}
    )

    return {"message": "Google authorization successful"}


@router.get("/files", response_model=s.GoogleFiles)
async def drive_get_files(
    creds=Depends(validate_drive_token),
    user_id: int = Depends(validate_api_token),
):
    service = build("drive", "v3", credentials=creds)

    folder_id = utils.get_drive_folder_id(service)
    q = f"'{folder_id}' in parents and trashed=false"

    # list the folder content
    files = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(q=q, fields="nextPageToken, files(id, name)", pageToken=page_token)
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken", None)
        if page_token is None:
            break

    users_files = []
    user = await crud.get_user_by_id(user_id)
    if user.mri_files:
        drive_file_ids = [record["id"] for record in files]
        for file in user.mri_files:
            if file.file_id in drive_file_ids:
                users_files.append(
                    {
                        "id": file.file_id,
                        "name": file.filename,
                        "patient_name": f"{file.patient.forename} {file.patient.surname}",
                        "modified_at": file.modified_at,
                    }
                )

    return {"files": users_files}


@router.delete("/remove")
async def drive_remove_authorization(
    user_id: int = Depends(validate_api_token),
    log = Depends(get_logger)
):
    await crud.update_user_refresh_token(user_id=user_id, refresh_token=None)
    await crud.update_user_associated_drive(user_id=user_id, email=None)

    user = await crud.get_user_by_id(user_id)
    log.info(
        f"User '{user.username}' has revoked authorization for Google Drive.",
        extra={"topic": "GOOGLE"}
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
