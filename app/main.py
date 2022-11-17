import jwt
from fastapi import (
    FastAPI,
    status,
    Response,
    Depends,
    HTTPException
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse

import google_auth_oauthlib.flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from sqlalchemy.exc import IntegrityError
from passlib.hash import argon2
from datetime import datetime, timedelta

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
async def unicorn_exception_handler(request: Request(), exc: APIException):
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
        content={
            'message': 'Invalid credentials',
            'type': 'auth',
            'headers': {'WWW-Authenticate': 'Bearer'}},
        status_code=401
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

    return {'creds': creds.to_json()}


@api.get('/google/get/files', dependencies=[Depends(validate_token)])
async def drive_get_files(creds=Depends(validate_drive_token)):

    service = build('drive', 'v3', credentials=creds)

    results = service.files().list(
        q=const.GoogleAPI.CONTENT_FILTER,
        fields="nextPageToken, files(id, name)"
    ).execute()
    items = results.get('files', [])

    return {'folder': items}


@api.get('/test', dependencies=[Depends(validate_token)])
async def test():
    return {'email': 'abc@abc.sk'}


@api.get('/user')
async def user_resource(user_id: int = Depends(validate_token)):
    return {'user': user_id}
