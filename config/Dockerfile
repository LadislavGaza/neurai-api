FROM python:3.10-slim

WORKDIR /neurai-api
COPY . .

RUN pip install -r config/requirements.txt

EXPOSE 8080
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-c", "config/gunicorn.conf.py", "app.main:api"]
