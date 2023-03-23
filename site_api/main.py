import json
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


async def get_patient(patient_id):
    patient = await crud.get_patient_by_id(patient_id)
    if patient is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Patient does not exist"},
        )

    return patient


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
                content={"message": "Exception", "detail": str(err)}
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
    return requests.post(
        urljoin(const.COMMON_API_URL, path), 
        data=data,
        headers={"Authorization": auth_header}
    )
 

@app.get("/patients", response_model=List[s.Patient])
async def patients_overview(
    authorization: str | None = Header(default=None)
):
    response = api_get("/patients", authorization)
    anonymous = {p["id"]: p for p in response.json()}
    unknown_patient = {
        "forename": "",
        "surname": ""
    }

    patients = (await crud.get_patients()).all()
    patients = [
        (s.PatientDetail.from_orm(patient).dict() |
         anonymous.get(patient.id, unknown_patient)) 
        for patient in patients
    ]
    return patients


@app.post("/patients", response_model=s.Patient)
async def add_patient(
    patient: s.NewPatient,
    authorization: str | None = Header(default=None)
):
    anonymous = patient.copy()
    anonymous.forename = ""
    anonymous.surname = ""

    response = api_post("/patients", anonymous.json(), authorization)
    # ID can be generated by api when empty
    new_anonymous = response.json()
    patient.id = new_anonymous["id"]

    await crud.create_patient(patient=patient)

    response = api_get(f"/patient/{patient.id}", authorization)
    new_patient = await get_patient(patient.id)

    new_patient = (
        response.json() |
        s.PatientDetail.from_orm(new_patient).dict()
    )
    return new_patient


@app.get("/patient/{patient_id}", response_model=s.Patient)
async def patient(
    patient_id: str,
    authorization: str | None = Header(default=None)
):
    response = api_get(f"/patient/{patient_id}", authorization)
    patient = await get_patient(patient_id)

    new_patient = (
        response.json() | 
        s.PatientDetail.from_orm(patient).dict()
    )
    return new_patient


@app.get(
    "/patient/{patient_id}/files",
    response_model=s.PatientFilesPatientDetail
)
async def patient_files(
    patient_id: str,
    authorization: str | None = Header(default=None)
):
    response = api_get(f"/patient/{patient_id}/files", authorization)
    patient = await get_patient(patient_id)
    response_files = response.json()

    response_files["patient"] = (
        response_files.get("patient", []) | 
        s.PatientDetail.from_orm(patient).dict()
    )
    return response_files


@app.get(
    "/patient/{patient_id}/screening",
    response_model=s.PatientDetailScreenings
)
async def patient_screenings(
    patient_id: str,
    authorization: str | None = Header(default=None)
):
    response = api_get(f"/patient/{patient_id}/screening", authorization)
    patient = await get_patient(patient_id)
    response_files = response.json()

    response_files["patient"] = (
        response_files.get("patient", []) | 
        s.PatientDetail.from_orm(patient).dict()
    )
    return response_files
