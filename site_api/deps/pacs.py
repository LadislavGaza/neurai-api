import os
import sys
from itertools import groupby
from typing import List
from datetime import datetime, date, time

from pynetdicom import (
    AE,
    build_role,
    evt,
    StoragePresentationContexts,
    debug_logger
)
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelGet,
    PatientStudyOnlyQueryRetrieveInformationModelGet,
    EncapsulatedSTLStorage,
    EncapsulatedOBJStorage,
    EncapsulatedMTLStorage,
)
from pydicom.dataset import Dataset
from pydicom.filewriter import write_file_meta_info
from pynetdicom.dsutils import encode
# DO NOT DELETE - DICOM C-GET WILL FAIL!!!
from pydicom.uid import DeflatedExplicitVRLittleEndian

from site_api.deps import utils
from site_api.deps.const import SOP_CLASS_PREFIXES


class PACSClient:

    PATIENT_METADATA = {
        "PatientID": "id", 
        "PatientName": "name",
        "PatientBirthDate": "birth_date"
    }
    STUDY_METADATA = {
        "StudyInstanceUID": "study_uid",
        "StudyDescription": "name",
        "StudyDate": "created_at_date",
        "StudyTime": "created_at_time"
    }
    SERIES_METADATA = {
        "SeriesInstanceUID": "series_uid",
        "SeriesDescription": "description",
        "ProtocolName": "filename",
        "SeriesDate": "created_at_date",
        "SeriesTime": "created_at_time"
       
    }
    METADATA = PATIENT_METADATA.keys() | STUDY_METADATA.keys() | SERIES_METADATA.keys()

    DATE_FIELDS = {"PatientBirthDate", "StudyDate", "SeriesDate"}
    TIME_FIELDS = {"StudyTime", "SeriesTime"}

    def __init__(self, ip: str, port: int, ae_title: str):
        debug_logger()
        self.ip = ip
        self.port = port
        self.ae_title = ae_title
        self.ae = AE()

    def search_studies_by_patient(self, query: dict):
        self.ae = AE()
        self.ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
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
        assoc.release()

        return self._dicom_series_group_by_patient(results)

    def search_patients(self, query: dict):
        self.ae = AE()
        self.ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ds = Dataset()
        ds.QueryRetrieveLevel = "STUDY"

        query['PatientName'] = f"*{query.get('PatientName', '')}*"
        for field in self.PATIENT_METADATA.keys():
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
                for field in self.PATIENT_METADATA.keys()
                if hasattr(identifier, field)
            }
            results.append(item)
        assoc.release()
        results_renamed = []
        for patient in results:
            patient_mapped = utils.rename_dict_keys(
                patient,
                self.PATIENT_METADATA
            )
            if patient_mapped['birth_date']:
                patient_mapped['birth_date'] = datetime.strptime(patient_mapped['birth_date'], "%Y%m%d").strftime("%d.%m.%Y")
            else:
                patient_mapped['birth_date'] = None
            results_renamed.append(patient_mapped)

        return results_renamed

    def download(self, series_uid: str, folder: str) -> bool:
        self.ae = AE()
        ext_neg = self._export_role_selection()
        query_model = StudyRootQueryRetrieveInformationModelGet

        ds = Dataset()
        ds.QueryRetrieveLevel = "SERIES"
        ds.PatientID = ""
        ds.StudyInstanceUID = ""
        ds.SeriesInstanceUID = series_uid

        # Request association with remote
        assoc = self.ae.associate(
            self.ip,
            self.port,
            ae_title=self.ae_title,
            ext_neg=ext_neg,
            evt_handlers=[(evt.EVT_C_STORE, self._handle_store, [folder])],
            max_pdu=16382
        )
        if not assoc.is_established:
            return False

        responses = assoc.send_c_get(ds, query_model)
        for (status, rsp_identifier) in responses:
            if status and status.Status in [0xFF00, 0xFF01]:
                # to be added processing of response?
                pass

        assoc.release()
        return True

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
                study = self._merge_created_timestamp(study)

                study["mri_files"] = []
                for series in st_group:
                    image = utils.filter_dict_keys(series, self.SERIES_METADATA.keys())
                    image = utils.rename_dict_keys(image, self.SERIES_METADATA)
                    image = self._merge_created_timestamp(image)
                    study["mri_files"].append(image)

                patient["screenings"].append(study)

            patients.append(patient)

        return patients


    def _merge_created_timestamp(self, element):
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

    def _export_role_selection(self) -> list:
        # Exclude these SOP Classes
        _exclusion = [
            EncapsulatedSTLStorage,
            EncapsulatedOBJStorage,
            EncapsulatedMTLStorage,
        ]
        store_contexts = [
            cx for cx in StoragePresentationContexts 
            if cx.abstract_syntax not in _exclusion
        ]

        # Extended Negotiation - SCP/SCU Role Selection
        ext_neg = []
        self.ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        self.ae.add_requested_context(StudyRootQueryRetrieveInformationModelGet)
        self.ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelGet)
        for cx in store_contexts:
            self.ae.add_requested_context(cx.abstract_syntax)
            ext_neg.append(build_role(cx.abstract_syntax, scp_role=True))

        return ext_neg


    def _dicom_parse_filename(self, ds):
        # Because pydicom uses deferred reads for its decoding, decoding errors
        # are hidden until encountered by accessing a faulty element
        try:
            sop_class = ds.SOPClassUID
            sop_instance = ds.SOPInstanceUID
        except Exception as exc:
            # Unable to decode dataset
            return 0xC210

        try:
            # Get the elements we need
            mode_prefix = SOP_CLASS_PREFIXES[sop_class][0]
        except KeyError:
            mode_prefix = "UN"

        filename = f"{mode_prefix}.{sop_instance}"
        return filename

    def _handle_store(self, event, output_directory):
        # if args.ignore:
        #    return 0x0000
        try:
            ds = event.dataset
            # Remove any Group 0x0002 elements that may have been included
            ds = ds[0x00030000:]
        except Exception as exc:
            # Unable to decode dataset
            return 0x210
        # Add the file meta information elements
        ds.file_meta = event.file_meta


        filename = self._dicom_parse_filename(ds)

        status_ds = Dataset()
        status_ds.Status = 0x0000

        # Try to save to output-directory
        if output_directory is not None:
            filename = os.path.join(output_directory, filename)
            try:
                os.makedirs(output_directory, exist_ok=True)
            except Exception as exc:
                # Failed - Out of Resources - IOError
                status_ds.Status = 0xA700
                return status_ds

        try:
            if event.context.transfer_syntax == DeflatedExplicitVRLittleEndian:
                # Workaround for pydicom issue #1086
                with open(filename, "wb") as f:
                    f.write(b"\x00" * 128)
                    f.write(b"DICM")
                    write_file_meta_info(f, event.file_meta)
                    f.write(encode(ds, False, True, True))
            else:
                # We use `write_like_original=False` to ensure that a compliant
                #   File Meta Information Header is written
                ds.save_as(filename, write_like_original=False)

            status_ds.Status = 0x0000  # Success
        except IOError as exc:
            # Failed - Out of Resources - IOError
            status_ds.Status = 0xA700
        except Exception as exc:
            # Failed - Out of Resources - Miscellaneous error
            status_ds.Status = 0xA701

        return status_ds