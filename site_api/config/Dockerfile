FROM python:3.10-slim

RUN apt-get update
RUN apt-get -y upgrade
RUN apt-get install -y gcc sqlite3 libsqlite3-dev


WORKDIR /neurai
COPY site_api ./site_api
RUN pip install -r site_api/config/requirements.txt


EXPOSE 8080
CMD [                                       \
    "gunicorn",                             \
    "-k", "uvicorn.workers.UvicornWorker",  \
    "-c", "site_api/config/gunicorn.conf.py",    \
    "site_api.main:app"                          \
]

