#!/bin/bash

alembic -c site_api/config/alembic.ini -x data=true upgrade head

gunicorn -k uvicorn.workers.UvicornWorker -c site_api/config/gunicorn.conf.py site_api.main:app
