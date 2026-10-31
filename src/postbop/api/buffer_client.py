import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from postbop.api.buffer_auth import refresh_tokens
from postbop.config import BUFFER_API_URL
from postbop.storage.credentials import load_access_token

class BufferApiError(RuntimeError):
    pass

def _graphql_request(
    query: str,
    variables: dict | None = None,
    allow_refresh: bool = True,
) -> dict:
    access_token = load_access_token()

    if access_token is None:
        raise BufferApiError(
            "No Buffer access token is stored"
        )

    payload = json.dumps({
        "query": query,
        "variables": variables or {},
    }).encode("utf-8")

    request = Request(
        BUFFER_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            result = json.load(response)

    except HTTPError as exception:
        if exception.code == 401 and allow_refresh:
            refresh_tokens()

            return _graphql_request(
                query,
                variables,
                allow_refresh=False,
            )

        raise BufferApiError(
            f"Buffer returned HTTP {exception.code}"
        ) from exception

    except URLError as exception:
        raise BufferApiError(
            "Unable to reach the Buffer API"
        ) from exception

    if not isinstance(result, dict):
        raise BufferApiError(
            "Buffer returned an invalid API response"
        )

    errors = result.get("errors")

    if errors:
        unauthorized = any(
            error.get("extensions", {}).get("code")
            == "UNAUTHORIZED"
            for error in errors
            if isinstance(error, dict)
        )

        if unauthorized and allow_refresh:
            refresh_tokens()

            return _graphql_request(
                query,
                variables,
                allow_refresh=False,
            )

        message = "Buffer API request failed"

        first_error = errors[0]

        if isinstance(first_error, dict):
            message = first_error.get(
                "message",
                message,
            )

        raise BufferApiError(message)

    data = result.get("data")

    if not isinstance(data, dict):
        raise BufferApiError(
            "Buffer returned no API data"
        )

    return data

def get_account() -> dict:
    query = """
    query GetAccount {
        account {
            id
            name
            timezone
            organizations {
                id
                name
                channelCount
            }
        }
    }
    """

    data = _graphql_request(query)

    return data["account"]

def get_channels(organization_id: str) -> list[dict]:
    query = """
    query GetChannels($organizationId: OrganizationId!) {
        channels(
            input: {
                organizationId: $organizationId
            }
        ) {
            id
            name
            displayName
            service
            isQueuePaused
            isDisconnected
            isLocked
        }
    }
    """

    data = _graphql_request(
        query,
        {
            "organizationId": organization_id,
        },
    )

    return data["channels"]