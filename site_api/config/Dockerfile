FROM python:3.10-slim

RUN apt-get update
RUN apt-get -y upgrade
RUN apt-get install -y gcc sqlite3 libsqlite3-dev

WORKDIR /neurai
COPY site_api ./site_api
RUN mkdir -p sqlite
RUN pip install -r site_api/config/requirements.txt

COPY site_api/config/entrypoint.sh /
RUN chmod +x /entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-c", "site_api/config/gunicorn.conf.py", "site_api.main:app"]