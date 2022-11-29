from io import BytesIO
from googleapiclient.http import MediaIoBaseUpload

from nibabel import FileHolder, Nifti1Image
from pydicom import dcmread
from pydicom.errors import InvalidDicomError

from buffered_encryption.aesctr import EncryptionIterator, ReadOnlyEncryptedFile

from app import const


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
            Nifti1Image.from_file_map({'header': fh, 'image': fh})
            patient_name = None  # nifti doesn't include patient name

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
            return ef.read()

    def upload_encrypted(self, service, folder_id):
        file_metadata = {
            'name': self.filename,
            'parents': [folder_id]
        }
        media = MediaIoBaseUpload(
            self.encrypt(),
            mimetype='application/octet-stream',
            resumable=True
        )
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,mimeType,createdTime'
        ).execute()
        return {
            'id': uploaded_file.get('id'),
            'name': uploaded_file.get('name'),
            'mimeType': uploaded_file.get('mimeType'),
            'createdTime': uploaded_file.get('createdTime')
        }

    # def download_decrypted(self, service, file_id: int):
    #     file_media = service.files().get_media(fileId=file_id).execute()
    #     f_encrypted = MRIFile(filename=self.filename, content=file_media)
    #     self.content = f_encrypted.decrypt()
