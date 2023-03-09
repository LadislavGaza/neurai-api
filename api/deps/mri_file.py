from io import BytesIO
from typing import List

from dicom2nifti.exceptions import ConversionValidationError
from googleapiclient.http import MediaIoBaseUpload
from fastapi import status

from nibabel import FileHolder, Nifti1Image
from pydicom import dcmread
from pydicom.errors import InvalidDicomError
import dicom2nifti

from buffered_encryption.aesctr import EncryptionIterator, ReadOnlyEncryptedFile

from gzip import compress
import tempfile
from pathlib import Path

from random import choice, choices
from string import ascii_lowercase

from api.deps import const



class MRIFile:
    def __init__(self, filename: str, content):
        self.filename = filename
        self.content = content
        self.is_nifti = False

    def check_file_type(self):
        try:
            dicom_meta = dcmread(self.content)
            patient_name = dicom_meta.PatientName
        except InvalidDicomError as e:
            self.is_nifti = True

        # read nifti file
        if self.is_nifti:
            fh = FileHolder(fileobj=self.content)
            Nifti1Image.from_file_map({"header": fh, "image": fh})
            patient_name = None  # nifti doesn"t include patient name

    def create_valid_series(self, files_length, nifti_file, dicom_files):
        self.check_file_type()

        if self.is_nifti:
            if files_length > 1:
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message": "More than one scanning uploaded"
                    },
                )
            nifti_file = self
        else:
            if nifti_file:
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message": "More than one scanning uploaded"
                    },
                )
            dicom_files.append(self)

        return nifti_file, dicom_files

    def encrypt(self):
        enc_file = EncryptionIterator(
            self.content,
            const.ENC.KEY,
            const.ENC.SIG
        )

        cipher_file = BytesIO()
        for chunk in enc_file:
            cipher_file.write(chunk)
        return cipher_file

    def decrypt(self):
        with BytesIO(self.content) as file_media_bytes:
            file_media_bytes.seek(0)
            ef = ReadOnlyEncryptedFile(
                file_media_bytes,
                const.ENC.KEY,
                const.ENC.SIG
            )
            self.content = ef.read()

    def upload_encrypted(self, service, folder_id):
        file_metadata = {
            "name": self.filename,
            "parents": [folder_id]
        }
        media = MediaIoBaseUpload(
            self.encrypt(),
            mimetype="application/octet-stream",
            resumable=True
        )
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,name,createdTime"
        ).execute()
        return {
            "id": uploaded_file.get("id"),
            "name": uploaded_file.get("name"),
            "created_at": uploaded_file.get("createdTime"),
            "modified_at": uploaded_file.get("createdTime")
        }

    def download_decrypted(self, service, file_id: str):
        self.content = service.files().get_media(fileId=file_id).execute()
        self.decrypt()

    def prepare_zipped_nifti(self, nifti_file, dicom_files):
        self.filename = "".join(choice(ascii_lowercase) for i in range(12))
        if nifti_file:
            nifti_file.content.seek(0)
            self.content = BytesIO(compress(nifti_file.content.read()))
        else:
            temp_directory = tempfile.TemporaryDirectory()
            temp_dir_path = Path(temp_directory.name)

            for dicom_file in dicom_files:
                dicom_file.content.seek(0)
                temp_bytes = temp_dir_path / dicom_file.filename
                temp_bytes.write_bytes(dicom_file.content.read())

            temp_file = tempfile.NamedTemporaryFile(suffix=".nii.gz")
            dicom2nifti.dicom_series_to_nifti(
                temp_dir_path,
                Path(temp_file.name),
                reorient_nifti=True
            )
            temp_file.seek(0)  # this 99% needs to be here

            self.content = BytesIO(temp_file.read())

            temp_directory.cleanup()
            temp_file.close()
        self.is_nifti = True