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
from googleapiclient.errors import HttpError

from sqlalchemy.exc import IntegrityError
from passlib.hash import argon2
from datetime import datetime, timedelta
from typing import List
from buffered_encryption.aesctr import ReadOnlyEncryptedFile
from gzip import compress
import tempfile
from pathlib import Path
import dicom2nifti
import os
from io import BytesIO

from nibabel.spatialimages import HeaderDataError

import app.schema as s
from app import (
    crud,
    utils,
    const
)


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
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        const.GoogleAPI.CREDS_FILE,
        const.GoogleAPI.SCOPES,
        redirect_uri=const.GoogleAPI.REDIRECT_URL
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return {'autorization_url': authorization_url}


@api.get('/google/authorize/code')
async def drive_authorize_code(code: str, state: str, user_id=Depends(validate_token)):
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        const.GoogleAPI.CREDS_FILE,
        const.GoogleAPI.SCOPES,
        redirect_uri=const.GoogleAPI.REDIRECT_URL,
        state=state
    )

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


@api.get('/google/files')
async def drive_get_files(
        creds=Depends(validate_drive_token),
        user_id: int = Depends(validate_token)):
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
    #     f_e = utils.MRIFile(filename=file['name'], content='')
    #     f_e.download_decrypted(service, file['id'])
    #     with open(file['name'], "wb") as f:
    #         f.write(f_e.content)

    # check the files uploaded by logged in user
    users_files = []
    user = await crud.get_user_by_id(user_id)
    if user.mri_files:
        drive_file_ids = [record['id'] for record in files]
        for file in user.mri_files:
            if file.file_id in drive_file_ids:
                users_files.append({
                    'id': file.file_id,
                    'name': file.filename,
                    'patient_name': f'{file.patient.forename} {file.patient.surname}',
                    'modified_at': file.modified_at
                })

    return {'files': users_files}


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
    dicom_files = []
    nifti_file = None
    try:
        for input_file in files:

            file = utils.MRIFile(
                filename=input_file.filename,
                content=input_file.file
            )

            file.check_file_type()

            if file.is_nifti:
                if len(files)>1:
                    pass # viac ako 1 snimkovanie raise err
                nifti_file = file
            else:
                if nifti_file:
                    pass # raise err viac ako 1 snimkovanie
                dicom_files.append(file)

        if nifti_file:
            upload_file = utils.MRIFile(
                filename=nifti_file.filename,
                content=compress(nifti_file.content)
            )
            upload_file.is_nifti = True
        else:
            tmpdirname = tempfile.TemporaryDirectory()
            temp_dir = Path(tmpdirname.name)

            for dicom_file in dicom_files:
                dicom_file.content.seek(0)
                file_name = temp_dir / dicom_file.filename
                file_name.write_bytes(dicom_file.content.read())

            tmpfile = tempfile.NamedTemporaryFile(suffix='.nii.gz')
            dicom2nifti.dicom_series_to_nifti(temp_dir, Path(tmpfile.name), reorient_nifti=True)
            tmpfile.seek(0) # this 99% needs to be here

            upload_file = utils.MRIFile(
                filename='nigakabel.nii.gz',
                content=BytesIO(tmpfile.read())
            )
            upload_file.is_nifti = True

        # await upload_file.seek(0)  # this 0% needs to be here
        tmpdirname.cleanup()
        tmpfile.close()


        new_file = upload_file.upload_encrypted(
            service=service,
            folder_id=folder_id
        )

        new_files.append(new_file)

        await crud.create_mri_file(
            filename=upload_file.filename,
            file_id=new_file['id'],
            patient_id=patientID,
            user_id=user_id
        )


    except HeaderDataError:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                'message': 'File(s) must be valid dicom or nifti format'
            },
        )
    except HttpError as e:
        status_code = (
            e.status_code
            if e.status_code
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        raise APIException(
            status_code=status_code,
            content={
                'message': 'Google Drive upload failed'
            },
        )

    return {'files': new_files}
