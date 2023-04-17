FROM python:3.10-slim

RUN apt-get update && apt-get -y upgrade
RUN apt-get install -y gcc azure-cli

WORKDIR /neurai
COPY api ./api
RUN pip install -r api/config/requirements.txt

EXPOSE 8080
ENTRYPOINT ["/bin/sh", "-c" , "alembic -c api/config/alembic.ini -x data=true upgrade head && python -m api.main"]

# ENTRYPOINT ["/bin/sh", "-c" , "alembic -c api/config/alembic.ini -x data=true upgrade head && gunicorn -k uvicorn.workers.UvicornWorker -c api/config/gunicorn.conf.py api.main:app"]