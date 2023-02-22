import jwt
import base64

from fastapi import (
    FastAPI,
    status,
    Response,
    Depends,
    HTTPException,
    UploadFile,
    File,
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

from nibabel.spatialimages import HeaderDataError
from dicom2nifti.exceptions import ConversionValidationError
from nibabel.wrapstruct import WrapStructError

import app.schema as s
from app import crud, utils, const
from app.utils import APIException
from app.services.smtpService import send_reset_email

api = FastAPI(
    title=const.APP_NAME,
    description="Intelligent neurosurgeon assistant",
    docs_url="/docs",
    redoc_url=None,
    contact={
        "name": "Team 23",
        "url": "https://team23-22.studenti.fiit.stuba.sk/neurai",
    },
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


async def validate_api_token(token: str = Depends(oauth2_scheme)):
    unauthorized = APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": "Invalid credentials", "type": "auth"},
    )
    try:
        payload = jwt.decode(token, const.JWT.SECRET, "HS256")
        if payload["audience"] != "api":
            raise unauthorized
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        raise unauthorized

    return payload["user_id"]


async def validate_reset_token(token: str = Depends(oauth2_scheme)):
    unauthorized = APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": "Invalid credentials", "type": "auth"},
    )
    try:
        payload = jwt.decode(token, const.JWT.SECRET, "HS256")
        if payload["audience"] != "reset-password":
            raise unauthorized
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        raise unauthorized

    return payload["user_id"]


async def validate_drive_token(user_id: int = Depends(validate_api_token)):
    creds = None
    token = None

    refresh_token = (await crud.get_user_by_id(user_id=user_id)).refresh_token

    if refresh_token:
        web_creds = const.GoogleAPI.CREDS["web"]
        creds = Credentials(
            token,
            refresh_token=refresh_token,
            token_uri=web_creds["token_uri"],
            client_id=web_creds["client_id"],
            client_secret=web_creds["client_secret"],
            scopes=const.GoogleAPI.SCOPES,
        )

    try:
        service = build("drive", "v3", credentials=creds)
        results = (
            service.files()
            .list(
                q=const.GoogleAPI.CONTENT_FILTER,
                fields="nextPageToken, files(id, name)",
            )
            .execute()
        )
        items = results.get("files", [])

    except Exception:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": "Google drive authorization failed", "type": "google"},
        )

    # if the NeurAI file doesn't exists create one
    if not items:
        folder_metadata = {
            "name": const.APP_NAME,
            "mimeType": const.GoogleAPI.DRIVE_MIME_TYPE,
        }
        service.files().create(body=folder_metadata, fields="id").execute()

        results = (
            service.files()
            .list(
                q=const.GoogleAPI.CONTENT_FILTER,
                fields="nextPageToken, files(id, name)",
            )
            .execute()
        )
        items = results.get("files", [])

        if not items:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "Folder NeurAI not found"},
            )

    return creds


@api.post("/registration")
async def registration(user: s.UserCredential):

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

    return Response(status_code=status.HTTP_201_CREATED)


@api.post("/login", response_model=s.Login)
async def login(user: s.UserLoginCredentials):
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


@api.post("/reset-password")
async def reset_password(user: s.ResetPassword):
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
    return {"message": "Password reset email sent successfully"}


@api.post("/change-password")
async def change_password(
    data: s.ChangePassword,
    email: str = Depends(validate_reset_token),
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

    return {"message": "Password successfully changed"}


@api.get(
    "/patients",
    dependencies=[Depends(validate_api_token)],
    response_model=List[s.PatientSummary],
)
async def patients_overview():
    return (await crud.get_patients()).all()


@api.get(
    "/google/authorize",
    dependencies=[Depends(validate_api_token)],
    response_model=s.AuthorizationURL,
)
async def drive_authorize():
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        const.GoogleAPI.CREDS_FILE,
        const.GoogleAPI.SCOPES,
        redirect_uri=const.GoogleAPI.REDIRECT_URL,
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt='consent'
    )
    return {"autorization_url": authorization_url}


@api.get("/google/authorize/code", response_model=s.AuthorizationCode)
async def drive_authorize_code(
    code: str, state: str, user_id=Depends(validate_api_token)
):
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        const.GoogleAPI.CREDS_FILE,
        const.GoogleAPI.SCOPES,
        redirect_uri=const.GoogleAPI.REDIRECT_URL,
        state=state,
    )

    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        creds.refresh(Request())

    except Exception:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": "Google drive authorization failed", "type": "google"},
        )

    await crud.update_user_refresh_token(
        user_id=user_id, refresh_token=creds.refresh_token
    )

    service = build("drive", "v3", credentials=creds)
    about = service.about().get(
        fields="user(emailAddress)"
    ).execute()
    email = about["user"].get("emailAddress", "")
    await crud.update_user_associated_drive(user_id=user_id, email=email)

    return {"message": "Google authorization successful"}


