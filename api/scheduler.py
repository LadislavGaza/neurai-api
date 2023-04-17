import asyncio
from rocketry import Rocketry
from rocketry.conds import every

app = Rocketry(config={"task_execution": "async"})


@app.task(every('1 minutes', based="finish"))
async def inference_status():
    await asyncio.sleep(1)


# 1. Z annotations si vytiahnes vsetko co ma jobname IS NOT NULL
# 2. Pre kazdy jobname urobis 
#     2.1 job = ml_client.jobs.get(job.name)
#     2.2 if job.status == Completed
#         2.2.1 zrob temp directory a spusti download do temp directory
#         2.2.2 nacitaj subor s nazvom [INPUT FILENAME] z temp directory a zrob ulozenie na gdrive
#         2.2.3 jobname = null
#     2.3 if job.status == Failed
#         2.3.1 jobname = null ??????? raise RuntimeError?


# do annotations pridat fieldy:
# - is_ai boolean NOT NULL
# - job-name string NULLABLE - NEPOSIELAT NA FE !!! -> zmenit na status = progress / completed