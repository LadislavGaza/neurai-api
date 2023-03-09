import os
import json
import base64
import logging


APP_NAME = "NeurAI Hospital API"


class JWT:
    SECRET = os.environ.get("JWT_SECRET")


class CORS:
    ORIGINS = [
        "https://team23-22.studenti.fiit.stuba.sk",
        "http://localhost",
        "http://localhost:4040/",
        "http://localhost:4040"
    ]


class LOGGING:
    MAX_SIZE_BYTES = 20000000
    ROTATIONS = 5
    CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "user": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(asctime)s [%(topic)s] [%(module)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "neurai": {
                "formatter": "default",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "/var/log/neurai/neurai.log",
                "maxBytes": MAX_SIZE_BYTES,
                "backupCount": ROTATIONS
            },
            "user": {
                "formatter": "user",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "/var/log/neurai/user.log",
                "maxBytes": MAX_SIZE_BYTES,
                "backupCount": ROTATIONS
            }
        },
        "loggers": {
            # Added in __init__
        }
    }

    def __init__(self):
        LOGGING.CONFIG["loggers"] = {
            name: {
                "handlers": ["console", "neurai"],
                "level": "WARNING"
            } for name in logging.root.manager.loggerDict
        }
        LOGGING.CONFIG["loggers"][APP_NAME] = {
            "handlers": ["console", "user"],
            "level": "INFO"
        }

        # Make sure subfolder exists
        filename = LOGGING.CONFIG["handlers"]["neurai"]["filename"]
        os.makedirs(os.path.dirname(filename), exist_ok=True)
