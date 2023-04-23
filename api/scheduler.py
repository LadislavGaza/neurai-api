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
    f = open('test.txt', 'a')
    active_inferences = await crud.get_running_inferences()
    f.write('starting inference check' + str(active_inferences)+'\n')
    print('inferences to check', active_inferences)
    unprocessed_annotations = []
    for annotation in active_inferences:
        print(annotation.__dict__)
        mri = ml.complete(annotation.job_name)
        print('mri check resuts', mri)
        if mri is not None:
            refresh_token = annotation.creator.refresh_token
            uploaded_file = upload.drive_upload(mri, refresh_token)
            print('uploaded file', uploaded_file)
            await crud.update_annotation_file(
                id=annotation.id,
                filename=uploaded_file["name"],
                file_id=uploaded_file["id"],
                visible=False,  # remove should not be changed by finished job
                job_name=None       # Mark job as finished
            )
            f.write('starting to check queues' + str(app_fastapi.waiting_for_inference_queue.empty())+'\n')
            print('starting to check queues', app_fastapi.waiting_for_inference_queue.empty())
            while True:
                if app_fastapi.waiting_for_inference_queue.empty():
                    break
                user_id_to_check = await app_fastapi.waiting_for_inference_queue.get()
                print('getting user', user_id_to_check, annotation.mri_file_id)
                if user_id_to_check == annotation.created_by:
                    data = {
                        'annotation_id': annotation.id,
                        'user_id': annotation.created_by,
                        'mri_id': annotation.mri_file_id,
                        'screening_id': annotation.mri_file.screening_id,
                    }

                    await app_fastapi.finished_inference_message_queue.put(data)
                    print('empty?', app_fastapi.finished_inference_message_queue.empty())
                    f.write('empty?'+ app_fastapi.finished_inference_message_queue.empty()+'\n')
                    app_fastapi.waiting_for_inference_queue.task_done()
                    break
                else:
                    unprocessed_annotations.append(user_id_to_check)
                    app_fastapi.waiting_for_inference_queue.task_done()

            # await app_fastapi.waiting_for_inference_queue.join()
            f.write('unprocessed annotations' + str(unprocessed_annotations)+'\n')
            for ann in unprocessed_annotations:
                await app_fastapi.waiting_for_inference_queue.put(ann)
