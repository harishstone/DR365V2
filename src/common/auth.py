import requests
import os
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings()
load_dotenv()

VEEAM_SERVER = os.getenv("VEEAM_SERVER")
USERNAME = os.getenv("VEEAM_USERNAME")
PASSWORD = os.getenv("VEEAM_PASSWORD")

def get_access_token():
    url = f"https://{VEEAM_SERVER}:9419/api/oauth2/token"

    payload = {
        "grant_type": "password",
        "username": USERNAME,
        "password": PASSWORD
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(
        url,
        data=payload,
        headers=headers,
        verify=False
    )
    response.raise_for_status()

    return response.json()["access_token"]
