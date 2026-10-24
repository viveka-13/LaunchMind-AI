# agent/export/google_auth_helper.py
# Google OAuth2 and Service Account credential resolver for Google Docs and Google Slides

import os
import json
import logging
from typing import Optional, Tuple, Any
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive.file",
]

# Safe path for user credentials outside repo
TOKEN_PATH = os.environ.get("GOOGLE_OAUTH_TOKEN_PATH", "./data/tokens/google_token.json")


def get_google_credentials() -> Tuple[Optional[Any], Optional[str], Optional[str]]:
    """
    Resolve Google API credentials.
    Priority:
    1. OAuth2 User Credentials from GOOGLE_OAUTH_TOKEN_PATH (with refresh)
    2. Service Account from GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_SERVICE_ACCOUNT_JSON
    Returns: (credentials, auth_mode, error_or_instruction)
    """
    # 1. OAuth2 User Credentials
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                os.makedirs(os.path.dirname(os.path.abspath(TOKEN_PATH)), exist_ok=True)
                with open(TOKEN_PATH, "w") as token_file:
                    token_file.write(creds.to_json())
            return creds, "oauth2", None
        except Exception as e:
            logger.warning(f"[GoogleAuth] Failed to load OAuth token from {TOKEN_PATH}: {e}")

    # 2. Service Account File
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if sa_path and os.path.exists(sa_path):
        try:
            creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
            return creds, "service_account", None
        except Exception as e:
            logger.warning(f"[GoogleAuth] Failed to load service account from {sa_path}: {e}")

    # 3. Inline Service Account JSON
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        try:
            info = json.loads(sa_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            return creds, "service_account", None
        except Exception as e:
            logger.warning(f"[GoogleAuth] Failed to load service account from JSON: {e}")

    instructions = (
        "Google API credentials not configured. To enable Google Docs/Slides exports:\n"
        "Option A (OAuth2): Save authorized credentials to ./data/tokens/google_token.json (or GOOGLE_OAUTH_TOKEN_PATH).\n"
        "Option B (Service Account): Set GOOGLE_APPLICATION_CREDENTIALS to your service account key file path."
    )
    return None, None, instructions
