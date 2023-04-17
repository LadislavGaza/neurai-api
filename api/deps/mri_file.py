import tempfile
from io import BytesIO
from gzip import compress
from pathlib import Path
from typing import List

from fastapi import status
from fastapi import UploadFile
from googleapiclient.http import MediaIoBaseUpload
from buffered_encryption.aesctr import (
    EncryptionIterator, ReadOnlyEncryptedFile
)

from pydicom import dcmread
from pydicom.errors import InvalidDicomError
import dicom2nifti
from dicom2nifti.exceptions import ConversionValidationError
from nibabel import FileHolder, Nifti1Image
from nibabel.spatialimages import HeaderDataError
from nibabel.wrapstruct import WrapStructError


from api.deps import const


class MRIFile:
    def __init__(self, filename: str, content: UploadFile | None = None):
        self.filename = filename
        self.content = content

    def is_nifti(self) -> bool:
        try:
            fh = FileHolder(fileobj=self.content)
            Nifti1Image.from_file_map({"header": fh, "image": fh})
            return True
        except (HeaderDataError, WrapStructError):
            # Invalid header data or wrong block size
            return False

    def is_dicom(self) -> bool:
        try:
            dcmread(self.content)
            return True
        except InvalidDicomError as e:
            return False

    def from_nifti(self) -> bool:
        if not self.is_nifti():
            return False

        self.content.seek(0)
        self.content = BytesIO(compress(nifti.content.read()))
        return True

    def from_dicom(self, dicom_files: List["MRIFile"]) -> bool:
        temp_directory = tempfile.TemporaryDirectory()
        temp_dir_path = Path(temp_directory.name)

        for dicom_file in dicom_files:
            dicom_file.content.seek(0)
            temp_bytes = temp_dir_path / dicom_file.filename
            temp_bytes.write_bytes(dicom_file.content.read())

        temp_file = tempfile.NamedTemporaryFile(suffix=".nii.gz")
        try:
            dicom2nifti.dicom_series_to_nifti(
                temp_dir_path, Path(temp_file.name), reorient_nifti=True
            )
        except ConversionValidationError:
            # Not enough slices (<4) or inconsistent slice increment
            return False

        temp_file.seek(0)
        self.content = BytesIO(temp_file.read())

        temp_directory.cleanup()
        temp_file.close()
        return True

    def encrypt(self) -> BytesIO:
        enc_file = EncryptionIterator(
            self.content,
            const.ENC.KEY,
            const.ENC.SIG
        )

        cipher_file = BytesIO()
        for chunk in enc_file:
            cipher_file.write(chunk)
        return cipher_file

    def decrypt(self) -> BytesIO:
        with BytesIO(self.content) as file_media_bytes:
            file_media_bytes.seek(0)
            ef = ReadOnlyEncryptedFile(
                file_media_bytes,
                const.ENC.KEY,
                const.ENC.SIG
            )
            return ef.read()

    def upload_encrypted(self, service, folder_id) -> dict:
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
            "modified_at": uploaded_file.get("createdTime"),
            "content": self.content
        }

    def download_decrypted(self, service, file_id: str):
        self.content = service.files().get_media(fileId=file_id).execute()
        self.content = self.decrypt()
