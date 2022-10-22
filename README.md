## NeurAI REST API Backend

Build with Python language and FastAPI web framework. It runs in ASGI web server Gunicorn

#### Development build

Run following commands:
```bash
$ docker-compose build
$ docker-compose up
```

- REST API launches on `localhost:8080`.
- Docstring auto-generated OpenAPI docs available at: `/docs`.



#### Generate migrations

Database should be accessible on URL set by environment variable  `DB_URL`.

Create python virtual environment in root project directory and install alembic

```bash
$ virtualenv .venv
$ source .venv/bin/activate
$ pip install sqlalchemy asyncpg alembic
$ export DB_URL="postgresql+asyncpg://user:password@localhost/db"
$ alembic -c config/alembic.ini revision --autogenerate -m "message"
```