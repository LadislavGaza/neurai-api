from itertools import groupby
from datetime import datetime, date, time
from pydicom.dataset import Dataset

from pynetdicom import AE, debug_logger
from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelFind

from site_api.deps import utils


class PACSClient:

    PATIENT_METADATA = {
        "PatientID": "id", 
        "PatientName": "name",
        "PatientBirthDate": "birth_date"
    }
    STUDY_METADATA = {
        "StudyInstanceUID": "uid",
        "StudyDescription": "description",
        "StudyDate": "created_at_date",
        "StudyTime": "created_at_time"
    }
    SERIES_METADATA = {
        "SeriesInstanceUID": "uid", 
        "SeriesDescription": "description",
        "ProtocolName": "filename",
        "SeriesDate": "created_at_date",
        "SeriesTime": "created_at_time"
       
    }
    METADATA = PATIENT_METADATA.keys() | STUDY_METADATA.keys() | SERIES_METADATA.keys()

    DATE_FIELDS = {"PatientBirthDate", "StudyDate", "SeriesDate"}
    TIME_FIELDS = {"StudyTime", "SeriesTime"}

     
    def __init__(self, ip: str, port: int, ae_title: str):
        self.ip = ip
        self.port = port
        self.ae_title = ae_title

        self.ae = AE()
        self.ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)

    def search(self, query: dict):
        ds = Dataset()
        ds.QueryRetrieveLevel = "SERIES"
        ds.Modality = "MR"

        for field in self.METADATA:
            setattr(ds, field, query.get(field, ""))

        results = []
        assoc = self.ae.associate(self.ip, self.port, ae_title=self.ae_title)
        if not assoc.is_established:
            return results
 
        responses = assoc.send_c_find(ds, PatientRootQueryRetrieveInformationModelFind)
        for (status, identifier) in responses:
            if identifier is None:
                continue

            item = {
                field: self._attribute_parse(
                    field, getattr(identifier, field)
                )
                for field in self.METADATA
                if hasattr(identifier, field)
            }
            results.append(item)

        return self._dicom_series_group_by_patient(results)
 

    def _dicom_series_group_by_patient(self, series):
        # Reorganize hierarchically, IDs are assumed to be required fields
        PATIENT_ID = "PatientID"
        STUDY_ID = "StudyInstanceUID"

        patients = []
        series = sorted(series, key=lambda x: x[PATIENT_ID])

        for p_key, p_group in groupby(series):
            patient = utils.filter_dict_keys(p_key, self.PATIENT_METADATA.keys())
            patient = utils.rename_dict_keys(patient, self.PATIENT_METADATA)

            patient["screenings"] = []
            p_group = sorted(p_group, key=lambda x: x[STUDY_ID])

            for st_key, st_group in groupby(p_group):
                study = utils.filter_dict_keys(st_key, self.STUDY_METADATA.keys())
                study = utils.rename_dict_keys(study, self.STUDY_METADATA)
                study = self.merge_created_timestamp(study)

                study["mri_files"] = []
                for series in st_group:
                    image = utils.filter_dict_keys(series, self.SERIES_METADATA.keys())
                    image = utils.rename_dict_keys(image, self.SERIES_METADATA)
                    image = self.merge_created_timestamp(image)
                    study["mri_files"].append(image)

                patient["screenings"].append(study)

            patients.append(patient)

        return patients


    def merge_created_timestamp(self, element):
        if isinstance(element.get("created_at_date"), date):
            element["created_at"] = datetime.combine(
                element.get("created_at_date", date.today()), 
                element.get("created_at_time", time())
            )

        element.pop("created_at_date", None)
        element.pop("created_at_time", None)
        return element

    def _attribute_parse(self, key: str, value: str):
        if value and key in self.DATE_FIELDS:
            value = datetime.strptime(value, "%Y%m%d").date()
        elif value and key in self.TIME_FIELDS:
            value = datetime.strptime(value, "%H%M%S").time()
        else:
            value = str(value).strip()

        return value