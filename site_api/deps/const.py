import os
import json
import base64
import logging


APP_NAME = "NeurAI Hospital API"
COMMON_API_URL = os.environ.get("COMMON_API_URL")
SOP_CLASS_PREFIXES = {
    "1.2.840.10008.5.1.4.1.1.2": ("CT", "CT Image Storage"),
    "1.2.840.10008.5.1.4.1.1.2.1": ("CTE", "Enhanced CT Image Storage"),
    "1.2.840.10008.5.1.4.1.1.4": ("MR", "MR Image Storage"),
    "1.2.840.10008.5.1.4.1.1.4.1": ("MRE", "Enhanced MR Image Storage"),
    "1.2.840.10008.5.1.4.1.1.128": ("PT", "Positron Emission Tomography Image Storage"),
    "1.2.840.10008.5.1.4.1.1.130": ("PTE", "Enhanced PET Image Storage"),
    "1.2.840.10008.5.1.4.1.1.481.1": ("RI", "RT Image Storage"),
    "1.2.840.10008.5.1.4.1.1.481.2": ("RD", "RT Dose Storage"),
    "1.2.840.10008.5.1.4.1.1.481.5": ("RP", "RT Plan Storage"),
    "1.2.840.10008.5.1.4.1.1.481.3": ("RS", "RT Structure Set Storage"),
    "1.2.840.10008.5.1.4.1.1.1": ("CR", "Computed Radiography Image Storage"),
    "1.2.840.10008.5.1.4.1.1.6.1": ("US", "Ultrasound Image Storage"),
    "1.2.840.10008.5.1.4.1.1.6.2": ("USE", "Enhanced US Volume Storage"),
    "1.2.840.10008.5.1.4.1.1.12.1": ("XA", "X-Ray Angiographic Image Storage"),
    "1.2.840.10008.5.1.4.1.1.12.1.1": ("XAE", "Enhanced XA Image Storage"),
    "1.2.840.10008.5.1.4.1.1.20": ("NM", "Nuclear Medicine Image Storage"),
    "1.2.840.10008.5.1.4.1.1.7": ("SC", "Secondary Capture Image Storage"),
}

class CORS:
    ORIGINS = [
        "https://team23-22.studenti.fiit.stuba.sk",
        "http://localhost",
        "http://localhost:4040/",
        "http://localhost:4040",
        "http://localhost:8080/",
        "http://localhost:8080"
    ]


class PACS:
    IP = os.environ.get("PACS_IP")
    PORT = int(os.environ.get("PACS_PORT"))
    AE_TITLE = os.environ.get("PACS_AE_TITLE")


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
