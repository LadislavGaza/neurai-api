import logging
from logging.config import dictConfig

from fastapi import (
    FastAPI,
    Depends,
    status,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer


from site_api import const


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


async def get_logger():
    return logging.getLogger(const.APP_NAME)


async def validate_api_token(
    token: str = Depends(oauth2_scheme),
    log = Depends(get_logger)
):
    unauthorized = APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": "Invalid credentials", "type": "auth"},
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


@app.get("/")
async def patients_overview():
    return {"test": "Hello world!"}
