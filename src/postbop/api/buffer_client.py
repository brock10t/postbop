import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from postbop.api.buffer_auth import refresh_tokens
from postbop.config import BUFFER_API_URL
from postbop.storage.credentials import load_access_token

from http.client import IncompleteRead

class BufferApiError(RuntimeError):
    pass

class BufferSubmissionUncertainError(BufferApiError):
    """A write request may have succeeded, but was not confirmed."""
    pass

class BufferRateLimitError(BufferApiError):
    def __init__( self, retry_after: int | None = None, window: str | None = None ):
        
        self.retry_after = retry_after
        self.window = window

        if retry_after is not None:
            message = ( "Buffer rate limit reached. Retry in {retry_after} seconds." )
        else:
            message = ("Buffer rate limit reached. Please try again later." )

        super().__init__(message)

def _graphql_request( query: str, variables: dict | None = None, allow_refresh: bool = True, *, 
                     submission: bool = False
) -> dict:
    access_token = load_access_token()

    if access_token is None:
        raise BufferApiError( "No Buffer access token is stored" )

    payload = json.dumps({ "query": query, "variables": variables or {} }).encode("utf-8")

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
        if exception.code == 429:
            retry_after = None
            window = None

            retry_after_header = ( exception.headers.get( "Retry-After" ) )

            if retry_after_header:
                try:
                    retry_after = int( retry_after_header )
                except ValueError:
                    pass

            try:
                error_result = json.load( exception )
            except Exception:
                error_result = {}

            errors = error_result.get(
                "errors",
                [],
            )

            if errors:
                first_error = errors[0]

                if isinstance( first_error, dict ):
                    extensions = ( first_error.get( "extensions", {} ) )
                    window = extensions.get( "window" )

            raise BufferRateLimitError(
                retry_after=retry_after,
                window=window,
            ) from exception

        if exception.code == 401 and allow_refresh:
            refresh_tokens()
            return _graphql_request( query, variables, allow_refresh=False, submission=submission )

        # A server error or request timeout may occur after Buffer has already created the post.
        if submission and ( exception.code >= 500 or exception.code == 408 ):
            raise BufferSubmissionUncertainError(
                "Buffer did not confirm whether the post was created."
            ) from exception

        raise BufferApiError( f"Buffer returned HTTP {exception.code}" ) from exception

    except ( URLError, OSError, IncompleteRead, json.JSONDecodeError, UnicodeError ) as exception:
        if submission:
            raise BufferSubmissionUncertainError(
                "The connection was interrupted before Buffer confirmed the submission."
            ) from exception
        raise BufferApiError(
            "Unable to complete the Buffer API request."
        ) from exception

    if not isinstance(result, dict):
        if submission:
            raise BufferSubmissionUncertainError( "Buffer returned an invalid submission response." )

        raise BufferApiError( "Buffer returned an invalid API response." )

    errors = result.get("errors")

    if errors:
        rate_limited_error = next(
            (
                error
                for error in errors
                if (
                    isinstance(error, dict)
                    and error.get(
                        "extensions",
                        {},
                    ).get("code")
                    == "RATE_LIMIT_EXCEEDED"
                )
            ),
            None,
        )

        if rate_limited_error is not None:
            window = rate_limited_error.get(
                "extensions",
                {},
            ).get("window")

            raise BufferRateLimitError(
                window=window,
            )

        unauthorized = any(
            error.get("extensions", {}).get("code")
            == "UNAUTHORIZED"
            for error in errors
            if isinstance(error, dict)
        )

        if unauthorized and allow_refresh:
            refresh_tokens()

            return _graphql_request( query, variables, allow_refresh=False )

        message = "Buffer API request failed"

        first_error = errors[0]

        if isinstance(first_error, dict):
            message = first_error.get( "message", message )
            raise BufferApiError(message)

        # These errors explicitly indicate that the request was rejected rather than completed.
        confirmed_rejection_codes = {
            "UNAUTHORIZED",
            "FORBIDDEN",
            "NOT_FOUND",
            "INSUFFICIENT_SCOPE",
            "BAD_USER_INPUT",
            "GRAPHQL_VALIDATION_FAILED",
        }

        if submission:
            codes = [
                error.get("extensions", {}).get("code")
                if isinstance(error, dict)
                and isinstance(error.get("extensions"), dict)
                else None
                for error in errors
            ]

            if any(
                code not in confirmed_rejection_codes
                for code in codes
            ):
                raise BufferSubmissionUncertainError( f"Buffer did not confirm the submission: {message}" )

    data = result.get("data")

    if not isinstance(data, dict):
        if submission:
            raise BufferSubmissionUncertainError( "Buffer returned no confirmation of the submission." )
        raise BufferApiError( "Buffer returned no API data." )

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

    data = _graphql_request( query, { "organizationId": organization_id, } )

    return data["channels"]

