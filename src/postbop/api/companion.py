import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from postbop.config import COMPANION_BASE_URL

def create_oauth_session(state_hash: str) -> None:
    payload = json.dumps({
        "state_hash": state_hash,
    }).encode("utf-8")

    request = Request(
        f"{COMPANION_BASE_URL}/oauth/session",
        data=payload,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
    except HTTPError as exception:
        raise RuntimeError(
            f"Companion returned HTTP {exception.code}"
        ) from exception
    except URLError as exception:
        raise RuntimeError(
            "Unable to reach the PostBop companion service"
        ) from exception

    if result.get("status") != "created":
        raise RuntimeError(
            "Companion did not create the OAuth session"
        )

def get_oauth_result( state: str ) -> dict:
    payload = json.dumps({ "state": state, }).encode("utf-8")

    request = Request(
        f"{COMPANION_BASE_URL}/oauth/result",
        data=payload,
        headers={ "Content-Type": "application/json", },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            return json.load(response)
    except HTTPError as exception:
        try:
            result = json.load(exception)
        except Exception:
            result = {}

        error = result.get(
            "error",
            f"http_{exception.code}",
        )

        raise RuntimeError(
            f"OAuth relay error: {error}"
        ) from exception
    except URLError as exception:
        raise RuntimeError( "Unable to reach the PostBop companion service" ) from exception

def activate_media_credential( media_token: str, buffer_access_token: str ) -> None:
    payload = json.dumps({ "buffer_access_token": buffer_access_token, }).encode("utf-8")

    request = Request(
        f"{COMPANION_BASE_URL}/media/activate",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {media_token}",
        },
        method="POST",
    )

    try:
        with urlopen( request, timeout=25 ) as response:
            result = json.load(response)

    except HTTPError as exception:
        raise RuntimeError(
            f"Media activation failed "
            f"(HTTP {exception.code})."
        ) from exception

    except URLError as exception:
        raise RuntimeError( "Unable to reach the media activation service." ) from exception

    if result.get("status") != "activated":
        raise RuntimeError( "The media service did not activate the credential." )