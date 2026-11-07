import re

from dataclasses import dataclass

# Networks that use standard UTF-16 counting.
CHARACTER_LIMITS = {
    "facebook": 5000,
    "threads": 500,
    "pinterest": 500,
    "tiktok": 4000,
    "youtube": 5000,
    "googlebusiness": 4000,
    "substack": 10000,
}


URL_PATTERN = re.compile( r"(?i)\b(?:https?://|www\.)[^\s<>]+" )

@dataclass(frozen=True)
class ChannelCharacterCheck:
    channel_id: str
    channel_name: str
    service: str
    used: int | None
    limit: int | None
    exact: bool = True
    note: str = ""

    @property
    def remaining(self) -> int | None:
        if self.used is None or self.limit is None:
            return None
        return self.limit - self.used

    @property
    def over_limit(self) -> bool:
        if self.remaining is None or self.remaining >= 0:
            return False

        # Exact counts always enforce the platform limit.
        if self.exact:
            return True

        # Block substantially oversized estimated Bluesky posts.
        if self.service == "bluesky":
            return self.used >= self.limit * 1.5

        # Other estimates remain advisory.
        return False

def count_utf16(text: str) -> int:
    return len( text.encode("utf-16-le") ) // 2

def count_instagram(text: str) -> int:
    # Buffer counts each line break as two units.
    normalized = ( text.replace("\r\n", "\n") .replace("\r", "\n") )
    return ( count_utf16(normalized) + normalized.count("\n") )


def count_linkedin(text: str) -> tuple[int, bool]:
    # LinkedIn counts recognized URLs as 24 units.
    # URL detection is approximate, so we won't treat results containing URLs as exact.
    matches = list( URL_PATTERN.finditer(text) )

    if not matches:
        return count_utf16(text), True

    total = 0
    position = 0

    for match in matches:
        total += count_utf16( text[position:match.start()] )
        total += 24
        position = match.end()

    total += count_utf16( text[position:] )

    return total, False


def check_channel_characters( text: str, channel: dict ) -> ChannelCharacterCheck:
    channel_id = channel["id"]

    channel_name = ( channel.get("name") or "Unnamed channel" )
    service = str( channel.get("service") or "unknown" ).lower()

    used = None
    limit = None
    exact = True
    note = ""

    if service in CHARACTER_LIMITS:
        limit = CHARACTER_LIMITS[service]
        used = count_utf16(text)
    
    elif service == "instagram":
        limit = 2196
        used = count_instagram(text)
    
    elif service == "linkedin":
        limit = 3000
        used, exact = count_linkedin(text)
        if not exact:
            note = "URL counting is estimated."
    
    elif service == "bluesky":
        limit = 300
        # ASCII without URLs can be counted exactly.
        # For complex Unicode, Python's len() is only an estimate of grapheme clusters.
        used = len(text)
        exact = ( text.isascii() and URL_PATTERN.search(text) is None )
        if not exact:
            note = ( "Bluesky character count is estimated for this text." )

    elif service == "twitter":
        # We don't know the user's X subscription tier from the current channel data.
        exact = False
        note = ( "X allows 280 or 25,000 characters depending on the account tier." )

    elif service == "mastodon":
        # The limit depends on the connected server.
        exact = False
        note = ( "Mastodon limits depend on the connected server." )

    else:
        exact = False
        note = ( "No local character limit available." )

    return ChannelCharacterCheck(
        channel_id=channel_id,
        channel_name=channel_name,
        service=service,
        used=used,
        limit=limit,
        exact=exact,
        note=note,
    )

def check_selected_channels( text: str, channels: list[dict] ) -> list[ChannelCharacterCheck]:
    return [
        check_channel_characters( text, channel )
        for channel in channels
    ]