from logging.config import dictConfig

from fastapi import (
    FastAPI,
    status,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from google.auth.transport.requests import Request

from api.routes import patient, gdrive, users, mri
from api.deps import const
from api.deps.utils import APIException, get_localization_data

log = const.LOGGING()
dictConfig(log.CONFIG)


app = FastAPI(
    title=const.APP_NAME,
    description="Intelligent neurosurgeon assistant",
    docs_url="/docs",
    redoc_url=None,
    contact={
        "name": "Team 23",
        "url": "https://team23-22.studenti.fiit.stuba.sk/neurai",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=const.CORS.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


@app.exception_handler(APIException)
async def api_exception_handler(
        request: Request(),
        exc: APIException,
):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.content,
    )


@app.exception_handler(HTTPException)
async def validation_exception_handler(
        request,
        err: HTTPException
):
    translation = get_localization_data(request)

    if (
        "/google/" in str(request.url)
        and err.status_code == status.HTTP_401_UNAUTHORIZED
    ):

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": translation["drive_authorization_failed"], "type": "google"},
        )
    else:
        return JSONResponse(
            status_code=err.status_code,
            content={"message": translation["user_missing"], "type": "auth"},
        )


app.include_router(users.router)
app.include_router(patient.router)
app.include_router(gdrive.router)
app.include_router(mri.router)
