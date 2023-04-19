from rocketry import Rocketry
from rocketry.conds import every

from api.deps.inference import MLInference
from api.deps import upload
from api.db import crud

app = Rocketry(config={"task_execution": "async"})


@app.task(every('1 minutes', based="finish"))
async def check_done_inference():
    ml = MLInference()
    active_inferences = await crud.get_running_inferences()

    for annotation in active_inferences:
        mri = ml.complete(annotation.job_name)

        if mri is not None:
            refresh_token = annotation.creator.refresh_token
            uploaded_file = upload.drive_upload(mri, refresh_token)

            await crud.update_annotation_file(
                id=annotation.id,
                filename=uploaded_file["name"],
                file_id=uploaded_file["id"],
                is_ai=True,
                job_name=None       # Mark job as finished
            )
