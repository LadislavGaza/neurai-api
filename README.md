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

#### Run migrations

Execute into container and run alembic. Environment variable should already be set.
```bash
$ docker-compose exec api bash
(docker)$ alembic -c config/alembic.ini upgrade head
```

https://alembic.sqlalchemy.org/en/latest/cookbook.html
In order to seed test data to database run next command instead. if you already updated schema
to newest version you have to downgrade in order to force data seeding
```bash
(docker)$ alembic -c config/alembic.ini downgrade -1
(docker)$ alembic -c config/alembic.ini -x data=true upgrade head
```
