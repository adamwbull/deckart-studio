"""Which image hosts Tabletop Simulator can actually download.

TTS runs on an old Unity TLS stack that cannot complete a handshake with servers that only offer an
ECDSA certificate. cards.scryfall.io is such a host (verified: RSA and ECDHE-RSA handshakes are refused),
so its images must be mirrored to Steam Cloud before other players - or TTS itself - can load them.
"""
from urllib.parse import urlparse

from deckart_studio.image_source import is_remote_url

TTS_UNREACHABLE_HOSTS = {"cards.scryfall.io"}


def is_tts_unreachable(url: str) -> bool:
    return is_remote_url(url) and urlparse(url).hostname in TTS_UNREACHABLE_HOSTS


def describe_unreachable_hosts() -> str:
    return ", ".join(sorted(TTS_UNREACHABLE_HOSTS))
