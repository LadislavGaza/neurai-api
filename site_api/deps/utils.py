import json

from site_api import main
from fastapi import Request


def get_localization_data(request: Request):
    accepted_language = request.headers.get("Accept-Language")
    print('language', accepted_language)
    translation = None
    if not accepted_language or accepted_language not in main.app_languages:
        accepted_language = main.language_fallback

    if accepted_language == "en":
        translation = open("api/lang/en.json", "r")
    elif accepted_language == "sk":
        translation = open("api/lang/sk.json", "r")

    return json.load(translation)
