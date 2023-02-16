FROM python:3.10-slim

RUN apt-get update
RUN apt-get install -y gcc

WORKDIR /neurai-api
COPY config/requirements.txt config/requirements.txt
RUN pip install -r config/requirements.txt

COPY . .

EXPOSE 8080
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-c", "config/gunicorn.conf.py", "app.main:api"]
