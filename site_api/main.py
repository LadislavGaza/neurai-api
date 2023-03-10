import logging
from logging.config import dictConfig
from typing import List

from fastapi import (
    FastAPI,
    Header,
    Depends,
    status,
    HTTPException
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer

import requests
from requests.compat import urljoin
from requests.exceptions import (
    RequestException, 
    InvalidJSONError
)

from site_api.deps import const
from site_api.db import crud
import site_api.deps.schema as s


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


class APIException(Exception):
    status_code = None
    content = None

    def __init__(self, content, status_code: int):
        self.content = content
        self.status_code = status_code


@app.exception_handler(APIException)
async def api_exception_handler(request, exc: APIException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.content,
    )


@app.exception_handler(HTTPException)
async def validation_exception_handler(request, err: HTTPException):
    return JSONResponse(
        status_code=err.status_code,
        content={"message": "Exception", "detail": err.detail},
    )


async def get_logger():
    return logging.getLogger(const.APP_NAME)


def request_handle_errors(request):
    def wrapper(*args, **kwargs):
        try:
            response = request(*args, **kwargs)
            if not response.ok:
                raise APIException(
                    status_code=response.status_code,
                    content=response.json()
                )
            else:
                return response
                
        except (RequestException, ConnectionError, InvalidJSONError) as err:
            raise APIException(
                status_code=response.status_code,
                content={"message": "Exception", "detail": err}
            )

    return wrapper


@request_handle_errors
def api_get(path, auth_header):
    return requests.get(
        urljoin(const.COMMON_API_URL, path), 
        headers={"Authorization": auth_header}
    )


@request_handle_errors
def api_post(path, data, auth_header):
    return requests.get(
        urljoin(const.COMMON_API_URL, path), 
        headers={"Authorization": auth_header}
    )
 

# Common API môže mať do budúcna endpoint validate-token
# Token sa bude validovať len na Common API (lebo vždy mergujeme slovníky)

@app.get("/patients", response_model=List[s.Patient])
async def patients_overview(
    authorization: str | None = Header(default=None)
):
    response = api_get("/patients", authorization)
    anonyms = {anonym["id"]: anonym for anonym in response.json()}

    patients = (await crud.get_patients()).all()
    patients = [
        s.PatientAnonym.from_orm(patient).dict() | anonyms[patient.id] 
        for patient in patients
    ]
    return patients


@app.post("/patients", response_model=s.Patient)
async def add_patient(
    patient: s.NewPatient,
    authorization: str | None = Header(default=None)
):
    response = api_post("/patients", patient.dict(), authorization)
    await crud.create_patient(patient=patient)

    response = api_get("/patient/{patient_id}", authorization)
    patient = await crud.get_patient_by_id(patient_id)

    new_patient = response.json() | s.PatientAnonym.from_orm(patient).dict()
    return new_patient


@app.get(
    "/patient/{patient_id}/files",
    response_model=s.PatientFilesPatientDetail
)
async def patient(
    patient_id: str,
    authorization: str | None = Header(default=None)
):
    response = api_get("/patient/{patient_id}", authorization)
    patient = await crud.get_patient_by_id(patient_id)

    new_patient = response.json() | s.PatientAnonym.from_orm(patient).dict()
    return new_patient
