import os
import requests
from jinja2 import Template

SMTP_API_KEY = os.environ.get("SMTP_API_KEY")
SMTP_DOMAIN = os.environ.get("SMTP_DOMAIN")
DOMAIN = os.environ.get("DOMAIN")


def send_reset_email(to, token):
    with open(os.path.join(os.path.dirname(__file__), "reset_password.html")) as f:
        template = Template(f.read())
        res = requests.post(
            f"https://api.eu.mailgun.net/v3/{SMTP_DOMAIN}/messages",
            auth=("api", SMTP_API_KEY),
            data={
                "from": "NeurAI <team23.tp@gmail.com>",
                "to": [to],
                "subject": "Resetovanie hesla",
                "html": template.render(
                    RESET_PASSWORD_URL=f"{DOMAIN}/reset-hesla?token={token}"
                ),
            },
        )
        return res
