import os
import shutil
import tempfile
import uuid
import re

from pathlib import Path

MAX_IMAGE_BYTES = 10 * 1024 * 1024

SUPPORTED_EXTENSIONS = { ".jpg", ".jpeg", ".png", ".webp" }


def get_media_cache_dir() -> Path:
    state_home = Path( os.environ.get( "XDG_STATE_HOME", str(Path.home() / ".local/state"), ) ).expanduser()

    return state_home / "postbop" / "media"


def cache_image( source: str | Path ) -> Path:
    source = Path( source )

    if not source.is_file():
        raise ValueError( "The selected image does not exist." )

    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError( "The selected image format is not supported." )

    byte_size = source.stat().st_size

    if byte_size <= 0 or byte_size > MAX_IMAGE_BYTES:
        raise ValueError( "The selected image exceeds the allowed size." )

    cache_dir = get_media_cache_dir()

    cache_dir.mkdir( parents=True, exist_ok=True, mode=0o700 )

    filename = (
        f"{uuid.uuid4().hex}"
        f"{source.suffix.lower()}"
    )

    destination = cache_dir / filename

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile( dir=cache_dir, prefix=".incoming-", delete=False ) as temporary_file:
            temporary_path = Path( temporary_file.name )

            with source.open( "rb" ) as original:
                shutil.copyfileobj( original, temporary_file )

        # Catch a source file that grew during copying.
        if ( temporary_path.stat().st_size > MAX_IMAGE_BYTES ):
            raise ValueError( "The selected image exceeds the allowed size." )

        os.replace( temporary_path, destination )

    finally:
        if ( temporary_path is not None and temporary_path.exists() ):
            temporary_path.unlink()

    return destination


def delete_cached_image( image_path: str | Path | None ) -> None:
    if image_path is None:
        return

    path = Path( image_path )

    cache_dir = get_media_cache_dir().resolve()

    # Never delete an arbitrary user-selected file.
    if path.parent.resolve() != cache_dir:
        raise ValueError( "Refusing to delete a file outside PostBop's media cache." )

    if (
        len(path.stem) != 32
        or any(
            character not in "0123456789abcdef"
            for character in path.stem
        )
        or path.suffix.lower() not in SUPPORTED_EXTENSIONS
    ):
        raise ValueError( "Refusing to delete an unrecognized cached image." )

    path.unlink( missing_ok=True )

def get_cached_image( filename: str | None ) -> Path | None:
        if not isinstance(filename, str):
            return None

        if not re.fullmatch( r"[a-f0-9]{32}\.(?:jpg|jpeg|png|webp)", filename, ):
            return None

        path = get_media_cache_dir() / filename

        if path.is_symlink() or not path.is_file():
            return None

        return path