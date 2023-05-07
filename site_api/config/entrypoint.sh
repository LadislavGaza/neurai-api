#!/bin/bash

rm -rf /neurai/sqlite && mkdir -p /neurai/sqlite
sqlite3 /neurai/sqlite/neurai.db ""
alembic -c /neurai/site_api/config/alembic.ini -x data=true upgrade head