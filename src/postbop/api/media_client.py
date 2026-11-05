import json
import uuid

from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from postbop.config import COMPANION_BASE_URL
from postbop.models.media import HostedImage
from postbop.storage.credentials import load_media_token

class MediaUploadError(RuntimeError):
    pass

def upload_image( file_path: str | Path, ) -> HostedImage:
    path = Path(file_path)

    if not path.is_file():
        raise MediaUploadError( "The selected image does not exist." )

    media_token = load_media_token()

    if not media_token:
        raise MediaUploadError( "No PostBop media credential is stored." )

    boundary = uuid.uuid4().hex

    try:
        image_data = path.read_bytes()
    except OSError as exception:
        raise MediaUploadError( "Unable to read the selected image." ) from exception

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; '
        f'name="image"; '
        f'filename="{path.name}"\r\n'
        f"Content-Type: application/octet-stream\r\n"
        f"\r\n"
    ).encode("utf-8")

    body += image_data

    body += ( f"\r\n--{boundary}--\r\n" ).encode("utf-8")

    request = Request(
        f"{COMPANION_BASE_URL}/media/upload",
        data=body,
        headers={
            "Authorization": (
                f"Bearer {media_token}"
            ),
            "Content-Type": (
                "multipart/form-data; "
                f"boundary={boundary}"
            ),
        },
        method="POST",
    )

    try:
        with urlopen( request, timeout=30 ) as response:
            result = json.load(response)

    except HTTPError as exception:
        try:
            result = json.load( exception )
        except Exception:
            result = {}

        error = result.get(
            "error",
            f"http_{exception.code}",
        )

        if exception.code == 401:
            message = ( "PostBop's media credential is no longer valid." )

        elif exception.code == 413:
            message = ( "The selected image is too large." )

        elif exception.code == 415:
            message = ( "The selected image format is not supported." )

        else:
            message = (
                "The PostBop companion could "
                f"not upload the image: {error}"
            )

        raise MediaUploadError( message ) from exception

    except URLError as exception:
        raise MediaUploadError( "Unable to reach the PostBop media service." ) from exception

    except TimeoutError as exception:
        raise MediaUploadError( "The image upload timed out." ) from exception

    if not isinstance(result, dict):
        raise MediaUploadError( "The media service returned an invalid response." )

    if result.get("status") != "created":
        raise MediaUploadError( "The media service did not create the image." )

    try:
        media_id = int( result["media_id"] )
        url = str( result["url"] )
        mime_type = str( result["mime_type"] )
        byte_size = int( result["byte_size"] )

    except ( KeyError, TypeError, ValueError ) as exception:
        raise MediaUploadError( "The media service returned an incomplete response." ) from exception

    if not url.startswith("https://"):
        raise MediaUploadError( "The media service returned an invalid media URL." )

    return HostedImage( media_id=media_id, url=url, mime_type=mime_type, byte_size=byte_size )