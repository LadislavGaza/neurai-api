from io import BytesIO
from googleapiclient.http import MediaIoBaseUpload

from nibabel import FileHolder, Nifti1Image
from pydicom import dcmread
from pydicom.errors import InvalidDicomError

from buffered_encryption.aesctr import EncryptionIterator

from app import const, crud


async def upload_file(service, folder_id, file_to_upload, patient_id, user_id):
    try:
        is_nifti = False
        dicom_meta = dcmread(file_to_upload.file)
        patient_name = dicom_meta.PatientName
    except InvalidDicomError as e:
        is_nifti = True

    # read nifti file
    if is_nifti:
        fh = FileHolder(fileobj=file_to_upload.file)
        Nifti1Image.from_file_map({'header': fh, 'image': fh})
        patient_name = None  # nifti doesn't include patient name

    await crud.create_mri_file(
        filename=file_to_upload.filename,
        patient_id=patient_id,
        user_id=user_id
    )

    await file_to_upload.seek(0)  # this 100% needs to be here

    cipher_file = encrypt_file(file_to_upload.file)

    file_metadata = {
        'name': file_to_upload.filename,
        'parents': [folder_id]
    }
    media = MediaIoBaseUpload(
        cipher_file,
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


def encrypt_file(file):
    enc_file = EncryptionIterator(
        file,
        const.ENC.KEY,
        const.ENC.SIG
    )

    cipher_file = BytesIO()
    for chunk in enc_file:
        cipher_file.write(chunk)
    return cipher_file
