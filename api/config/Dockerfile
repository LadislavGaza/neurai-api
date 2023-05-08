FROM python:3.10-slim

RUN apt-get update && apt-get -y upgrade
RUN apt-get install -y gcc azure-cli

WORKDIR /neurai
COPY api ./api
RUN pip install -r api/config/requirements.txt

COPY api/config/entrypoint.sh /
RUN chmod +x /entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["python", "-m", "api.main"]