import google_auth_oauthlib.flow
import jwt
from fastapi import (
    FastAPI,
    status,
    Response,
    Depends,
    HTTPException,
    UploadFile,
    File
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse

import google_auth_oauthlib.flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from io import BytesIO

from sqlalchemy.exc import IntegrityError
from passlib.hash import argon2
from datetime import datetime, timedelta
from typing import List
from pydicom.errors import InvalidDicomError
from pydicom.filereader import dcmread
from buffered_encryption.aesctr import EncryptionIterator, ReadOnlyEncryptedFile


import app.schema as s
from app import crud
from app import const


class APIException(Exception):
    status_code = None
    content = None

    def __init__(self, content, status_code: int):
        self.content = content
        self.status_code = status_code


api = FastAPI(
    title=const.APP_NAME,
    description='Intelligent neurosurgeon assistant',
    docs_url='/docs',
    redoc_url=None,
    contact={
        'name': 'Team 23',
        'url': 'https://team23-22.studenti.fiit.stuba.sk/neurai',
    }
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=const.CORS.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login')

flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    const.GoogleAPI.CREDS_FILE,
    const.GoogleAPI.SCOPES,
    redirect_uri=const.GoogleAPI.REDIRECT_URL
)


@api.exception_handler(APIException)
async def api_exception_handler(request: Request(), exc: APIException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.content,
    )


@api.exception_handler(HTTPException)
async def validation_exception_handler(request, err: HTTPException):

    if ('/google/' in str(request.url) and
            err.status_code == status.HTTP_401_UNAUTHORIZED):

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                'message': 'Authentification failed',
                'type': 'auth'
            },
        )
    else:
        return JSONResponse(
            status_code=err.status_code,
            content={
                'message': 'Exception',
                'detail': err.detail}
        )


async def validate_token(token: str = Depends(oauth2_scheme)):
    unauthorized = APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            'message': 'Invalid credentials',
            'type': 'auth'
        }
    )
    try:
        payload = jwt.decode(token, const.JWT.SECRET, 'HS256')
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        raise unauthorized

    return payload['user_id']


async def validate_drive_token(user_id: int = Depends(validate_token)):
    creds = None
    token = ''

    refresh_token = (
        await crud.get_user_by_id(user_id=user_id)
    ).refresh_token

    if refresh_token:
        web_creds = const.GoogleAPI.CREDS['web']
        creds = Credentials(
            token,
            refresh_token=refresh_token,
            token_uri=web_creds['token_uri'],
            client_id=web_creds['client_id'],
            client_secret=web_creds['client_secret'],
            scopes=const.GoogleAPI.SCOPES
        )

    try:
        service = build('drive', 'v3', credentials=creds)
        results = service.files().list(
            q=const.GoogleAPI.CONTENT_FILTER,
            fields="nextPageToken, files(id, name)"
        ).execute()
        items = results.get('files', [])

    except Exception:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                'message': 'Google drive authorization failed',
                'type': 'google'
            },
        )

    # if the NeurAI file doesn't exists create one
    if not items:
        folder_metadata = {
            'name': const.APP_NAME,
            'mimeType': const.GoogleAPI.DRIVE_MIME_TYPE
        }
        service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()

        results = service.files().list(
            q=const.GoogleAPI.CONTENT_FILTER,
            fields="nextPageToken, files(id, name)"
        ).execute()
        items = results.get('files', [])

        if not items:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'message': 'Folder NeurAI not found'},
            )

    return creds


@api.post('/registration')
async def registration(user: s.UserCredential):
    try:
        user.password = argon2.hash(user.password)
        await crud.create_user(user)

    except IntegrityError:
        raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={'message': 'User with this name already exists'}
        )

    return Response(status_code=status.HTTP_201_CREATED)


@api.post('/login')
async def login(user: s.UserCredential):
    account = await crud.get_user(user)

    valid_credentials = (
        account is not None and
        argon2.verify(user.password, account.password)
    )

    if valid_credentials:
        expiration = (
            datetime.utcnow() +
            timedelta(seconds=const.JWT.EXPIRATION_SECONDS)
        )
        payload = {
            'user_id': account.id,
            'exp': expiration
        }
        token = jwt.encode(payload, const.JWT.SECRET, 'HS256')
        return {'token': token}

    raise APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            'message': 'Wrong email or password',
            'type': 'auth'
        }
    )


@api.get('/patients',
         dependencies=[Depends(validate_token)],
         response_model=List[s.PatientSummary])
