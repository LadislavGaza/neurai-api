import os
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

    return Response(status_code=status.HTTP_401_UNAUTHORIZED)


@api.get('/test')
async def test(dependencies=[Depends(validate_token)]):
    return {'email': 'abc@abc.sk'}


@api.get('/user')
async def user_resource(user_id: int = Depends(validate_token)):
    return {'user': user_id}
