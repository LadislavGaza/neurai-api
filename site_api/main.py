import os
import json
import logging
import tempfile
from pathlib import Path
from logging.config import dictConfig
from typing import List

from fastapi import (
    FastAPI,
    Header,
    Depends,
    status,
    HTTPException,
    BackgroundTasks
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
from site_api.deps.utils import get_localization_data
from site_api.deps.pacs import PACSClient


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
language_fallback = "sk"
app_languages = ["sk", "en"]


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
async def validation_exception_handler(
        request,
        err: HTTPException,
):
    translation = await get_localization_data(request)

    return JSONResponse(
        status_code=err.status_code,
        content={"message": translation["wrong_login"], "type": "auth"},
    )


async def get_logger():
    return logging.getLogger(const.APP_NAME)


async def get_patient(patient_id, translation=Depends(get_localization_data)):
    patient = await crud.get_patient_by_id(patient_id)
    if patient is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": translation["patient_not_exists"]},
        )

    return patient


async def add_patient(patient: s.Patient, authorization: str):
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


def api_get_unsafe(path, auth_header):
    return requests.get(
        urljoin(const.COMMON_API_URL, path), 
        headers={"Authorization": auth_header}
    )


@request_handle_errors
def api_get(path, auth_header):
    return api_get_unsafe(path, auth_header)


@request_handle_errors
def api_post(path, data, auth_header):
    return requests.post(
        urljoin(const.COMMON_API_URL, path), 
        data=data,
        headers={"Authorization": auth_header}
    )


@request_handle_errors
def api_upload(path, files, auth_header):
    return requests.post(
        urljoin(const.COMMON_API_URL, path), 
        files=files,
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
        "surname": "",
        "birth_date": None
    }

    patients = (await crud.get_patients()).all()
    patients = [
        (s.PatientDetail.from_orm(patient).dict() |
         anonymous.get(patient.id, unknown_patient)) 
        for patient in patients
    ]
    return patients


@app.post("/patients", response_model=s.Patient)
async def patient_create(
    patient: s.NewPatient,
    authorization: str | None = Header(default=None)
):
    new_patient = await add_patient(patient, authorization)
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


@app.get("/pacs/patients", response_model=List[s.HospitalStoragePatient])
async def pacs_search_patients(
    search: s.HospitalStorageSearch = Depends()
):
    pacs = PACSClient(const.PACS.IP, const.PACS.PORT, const.PACS.AE_TITLE)
    results = pacs.search_patients(vars(search))

    return results


@app.get("/pacs/studies", response_model=List[s.HospitalScreening])
async def pacs_search_studies(
    patient_id: str,
    authorization: str | None = Header(default=None)
):
    response = api_get(f"/patient/{patient_id}/study", authorization)
    existing_studies = response.json()

    pacs = PACSClient(const.PACS.IP, const.PACS.PORT, const.PACS.AE_TITLE)
    search = {"PatientID": patient_id}
    results = pacs.search_studies_by_patient(search, existing_studies)

    return results


@app.post("/pacs/mri")
async def pacs_export(
    mri_file_uids: List[str],
    authorization: str | None = Header(default=None)
):
    pacs = PACSClient(const.PACS.IP, const.PACS.PORT, const.PACS.AE_TITLE)

    for uid in mri_file_uids:
        temp_directory = tempfile.TemporaryDirectory()
        temp_dir_path = Path(temp_directory.name)  
        metadata = pacs.download(uid, temp_dir_path)

        print("PatientID", metadata["PatientID"], flush=True)
        print("StudyInstanceUID", metadata["StudyInstanceUID"], flush=True)
        print("SeriesInstanceUID", metadata["SeriesInstanceUID"], flush=True)

        # Import patient and skip if exists
        patient_id = metadata["PatientID"]
        resp = api_get_unsafe(f"/patient/{patient_id}", authorization)
        if resp.status_code == status.HTTP_404_NOT_FOUND:
            # Patient with ID does not exist, you have to create one
            new_patient = s.Patient(
                id=patient_id, 
                forename="",
                surname=metadata["PatientName"],
                birth_date=metadata["PatientBirthDate"]
            )
            new_patient = await add_patient(new_patient, authorization)
    
        # Import screening (study in DICOM terminology) and skip if exists
        resp = api_get(f"/patient/{patient_id}/screening", authorization)
        studies_uids = {
            s["study_uid"]: s["id"]
            for s in response.json()["screenings"] 
            if s["study_uid"]
        }
        print("StudyUIDs", studies_uids, flush=True)
        print(study_uid not in studies_uids.keys())

        study_uid = metadata["StudyInstanceUID"]
        if study_uid not in studies_uids.keys():
            # Screening with UID does not exist, you have to create one
            new_screening = {"uid": study_uid}
            response = api_post(
                f"/patient/{patient_id}/screening", 
                new_screening.json(),
                authorization
            )
            screening_id = response.json()["id"]
        else:
            screening_id = studies_uids[study_uid]

        # Check if series already exists, if it does skip import
        resp = api_get(f"/screening/{screening_id}/files", authorization)
        series_uids = set([
            s["series_uid"] for s in response.json()["mri_files"] 
        ])
        series_uid = metadata["SeriesInstanceUID"]
        if series_uid not in series_uids:
            files = [open(fname, 'rb') for fname in os.listdir(temp_dir_path)]
            response = api_post(
                f"/screening/{screening_id}/files/{series_uid}", 
                files, 
                authorization
            )
        else:
            pass # MR-ko už existuje
        
        temp_directory.cleanup()
