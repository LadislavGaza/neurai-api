from fastapi import (
    FastAPI,
    status,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from google.auth.transport.requests import Request

from app.routes import patient, gdrive, users, mri
from app.static import const
from app.utils import APIException


api = FastAPI(
    title=const.APP_NAME,
    description="Intelligent neurosurgeon assistant",
    docs_url="/docs",
    redoc_url=None,
    contact={
        "name": "Team 23",
        "url": "https://team23-22.studenti.fiit.stuba.sk/neurai",
    }
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=const.CORS.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


@api.exception_handler(APIException)
async def api_exception_handler(request: Request(), exc: APIException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.content,
    )


@api.exception_handler(HTTPException)
async def validation_exception_handler(request, err: HTTPException):

    if (
        "/google/" in str(request.url)
        and err.status_code == status.HTTP_401_UNAUTHORIZED
    ):

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": "Authentification failed", "type": "auth"},
        )
    else:
        return JSONResponse(
            status_code=err.status_code,
            content={"message": "Exception", "detail": err.detail},
        )


api.include_router(users.router)
api.include_router(patient.router)
api.include_router(gdrive.router)
api.include_router(mri.router)
