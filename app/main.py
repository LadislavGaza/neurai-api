from fastapi import FastAPI


api = FastAPI(
    title='NeurAI',
    description='Intelligent neurosurgeon assistant',
    version='0.0.1',
    terms_of_service="http://example.com/terms/",
    contact={
        "name": "Team 23",
        "url": "https://tp23.atlassian.net/",
    }
)


@api.get('/')
def index():
    return 'Hello world'
