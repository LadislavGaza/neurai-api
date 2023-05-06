import json

from site_api import main
from fastapi import Request


def get_localization_data(request: Request):
    accepted_language = request.headers.get("Accept-Language")

    translation = None
    if not accepted_language or accepted_language not in main.app_languages:
        accepted_language = main.language_fallback

    if accepted_language == "en":
        translation = open("api/lang/en.json", "r")
    elif accepted_language == "sk":
        translation = open("api/lang/sk.json", "r")

    return json.load(translation)


def filter_dict_keys(dictionary: dict, allowed_keys: set):
    return {
        k: v for k, v in dictionary.items() 
        if v and k in allowed_keys
    }

def rename_dict_keys(dictionary: dict, mapper: dict):
    return {
        mapper[k]: v for k, v in dictionary.items() 
    }