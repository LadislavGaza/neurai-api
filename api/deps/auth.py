import jwt
import logging

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from api.db import crud
from api.deps import const
from api.deps.utils import APIException, get_logger, get_localization_data

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


async def validate_api_token(
    token: str = Depends(oauth2_scheme),
    translation=Depends(get_localization_data),
    log=Depends(get_logger)
):
    unauthorized = APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": translation["wrong_login"], "type": "auth"},
    )
    try:
        # Decode and validate token in one step
        payload = jwt.decode(token, const.JWT.SECRET, "HS256")
        if payload["audience"] != "api":
            raise unauthorized

    except jwt.ExpiredSignatureError:
        # Get username from invalid token for logging
        payload = jwt.decode(
            token, const.JWT.SECRET, "HS256",
            options={"verify_signature": False}
        )
        if payload:
            username = payload.get("username")
            log.info(
                f"User '{username}' has timed out.",
                extra={"topic": "LOGOUT"}
            )
        raise unauthorized

    except (jwt.InvalidTokenError, jwt.DecodeError):
        raise unauthorized

    return payload["user_id"]


async def validate_reset_token(token: str = Depends(oauth2_scheme), translation=Depends(get_localization_data)):
    unauthorized = APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": translation["wrong_login"], "type": "auth"},
    )
    try:
        payload = jwt.decode(token, const.JWT.SECRET, "HS256")
        if payload["audience"] != "reset-password":
            raise unauthorized

    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        raise unauthorized

    return payload["user_id"]


async def validate_drive_token(
    user_id: int = Depends(validate_api_token),
    log=Depends(get_logger),
    translation=Depends(get_localization_data)
):
    creds = None
    token = None

    user = await crud.get_user_by_id(user_id=user_id)
    refresh_token = user.refresh_token

    if refresh_token:
        web_creds = const.GoogleAPI.CREDS["web"]
        creds = Credentials(
            token,
            refresh_token=refresh_token,
            token_uri=web_creds["token_uri"],
            client_id=web_creds["client_id"],
            client_secret=web_creds["client_secret"],
            scopes=const.GoogleAPI.SCOPES,
        )

    try:
        service = build("drive", "v3", credentials=creds)
        results = (
            service.files()
            .list(
                q=const.GoogleAPI.CONTENT_FILTER,
                fields="nextPageToken, files(id, name)",
            )
            .execute()
        )
        items = results.get("files", [])

    except Exception:
        log.info(
            f"User '{user.username}' used invalid refresh token for Google Drive.",
            extra={"topic": "GOOGLE"}
        )
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": translation["drive_authorization_failed"], "type": "google"},
        )

    # if the NeurAI file doesn't exist create one
    if not items:
        folder_metadata = {
            "name": const.APP_NAME,
            "mimeType": const.GoogleAPI.DRIVE_MIME_TYPE,
        }
        service.files().create(body=folder_metadata, fields="id").execute()

        results = (
            service.files()
            .list(
                q=const.GoogleAPI.CONTENT_FILTER,
                fields="nextPageToken, files(id, name)",
            )
            .execute()
        )
        items = results.get("files", [])

        if not items:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": translation["drive_folder_not_found"]},
            )

    return creds
