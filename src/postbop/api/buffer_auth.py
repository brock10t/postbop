import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from postbop.config import (
    BUFFER_CLIENT_ID,
    BUFFER_REDIRECT_URI,
    BUFFER_TOKEN_URL,
)
from postbop.storage.credentials import (
    load_refresh_token,
    store_access_token,
    store_refresh_token,
)

class BufferAuthError(RuntimeError):
    pass

def _request_tokens(parameters: dict[str, str]) -> dict:
    payload = urlencode(parameters).encode("ascii")

    request = Request(
        BUFFER_TOKEN_URL,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
    except HTTPError as exception:
        try:
            result = json.load(exception)
        except Exception:
            result = {}

        error = result.get(
            "error",
            f"http_{exception.code}",
        )

        description = result.get(
            "error_description",
            "Buffer rejected the authentication request",
        )

        raise BufferAuthError(
            f"{error}: {description}"
        ) from exception

    except URLError as exception:
        raise BufferAuthError(
            "Unable to reach Buffer's authentication service"
        ) from exception

    if not isinstance(result, dict):
        raise BufferAuthError(
            "Buffer returned an invalid token response"
        )

    return result

def _store_token_response(tokens: dict) -> None:
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if not isinstance(access_token, str) or not access_token:
        raise BufferAuthError(
            "Buffer did not return an access token"
        )

    if not isinstance(refresh_token, str) or not refresh_token:
        raise BufferAuthError(
            "Buffer did not return a refresh token"
        )

    store_refresh_token(refresh_token)
    store_access_token(access_token)

def exchange_authorization_code(
    authorization_code: str,
    code_verifier: str,
) -> dict:
    tokens = _request_tokens({
        "client_id": BUFFER_CLIENT_ID,
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": BUFFER_REDIRECT_URI,
        "code_verifier": code_verifier,
    })

    _store_token_response(tokens)

    return tokens

def refresh_tokens() -> dict:
    refresh_token = load_refresh_token()

    if refresh_token is None:
        raise BufferAuthError(
            "No Buffer refresh token is stored"
        )

    tokens = _request_tokens({
        "client_id": BUFFER_CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })

    _store_token_response(tokens)

    return tokens