def create_queue_post( channel_id: str, text: str, image_url: str | None = None,
                      link_url: str | None = None, service: str | None = None ) -> dict:

    link_url = link_url.strip() if link_url else None

    if not link_url:
        link_url = None

    if image_url and link_url:
        raise ValueError( "An image and link attachment cannot be combined." )

    metadata = _build_link_metadata( link_url, service )

    if not text.strip() and not image_url and not metadata:
        raise ValueError( "A post must contain text, an image, or a link." )

    query = """
    mutation CreateQueuePost(
        $text: String!
        $channelId: ChannelId!
        $assets: [AssetInput!]!
        $metadata: PostInputMetaData
    ) {
        createPost(
            input: {
                text: $text
                channelId: $channelId
                schedulingType: automatic
                mode: addToQueue
                assets: $assets
                metadata: $metadata
            }
        ) {
            __typename

            ... on PostActionSuccess {
                post {
                    id
                    text
                    dueAt
                    status
                    assets {
                        id
                        mimeType
                    }
                }
            }

            ... on MutationError {
                message
            }
        }
    }
    """

    assets = []

    if image_url:
        assets.append({
            "image": {
                "url": image_url,
            }
        })

    data = _graphql_request(
        query,
        {
            "text": text,
            "channelId": channel_id,
            "assets": assets,
            "metadata": metadata,
        },
        submission=True,
    )

    result = data.get( "createPost" )

    if not isinstance(result, dict):
        raise BufferApiError( "Buffer returned an invalid post response" )

    result_type = result.get("__typename")

    if result_type == "MutationError":
        raise BufferApiError(
            result.get( "message", "Buffer could not create the post" )
        )

    if result_type != "PostActionSuccess":
        raise BufferApiError( "Buffer returned an unexpected post result" )

    post = result.get("post")

    if not isinstance(post, dict):
        raise BufferApiError( "Buffer did not return the created post" )

    return post

def create_draft_post( channel_id: str, text: str, image_url: str | None = None,
                      link_url: str | None = None, service: str | None = None ) -> dict:

    link_url = link_url.strip() if link_url else None

    if not link_url:
        link_url = None

    if image_url and link_url:
        raise ValueError( "An image and link attachment cannot be combined." )

    metadata = _build_link_metadata( link_url, service )

    if not text.strip() and not image_url and not metadata:
        raise ValueError( "A post must contain text, an image, or a link." )

    query = """
    mutation CreateDraftPost(
        $text: String!
        $channelId: ChannelId!
        $assets: [AssetInput!]!
        $metadata: PostInputMetaData
    ) {
        createPost(
            input: {
                text: $text
                channelId: $channelId
                schedulingType: automatic
                mode: addToQueue
                saveToDraft: true
                assets: $assets
                metadata: $metadata
            }
        ) {
            __typename

            ... on PostActionSuccess {
                post {
                    id
                    text
                    status
                    assets {
                        id
                        mimeType
                    }
                }
            }

            ... on MutationError {
                message
            }
        }
    }
    """

    assets = []

    if image_url:
        assets.append({
            "image": {
                "url": image_url,
            }
        })

    data = _graphql_request(
        query,
        {
            "text": text,
            "channelId": channel_id,
            "assets": assets,
            "metadata": metadata,
        },
        submission=True,
    )

    result = data.get( "createPost" )

    if not isinstance(result, dict):
        raise BufferApiError( "Buffer returned an invalid draft response" )

    result_type = result.get( "__typename" )

    if result_type == "MutationError":
        raise BufferApiError(
            result.get( "message", "Buffer could not create the draft" )
        )

    if result_type != "PostActionSuccess":
        raise BufferApiError( "Buffer returned an unexpected draft result" )

    post = result.get("post")

    if not isinstance(post, dict):
        raise BufferApiError( "Buffer did not return the created draft" )

    return post

def create_idea( organization_id: str, text: str ) -> dict:
    if not text.strip():
        raise ValueError( "Idea text cannot be empty" )

    query = """
    mutation CreateIdea(
        $organizationId: ID!
        $text: String!
    ) {
        createIdea(
            input: {
                organizationId: $organizationId
                content: {
                    text: $text
                }
            }
        ) {
            __typename

            ... on Idea {
                id
                organizationId
                content {
                    text
                    title
                }
            }

            ... on MutationError {
                message
            }
        }
    }
    """

    data = _graphql_request(
        query,
        {
            "organizationId": organization_id,
            "text": text,
        },
        submission=True,
    )

    result = data.get("createIdea")

    if not isinstance(result, dict):
        raise BufferApiError( "Buffer returned an invalid idea response" )

    result_type = result.get("__typename")

    if result_type == "MutationError":
        raise BufferApiError( result.get( "message", "Buffer could not create the idea" ) )

    if result_type != "Idea":
        raise BufferApiError( result.get( "message", "Buffer returned an unexpected idea result" ) )

    return result

LINK_ATTACHMENT_SERVICES = {
    "bluesky",
    "facebook",
    "linkedin",
    "substack",
    "threads",
}


def _build_link_metadata( link_url: str | None, service: str | None ) -> dict | None:
    if not link_url:
        return None

    url = link_url.strip()

    if (
        not url
        or any(
            character.isspace() or ord(character) < 32
            for character in url
        )
    ):
        raise ValueError( "Enter a valid link URL without whitespace." )

    try:
        parsed = urlsplit(url)

        valid_url = (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )

    except ValueError:
        valid_url = False

    if not valid_url:
        raise ValueError( "Link attachments require a valid HTTP or HTTPS URL." )

    service = (service or "").lower()

    if service not in LINK_ATTACHMENT_SERVICES:
        raise ValueError(
            f"Link attachments are not supported for "
            f"{service or 'this channel'}."
        )

    return {
        service: {
            "linkAttachment": {
                "url": url,
            }
        }
    }