from fastapi import FastAPI
import app.model as m
from app import crud


api = FastAPI(
    title='NeurAI',
    description='Intelligent neurosurgeon assistant',
    version='0.0.1',
    contact={
        "name": "Team 23",
        "url": "https://tp23.atlassian.net/",
    }
)


@api.get('/')
async def index():
    async with m.engine.connect() as conn:
        query = crud.sample_text()
        name = (await conn.scalars(query)).first()
    return name
