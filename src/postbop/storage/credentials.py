import gi

gi.require_version("Secret", "1")

from gi.repository import Secret

TOKEN_SCHEMA = Secret.Schema.new(
    "co._10t.PostBop.BufferToken",
    Secret.SchemaFlags.NONE,
    {
        "provider": Secret.SchemaAttributeType.STRING,
        "token_type": Secret.SchemaAttributeType.STRING,
    },
)

PROVIDER = "buffer"

ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"

def _attributes(token_type: str) -> dict[str, str]:
    return {
        "provider": PROVIDER,
        "token_type": token_type,
    }

def _store_token(
    token_type: str,
    label: str,
    token: str,
) -> None:
    if not token:
        raise ValueError("Token cannot be empty")

    stored = Secret.password_store_sync(
        TOKEN_SCHEMA,
        _attributes(token_type),
        Secret.COLLECTION_DEFAULT,
        label,
        token,
        None,
    )

    if not stored:
        raise RuntimeError(
            f"Unable to store Buffer {token_type} token"
        )

def _load_token(token_type: str) -> str | None:
    return Secret.password_lookup_sync(
        TOKEN_SCHEMA,
        _attributes(token_type),
        None,
    )

def _clear_token(token_type: str) -> bool:
    return Secret.password_clear_sync(
        TOKEN_SCHEMA,
        _attributes(token_type),
        None,
    )

def store_access_token(token: str) -> None:
    _store_token(
        ACCESS_TOKEN,
        "PostBop Buffer Access Token",
        token,
    )

def store_refresh_token(token: str) -> None:
    _store_token(
        REFRESH_TOKEN,
        "PostBop Buffer Refresh Token",
        token,
    )

def load_access_token() -> str | None:
    return _load_token(ACCESS_TOKEN)

def load_refresh_token() -> str | None:
    return _load_token(REFRESH_TOKEN)

def clear_tokens() -> None:
    _clear_token(ACCESS_TOKEN)
    _clear_token(REFRESH_TOKEN)