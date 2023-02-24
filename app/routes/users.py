import jwt

from fastapi import (
    APIRouter,
    status,
    Response,
    Depends
)
from sqlalchemy.exc import IntegrityError

from passlib.hash import argon2
from datetime import datetime, timedelta

import app.schema as s
from app.static import const
from app.db import crud
from app.dependencies import (
    validate_reset_token, validate_api_token, get_logger
)
from app.services.smtpService import send_reset_email
from app.utils import APIException


router = APIRouter(
    tags=["user"],
    responses={404: {"description": "Not found"}},
)


@router.post("/registration")
async def registration(user: s.UserCredential, log = Depends(get_logger)):

    if (
        len(user.password) < 8
        or user.password.lower() == user.password
        or user.password.isalpha()
        or user.email.split("@")[0] in user.password
    ):
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": "Password invalid format"},
        )
    if not user.username:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": "Username field is missing"},
        )
    try:
        user.password = argon2.hash(user.password)
        await crud.create_user(user)

    except IntegrityError:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": "User with this name already exists"},
        )

    log.info(
        f"A new user {user.username} has registered.",
        extra={"topic": "REGISTRATION"}
    )

    return Response(status_code=status.HTTP_201_CREATED)


@router.post("/login", response_model=s.Login)
async def login(user: s.UserLoginCredentials, log = Depends(get_logger)):
    account = await crud.get_user(user)

    valid_credentials = account is not None and argon2.verify(
        user.password, account.password
    )

    if valid_credentials:
        expiration = datetime.utcnow() + timedelta(seconds=const.JWT.EXPIRATION_SECONDS)
        payload = {"user_id": account.id, "audience": "api", "exp": expiration}
        token = jwt.encode(payload, const.JWT.SECRET, "HS256")
        authorized_drive = True if account.refresh_token else False
        authorized_email = account.authorized_email if account.authorized_email else ""

        log.info(
            f"User {account.username} has logged in.",
            extra={"topic": "LOGIN"}
        )

        return {
            "token": token,
            "email": account.email,
            "username": account.username,
            "authorized": authorized_drive,
            "authorized_email": authorized_email
        }

    raise APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": "Wrong email or password", "type": "auth"},
    )


@router.post("/reset-password")
async def reset_password(user: s.ResetPassword, log = Depends(get_logger)):
    expiration = datetime.utcnow() + timedelta(
        seconds=const.JWT.EXPIRATION_PASSWORD_RESET
    )
    payload = {
        "audience": "reset-password",
        "user_id": user.email,
        "exp": expiration,
    }
    token = jwt.encode(payload, const.JWT.SECRET, "HS256")
    send_reset_email(to=user.email, token=token)

    log.info(
        f"User with e-mail {user.email} requested password reset.",
        extra={"topic": "REGISTRATION"}
    )

    return {"message": "Password reset email sent successfully"}


@router.post("/change-password")
async def change_password(
    data: s.ChangePassword,
    email: str = Depends(validate_reset_token),
    log = Depends(get_logger)
):
    user = await crud.get_user_by_mail(email)
    if not user:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "User not found"},
        )
    if (
        len(data.password) < 8
        or data.password.lower() == data.password
        or data.password.isalpha()
        or user.email.split("@")[0] in data.password
    ):
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": "Password invalid format"},
        )
    password_hash = argon2.hash(data.password)
    await crud.update_user_password(user_id=user.id, password=password_hash)

    log.info(
        f"User {user.username} changed password.",
        extra={"topic": "REGISTRATION"}
    )

    return {"message": "Password successfully changed"}


@router.get("/profile", response_model=s.UserProfile)
async def profile(user_id: int = Depends(validate_api_token)):
    user = await crud.get_user_by_id(user_id=user_id)
    authorized_drive = True if user.refresh_token else False

    return {
        "email": user.email,
        "username": user.username,
        "authorized": authorized_drive,
        "authorized_email": user.authorized_email
    }
