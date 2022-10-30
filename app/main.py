from fastapi import (
    FastAPI,
    status,
    HTTPException,
    Response
)
from sqlalchemy.exc import IntegrityError

import app.model as m
import app.schema as s
from app import crud


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


@api.post('/registration')
async def registration(user: s.UserCreate,
                       status_code=status.HTTP_201_CREATED):
    try:
        await crud.create_user(user)
    except IntegrityError:
        raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='User with this name already exists'
        )

    return Response(status_code=status.HTTP_201_CREATED)
