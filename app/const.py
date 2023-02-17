import os
import json
import base64

APP_NAME = "NeurAI"


class JWT:
    SECRET = os.environ.get("JWT_SECRET")  # openssl rand -hex 32
    EXPIRATION_SECONDS = int(os.environ.get("JWT_EXPIRATION_SECONDS"))
    EXPIRATION_PASSWORD_RESET = int(os.environ.get("JWT_EXPIRATION_PASSWORD_RESET"))


class GoogleAPI:
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]

    # https://developers.google.com/identity/protocols/oauth2/web-server#creatingcred
    CREDS_FILE = "config/web_credentials.json"
    CREDS = json.load(open(CREDS_FILE, "r"))
    REDIRECT_URL = os.environ.get("REDIRECT_URL")

    DRIVE_MIME_TYPE = "application/vnd.google-apps.folder"
    CONTENT_FILTER = f'mimeType = "{DRIVE_MIME_TYPE}" and name="{APP_NAME}"'


class CORS:
    ORIGINS = [
        "https://team23-22.studenti.fiit.stuba.sk"
        "http://localhost",
        "http://localhost:4040/",
        "http://localhost:4040"
    ]


class ENC:
    KEY = base64.b64decode(bytes(os.environ.get("ENC_KEY"), "utf-8"))
    SIG = base64.b64decode(bytes(os.environ.get("ENC_SIG"), "utf-8"))
