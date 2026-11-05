from dataclasses import dataclass

@dataclass(frozen=True)
class HostedImage:
    media_id: int
    url: str
    mime_type: str
    byte_size: int