import json
import os

import google_auth_oauthlib.flow
import jwt
from fastapi import (
    FastAPI,
    status,
    HTTPException,
    Response,
    Depends
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.crud import update_user_refresh_token, get_user_by_id

from sqlalchemy.exc import IntegrityError
from passlib.hash import argon2
from datetime import datetime, timedelta

import app.schema as s
from app import crud
import app.model as m


# Generate with: openssl rand -hex 32
JWT_SECRET = os.environ.get('JWT_SECRET')
JWT_EXPIRATION_SECONDS = int(os.environ.get('JWT_EXPIRATION_SECONDS'))
ORIGINS = [
    'https://team23-22.studenti.fiit.stuba.sk'
    'http://localhost',
    'http://localhost:4040',
]

api = FastAPI(
    title='NeurAI',
    description='Intelligent neurosurgeon assistant',
    docs_url='/docs',
    redoc_url=None,
    contact={
        "name": "Team 23",
        "url": "https://team23-22.studenti.fiit.stuba.sk/neurai",
    }
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login')

SCOPES = ['https://www.googleapis.com/auth/drive.file']
flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    'config/WEB_credentials.json',
    SCOPES,
    redirect_uri=os.environ.get('REDIRECT_URL')
)


async def validate_token(token: str = Depends(oauth2_scheme)):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, 'HS256')
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        raise unauthorized

    return payload['user_id']


async def validate_drive_token(user_id: int = Depends(validate_token)):
    creds = None
    f = open('config/WEB_credentials.json')
    web_cred = json.load(f)
    client_id = web_cred['web']['client_id']
    client_secret = web_cred['web']['client_secret']
    token_uri = web_cred['web']['token_uri']
    token = ''

    refresh_token = (await get_user_by_id(user_id=user_id)).refresh_token

    if refresh_token:
        creds = Credentials(
            token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES
        )
    try:
        service = build('drive', 'v3', credentials=creds)
        results = service.files().list(
            q="mimeType = 'application/vnd.google-apps.folder' and name='NeurAI'",
            fields="nextPageToken, files(id, name)"
        ).execute()
        items = results.get('files', [])
    except RefreshError:
        return JSONResponse(
            content={'message': 'Google drive authorization failed', 'type': 'google'},
            status_code=401
        )

    if not items:
        folder_metadata = {
            'name': 'NeurAI',
            'mimeType': 'application/vnd.google-apps.folder'
        }
        service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()

        results = service.files().list(
            q="mimeType = 'application/vnd.google-apps.folder' and name='NeurAI'",
            fields="nextPageToken, files(id, name)"
        ).execute()
        items = results.get('files', [])

        if not items:
            return JSONResponse(
                content={'message': 'Folder NeurAI not found'},
                status_code=404
            )

    return creds


@api.post('/registration')
async def registration(user: s.UserCredential,
                       status_code=status.HTTP_201_CREATED):
    try:
        user.password = argon2.hash(user.password)
        await crud.create_user(user)
    except IntegrityError:
        raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='User with this name already exists'
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
            timedelta(seconds=JWT_EXPIRATION_SECONDS)
        )
        payload = {
            'user_id': account.id,
            'exp': expiration
        }
        token = jwt.encode(payload, JWT_SECRET, 'HS256')
        return {'token': token}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Wrong email or password'
    )


@api.get('/test', dependencies=[Depends(validate_token)])
async def test():
    return {'email': 'abc@abc.sk'}


@api.get('/user')
async def user_resource(user_id: int = Depends(validate_token)):
    return {'user': user_id}


@api.get('/google/authorize')
async def drive_authorize():
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return JSONResponse(
                content={'autorization_url': authorization_url},
                status_code=200
            )


@api.get('/google/authorize/code')
async def drive_authorize_code(code: str, user_id=Depends(validate_token)):
    flow.fetch_token(code=code)
    creds = flow.credentials

    try:
        creds.refresh(Request())
    except RefreshError:
        return JSONResponse(
            content={'message': 'Google drive authorization failed', 'type': 'google'},
            status_code=401
        )

    refresh_token = creds.refresh_token
    await update_user_refresh_token(user_id=user_id, refresh_token=refresh_token)
    return JSONResponse(
                content={'creds': creds.to_json()},
                status_code=200
            )


@api.get('/google/get/files', dependencies=[Depends(validate_token)])
async def drive_get_files(validation_output=Depends(validate_drive_token)):
    if type(validation_output) == JSONResponse:
        return validation_output

    creds = validation_output
    service = build('drive', 'v3', credentials=creds)

    results = service.files().list(
        q="mimeType = 'application/vnd.google-apps.folder' and name='NeurAI'",
        fields="nextPageToken, files(id, name)"
    ).execute()
    items = results.get('files', [])

    return {'folder': items}
