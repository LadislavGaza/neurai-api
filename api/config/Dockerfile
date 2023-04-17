FROM python:3.10-slim

RUN apt-get update && apt-get -y upgrade
RUN apt-get install -y gcc

# install azure cli
RUN apt-get install -y ca-certificates curl apt-transport-https lsb-release gnupg
RUN mkdir -p /etc/apt/keyrings
RUN curl -sLS https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | tee /etc/apt/keyrings/microsoft.gpg > /dev/null
RUN chmod go+r /etc/apt/keyrings/microsoft.gpg
RUN AZ_REPO=$(lsb_release -cs) && "deb [arch=`dpkg --print-architecture` signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ $AZ_REPO main" | \
    tee /etc/apt/sources.list.d/azure-cli.list
RUN apt-get update && apt-get install -y azure-cli

WORKDIR /neurai
COPY api ./api
RUN pip install -r api/config/requirements.txt

EXPOSE 8080
# CMD [                                       \
#     "gunicorn",                             \
#     "-k", "uvicorn.workers.UvicornWorker",  \
#     "-c", "api/config/gunicorn.conf.py",    \
#     "api.main:app"                          \
# ]

ENTRYPOINT ["/bin/sh", "-c" , "alembic -c api/config/alembic.ini -x data=true upgrade head && gunicorn -k uvicorn.workers.UvicornWorker -c api/config/gunicorn.conf.py api.main:app"]