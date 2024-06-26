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

import api.deps.schema as s
from api.deps import const
from api.db import crud
from api.deps.auth import (
    validate_reset_token, validate_api_token, get_logger
)
from api.services.smtp_service import send_reset_email
from api.deps.utils import APIException, get_localization_data


router = APIRouter(
    tags=["user"],
    responses={404: {"description": "Not found"}},
)


@router.post("/registration")
async def registration(
        user: s.UserCredential,
        log=Depends(get_logger),
        translation=Depends(get_localization_data)
):
    if (
        len(user.password) < 8
        or user.password.lower() == user.password
        or user.password.isalpha()
        or user.email.split("@")[0] in user.password
    ):
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": translation["invalid_password"]},
        )
    if not user.username:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": translation["username_missing"]},
        )
    try:
        user.password = argon2.hash(user.password)
        await crud.create_user(user)

    except IntegrityError:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": translation["username_taken"]}
        )

    log.info(
        f"A new user {user.username} has registered.",
        extra={"topic": "REGISTRATION"}
    )

    return Response(status_code=status.HTTP_201_CREATED)


@router.post("/login", response_model=s.Login)
async def login(
        user: s.UserLoginCredentials,
        log=Depends(get_logger),
        translation=Depends(get_localization_data)

):
    account = await crud.get_user(user)

    valid_credentials = account is not None and argon2.verify(
        user.password, account.password
    )

    if valid_credentials:
        expiration = (
            datetime.utcnow() +
            timedelta(seconds=const.JWT.EXPIRATION_SECONDS)
        )
        payload = {
            "user_id": account.id,
            "username": account.username,
            "audience": "api",
            "exp": expiration
        }
        token = jwt.encode(payload, const.JWT.SECRET, "HS256")

        authorized_drive = True if account.refresh_token else False
        authorized_email = account.authorized_email if account.authorized_email else ""

        log.info(
            f"User '{account.username}' has logged in.",
            extra={"topic": "LOGIN"}
        )

        return {
            "token": token,
            "email": account.email,
            "username": account.username,
            "authorized": authorized_drive,
            "authorized_email": authorized_email
        }

    if account is not None:
        log.info(
            f"User '{account.username}' failed to log in "
            f"due to incorrect credentials.",
            extra={"topic": "LOGIN"}
        )

    raise APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": translation['wrong_login'], "type": "auth"},
    )


@router.post("/reset-password")
async def reset_password(
        user: s.ResetPassword,
        log=Depends(get_logger),
        translation=Depends(get_localization_data)
):
    expiration = (
        datetime.utcnow() +
        timedelta(seconds=const.JWT.EXPIRATION_PASSWORD_RESET)
    )
    payload = {
        "audience": "reset-password",
        "user_id": user.email,
        "exp": expiration,
    }
    token = jwt.encode(payload, const.JWT.SECRET, "HS256")
    send_reset_email(to=user.email, token=token)

    account = await crud.get_user_by_mail(user.email)
    log.info(
        f"User '{account.username}' requested password reset.",
        extra={"topic": "REGISTRATION"}
    )

    return {"message": translation["reset_password"]}


@router.post("/change-password")
async def change_password(
    data: s.ChangePassword,
    email: str = Depends(validate_reset_token),
    log=Depends(get_logger),
    translation=Depends(get_localization_data)
):
    user = await crud.get_user_by_mail(email)
    if not user:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["user_missing"]}
        )
    if (
        len(data.password) < 8
        or data.password.lower() == data.password
        or data.password.isalpha()
        or user.email.split("@")[0] in data.password
    ):
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": translation["invalid_password"]}
        )
    password_hash = argon2.hash(data.password)
    await crud.update_user_password(user_id=user.id, password=password_hash)

    log.info(
        f"User '{user.username}' changed password.",
        extra={"topic": "REGISTRATION"}
    )

    return {"message": translation["password_changed"]}


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