@api.get("/google/files", response_model=s.GoogleFiles)
async def drive_get_files(
    creds=Depends(validate_drive_token),
    user_id: int = Depends(validate_api_token),
):
    service = build("drive", "v3", credentials=creds)

    folder_id = utils.get_drive_folder_id(service)
    q = f"'{folder_id}' in parents and trashed=false"

    # list the folder content
    files = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(q=q, fields="nextPageToken, files(id, name)", pageToken=page_token)
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken", None)
        if page_token is None:
            break

    users_files = []
    user = await crud.get_user_by_id(user_id)
    if user.mri_files:
        drive_file_ids = [record["id"] for record in files]
        for file in user.mri_files:
            if file.file_id in drive_file_ids:
                users_files.append(
                    {
                        "id": file.file_id,
                        "name": file.filename,
                        "patient_name": f"{file.patient.forename} {file.patient.surname}",
                        "modified_at": file.modified_at,
                    }
                )

    return {"files": users_files}


@api.post("/patient/{patientID}/files", response_model=s.PatientFiles)
async def upload(
    patientID: str,
    user_id: int = Depends(validate_api_token),
    creds=Depends(validate_drive_token),
    files: List[UploadFile] = File(...),
):

    service = build("drive", "v3", credentials=creds)

    folder_id = utils.get_drive_folder_id(service)

    new_files = []
    dicom_files = []
    nifti_file = None
    try:
        for input_file in files:

            file = utils.MRIFile(filename=input_file.filename, content=input_file.file)

            nifti_file, dicom_files = file.create_valid_series(
                files_length=len(files), nifti_file=nifti_file, dicom_files=dicom_files
            )

        upload_file = utils.MRIFile(filename="", content=None)
        upload_file.prepare_zipped_nifti(nifti_file=nifti_file, dicom_files=dicom_files)
        new_file = upload_file.upload_encrypted(service=service, folder_id=folder_id)
        new_files.append(new_file)

        await crud.create_mri_file(
            filename=new_file["name"],
            file_id=new_file["id"],
            patient_id=patientID,
            user_id=user_id,
        )

    except (HeaderDataError, WrapStructError, ConversionValidationError):
        # Unable to process files for upload
        # For Nifti: invalid header data or wrong block size
        # For Dicom: not enough slices (<4) or inconsistent slice increment
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "File(s) must be valid dicom or nifti format"},
        )
    except APIException as excep:
        raise excep
    except HttpError as e:
        status_code = (
            e.status_code if e.status_code else status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        raise APIException(
            status_code=status_code,
            content={"message": "Google Drive upload failed"},
        )

    return {"mri_files": new_files}


@api.get("/profile", response_model=s.UserProfile)
async def profile(user_id: int = Depends(validate_api_token)):
    user = await crud.get_user_by_id(user_id=user_id)
    authorized_drive = True if user.refresh_token else False

    return {
        "email": user.email,
        "username": user.username,
        "authorized": authorized_drive,
        "authorized_email": user.authorized_email
    }


@api.get("/patient/{patientID}/files", response_model=s.PatientFilesPatientDetail)
async def patient(
    patientID: str,
    creds=Depends(validate_drive_token),
    user_id: int = Depends(validate_api_token),
):
    service = build("drive", "v3", credentials=creds)

    folder_id = utils.get_drive_folder_id(service)

    # list the folder content
    files = utils.get_drive_folder_content(service, folder_id)

    user = await crud.get_user_by_id(user_id)
    mri_files = utils.get_mri_files_per_user(
        user=user, files=files, patient_id=patientID
    )

    patient = await crud.get_patient_by_id(patientID)
    patient_info = {
        "id": patient.id,
        "forename": patient.forename,
        "surname": patient.surname,
        "created_at": patient.created_at,
    }

    return {"patient": patient_info, "mri_files": mri_files}


@api.get("/mri/{file_id}", dependencies=[Depends(validate_api_token)])
async def load_mri_file(file_id: str, creds=Depends(validate_drive_token)):
    service = build("drive", "v3", credentials=creds)
    f_e = utils.MRIFile(filename="", content="")
    f_e.download_decrypted(service, file_id)

    return base64.b64encode(f_e.content)


@api.delete("/google/remove")
async def drive_deauthorize(user_id: int = Depends(validate_api_token)):
    await crud.update_user_refresh_token(user_id=user_id, refresh_token=None)
    await crud.update_user_associated_drive(user_id=user_id, email=None)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
