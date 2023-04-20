"""
Based on: https://github.com/Miksus/rocketry-with-fastapi
"""
import asyncio
import logging
import uvicorn
import multiprocessing

from api.api import app as app_fastapi
from api.scheduler import app as app_rocketry


UVICORN_CONFIG = uvicorn.Config(
    app=app_fastapi,
    host="0.0.0.0",
    port=8080,
    workers=1, #multiprocessing.cpu_count() * 2 + 1,
    reload=True,
    loop="asyncio",
    log_level="debug"
)


class Server(uvicorn.Server):

    def handle_exit(self, sig: int, frame) -> None:
        app_rocketry.session.shut_down()
        return super().handle_exit(sig, frame)


async def main():
    server = Server(config=UVICORN_CONFIG)

    api = asyncio.create_task(server.serve())
    sched = asyncio.create_task(app_rocketry.serve())
    await asyncio.wait([sched, api])


if __name__ == "__main__":
    logger = logging.getLogger("rocketry.task")
    logger.addHandler(logging.StreamHandler())
    asyncio.run(main())
