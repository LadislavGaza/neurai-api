import os
import os.path
import tempfile
from io import BytesIO
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.ai.ml import MLClient, Input
from azure.ai.ml.entities import Model, Data
from azure.ai.ml.constants import AssetTypes
from azure.core.exceptions import ClientAuthenticationError

from api.deps import const
from api.deps.mri_file import MRIFile


class InferenceAuthException(Exception):
    pass


def get_ml_client():
    return MLClient(
        DefaultAzureCredential(),
        os.environ.get("AZURE_ML_SUBSCRIPTION_ID"),
        os.environ.get("AZURE_ML_RESOURCE_GROUP"),
        os.environ.get("AZURE_ML_WORKSPACE")
    )


def launch(mri: BytesIO) -> str:
    ml = get_ml_client()

    with tempfile.NamedTemporaryFile(suffix=".nii.gz") as nifti:
        path = Path(nifti.name)
        nifti.write(mri.getbuffer())

        source = Data(path=path, type=AssetTypes.URI_FILE)

        try:
            data = ml.data.create_or_update(source)
            input_file = Input(type=AssetTypes.URI_FILE, path=data.id)

            # TODO: fix exception Exception: BY_POLICY
            job = ml.batch_endpoints.invoke(
                endpoint_name=os.environ.get("AZURE_ML_ENDPOINT"),
                inputs={"file": input_file}
            )
        except ClientAuthenticationError:
            raise InferenceAuthException()  # Handle exeception and log

        return job.name


def load_result(path: str) -> MRIFile | None:
    result_files = list(filter(
        lambda f: f.endswith("nii.gz"),
        os.listdir(temp_dir_path)
    ))
    if len(result_files) == 0:
        return None

    with open(os.path.join(temp_dir_path, result_file), "rb") as f:
        content = BytesIO(f.read())
        return MRIFile(result_file, content)


def complete(job_name: str) -> MRIFile | None:
    ml = get_ml_client()
    try:
        job = ml.jobs.get(job_name)

        if job.status == "Completed":
            # Download finished NIfTI of annotation into temporary directory
            temp_directory = tempfile.TemporaryDirectory()
            temp_dir_path = Path(temp_directory.name)
            ml.jobs.download(name=job.name, download_path=temp_dir_path)

            # Load NIfTI file from the directory
            mri = load_result(temp_dir_path)
            temp_directory.cleanup()

            return mri
 
        # elif job.status == 'Failed':
        #    annotation.job_name = None

    except ClientAuthenticationError:
         raise InferenceAuthException()  # Handle exeception and log
