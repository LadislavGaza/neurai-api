import os
import os.path
import tempfile
from io import BytesIO
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.ai.ml import MLClient, Input
from azure.ai.ml.entities import Data
from azure.ai.ml.constants import AssetTypes
from azure.core.exceptions import ClientAuthenticationError

from api.deps import const
from api.deps.mri_file import MRIFile


class InferenceAuthException(Exception):
    pass


class MLInference:
    FILE_FORMAT = ".nii.gz"

    def __init__(self):
        self.ml = MLClient(
            DefaultAzureCredential(
                exclude_environment_credential=True,
                exclude_managed_identity_credential=True,
                exclude_shared_token_cache_credential=True
            ),
            const.AZUREML.SUBSCRIPTION_ID,
            const.AZUREML.RESOURCE_GROUP,
            const.AZUREML.WORKSPACE
        )
        self.endpoint = const.AZUREML.ENDPOINT

    def launch(self, mri: BytesIO) -> str:
        with tempfile.NamedTemporaryFile(suffix=self.FILE_FORMAT) as nifti:
            path = Path(nifti.name)
            nifti.write(mri.getbuffer())

            source = Data(path=path, type=AssetTypes.URI_FILE)

            try:
                # Upload source NIfTI file to Azure
                data = self.ml.data.create_or_update(source)
                input_file = Input(type=AssetTypes.URI_FILE, path=data.id)

                # Run inference on uploaded file
                job = self.ml.batch_endpoints.invoke(
                    endpoint_name=self.endpoint,
                    inputs={"file": input_file}
                )
            except ClientAuthenticationError:
                raise InferenceAuthException()  # Handle exeception and log

            return job.name

    def complete(self, job_name: str) -> MRIFile | None:
        try:
            job = self.ml.jobs.get(job_name)

            if job.status == "Completed":
                # Download finished NIfTI of annotation into temporary directory
                temp_directory = tempfile.TemporaryDirectory()
                temp_dir_path = Path(temp_directory.name)
                self.ml.jobs.download(name=job.name, download_path=temp_dir_path)

                # Load NIfTI file from the directory
                mri = self._load_result(temp_dir_path)
                temp_directory.cleanup()

                return mri

            # elif job.status == 'Failed':
            #    annotation.job_name = None

        except ClientAuthenticationError:
            raise InferenceAuthException()  # Handle exeception and log

    def _load_result(self, directory_path: str) -> MRIFile | None:
        result_files = list(filter(
            lambda f: f.endswith(self.FILE_FORMAT),
            os.listdir(directory_path)
        ))
        if len(result_files) == 0:
            return None

        mri_file = result_files[0]
        with open(os.path.join(directory_path, mri_file), "rb") as f:
            content = BytesIO(f.read())
            return MRIFile(mri_file, content)
