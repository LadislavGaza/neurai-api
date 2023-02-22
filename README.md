## NeurAI REST API Backend

Build with Python language and FastAPI web framework. It runs in ASGI web server Gunicorn

#### Development build

Set correct environment variables by using configuration templates from subfolder. Then run following commands:
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
virtualenv .venv
source .venv/bin/activate
pip install -r config/requirements.txt
export DB_URL="postgresql+asyncpg://user:password@localhost/db"
alembic -c config/alembic.ini revision --autogenerate -m "message"
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
(docker)$ alembic -c config/alembic.ini downgrade base
(docker)$ alembic -c config/alembic.ini -x data=true upgrade head
```

Encryption key and sigma is generated and set as environment variable 
```
import os  
import base64

b_key = os.urandom(32)
key = base64.b64encode(b_key)

b_sig = os.urandom(16)
sig = base64.b64encode(b_sig)

print('key: ', key.decode())
print('sig: ', sig.decode())
```

In order to add username to users table you need to  run next commands.
```bash
(docker)$ alembic -c config/alembic.ini downgrade -5
(docker)$ alembic -c config/alembic.ini -x data=true upgrade head
```
