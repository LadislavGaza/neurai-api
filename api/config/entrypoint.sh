#!/bin/bash

alembic -c api/config/alembic.ini -x data=true upgrade head

gunicorn -k uvicorn.workers.UvicornWorker -c api/config/gunicorn.conf.py api.main:app