async def patients_overview():
    return (await crud.get_patients()).all()


@api.get('/google/authorize', dependencies=[Depends(validate_token)])
async def drive_authorize():
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return {'autorization_url': authorization_url}


@api.get('/google/authorize/code')
async def drive_authorize_code(code: str, user_id=Depends(validate_token)):
    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        creds.refresh(Request())

    except Exception:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                'message': 'Google drive authorization failed',
                'type': 'google'
            }
        )

    await crud.update_user_refresh_token(
        user_id=user_id,
        refresh_token=creds.refresh_token
    )

    return {'message': 'Google authorization successful'}


@api.get('/google/files', dependencies=[Depends(validate_token)])
async def drive_get_files(creds=Depends(validate_drive_token)):
    service = build('drive', 'v3', credentials=creds)

    # get folder_id for NeurAI folder
    results = service.files().list(
        q=const.GoogleAPI.CONTENT_FILTER,
        fields="nextPageToken, files(id, name)"
    ).execute()
    items = results.get('files', [])

    # if NeurAI folder doesn't exist we need to retry authorization
    if not items:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={'message': 'Folder NeurAI not found'},
        )

    folder_id = items[0]['id']
    q = f"'{folder_id}' in parents and trashed=false"

    # list the folder content
    files = []
    page_token = None
    while True:
        response = service.files().list(
            q=q,
            fields='nextPageToken, files(id, name)',
            pageToken=page_token
        ).execute()
        files.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    # read and decrypt file, code for later

    # for file in files:
    #     file_media = service.files().get_media(fileId=file['id']).execute()
    #     with BytesIO(file_media) as file_media_bytes:
    #         file_media_bytes.seek(0)
    #         ef = ReadOnlyEncryptedFile(file_media_bytes,const.ENC.KEY,const.ENC.SIG)
    #         with open(file['name'],"wb") as f:
    #             f.write(ef.read())  # close file ?? 

    return {'files': files}


@api.get('/profile')
async def profile(user_id: int = Depends(validate_token)):
    user = await crud.get_user_by_id(user_id=user_id)
    authorized_drive = True if user.refresh_token else False
    return {
        'email': user.email,
        'authorizedDrive': authorized_drive
    }


@api.get('/test', dependencies=[Depends(validate_token)])
async def test():
    return {'email': 'abc@abc.sk'}


@api.get('/user')
async def user_resource(user_id: int = Depends(validate_token)):
    return {'user': user_id}


@api.post('/patient/{patientID}/files')
async def upload(
        patientID: str,
        user_id: int = Depends(validate_token),
        creds=Depends(validate_drive_token),
        files: List[UploadFile] = File(...)):

    service = build('drive', 'v3', credentials=creds)

    # get folder_id for NeurAI folder
    results = service.files().list(
        q=const.GoogleAPI.CONTENT_FILTER,
        fields="nextPageToken, files(id, name)"
    ).execute()
    items = results.get('files', [])

    # if NeurAI folder doesn't exist we need to retry authorization
    if not items:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={'message': 'Folder NeurAI not found'},
        )

    folder_id = items[0]['id']

    new_files = []
    try:
        for upload_file in files:
            dicom_meta = dcmread(upload_file.file)
            patient_name = dicom_meta.PatientName

            await crud.create_mri_file(
                filename=upload_file.filename,
                patient_id=patientID,
                user_id=user_id
            )

            await upload_file.seek(0)  # this 100% needs to be here

            enc_file = EncryptionIterator(
                upload_file.file,
                const.ENC.KEY,
                const.ENC.SIG
                )

            cipher_file = BytesIO()
            for chunk in enc_file:
                cipher_file.write(chunk)

            file_metadata = {
                'name': upload_file.filename,
                'parents': [folder_id]
            }
            media = MediaIoBaseUpload(
                cipher_file,
                mimetype='application/octet-stream', 
                resumable=True
            )
            uploaded_file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,mimeType,createdTime'
            ).execute()
            new_files.append({
                'id': uploaded_file.get('id'),
                'name': uploaded_file.get('name'),
                'mimeType': uploaded_file.get('mimeType'),
                'createdTime': uploaded_file.get('createdTime')
            })

    except InvalidDicomError as e:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                'message': 'File(s) must be dicom format'
            },
        )
    except Exception as e:
        status_code = (
            e.response.status_code
            if e.response.status_code
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        raise APIException(
            status_code=status_code,
            content={
                'message': 'Google Drive upload failed'
            },
        )

    return {'files': new_files}
