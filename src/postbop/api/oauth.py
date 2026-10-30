import base64
import hashlib
import secrets
from urllib.parse import urlencode

from postbop.config import (
    BUFFER_AUTH_URL,
    BUFFER_CLIENT_ID,
    BUFFER_REDIRECT_URI,
    BUFFER_SCOPES,
)

def generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)

def generate_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()

    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

def generate_state() -> str:
    return secrets.token_urlsafe(32)

def build_authorization_url(
    code_challenge: str,
    state: str,
) -> str:
    parameters = {
        "client_id": BUFFER_CLIENT_ID,
        "redirect_uri": BUFFER_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(BUFFER_SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "consent",
    }

    return f"{BUFFER_AUTH_URL}?{urlencode(parameters)}"