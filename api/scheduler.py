from rocketry import Rocketry
from rocketry.conds import every

from api.deps.inference import MLInference
from api.deps import upload
from api.db import crud
from api.api import app as app_fastapi

app = Rocketry(config={"task_execution": "async"})


@app.task(every('1 minutes', based="finish"))
async def check_done_inference():
    ml = MLInference()
    active_inferences = await crud.get_running_inferences()
    # app_fastapi.waiting_for_inference_queue.put('12') # contains mri_id value # just test
    unprocessed_annotations = []
    for annotation in active_inferences:
        mri = ml.complete(annotation.job_name)

        if mri is not None:
            refresh_token = annotation.creator.refresh_token
            uploaded_file = upload.drive_upload(mri, refresh_token)

            await crud.update_annotation_file(
                id=annotation.id,
                filename=uploaded_file["name"],
                file_id=uploaded_file["id"],
                visible=False,
                job_name=None       # Mark job as finished
            )
            while True:
                mri_id_to_check = app_fastapi.waiting_for_inference_queue.get_nowait()
                if mri_id_to_check == annotation.mri_file_id:
                    data = {
                        'annotation-id': annotation.id,
                        'user_id': annotation.created_by,
                        'mri_id': annotation.mri_file_id,
                        'screening_id': annotation.mri_file.screening_id,
                    }

                    app_fastapi.finished_inference_message_queue.put(data)
                    app_fastapi.waiting_for_inference_queue.task_done()
                    break

    await app_fastapi.waiting_for_inference_queue.join()
    for ann in unprocessed_annotations:
        app_fastapi.waiting_for_inference_queue.put_nowait(ann)
