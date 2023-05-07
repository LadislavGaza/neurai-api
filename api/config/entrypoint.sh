#!/bin/bash

alembic -c api/config/alembic.ini -x data=true upgrade head