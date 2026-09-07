import json
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_USER_AGENT = "DeckArtStudio/1.0 (personal use)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)
RETRY_STATUSES = {429, 500, 502, 503}
RETRY_BACKOFF_SECONDS = 3.0


def fetch_bytes(url: str, user_agent: str = DEFAULT_USER_AGENT, timeout: float = 30.0, retries: int = 6,
                method: str = "GET", body: bytes | None = None, content_type: str | None = None,
                headers: dict | None = None) -> bytes:
    request = build_request(url, user_agent, method, body, content_type, headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in RETRY_STATUSES or attempt == retries - 1:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}")


def build_request(url: str, user_agent: str, method: str, body: bytes | None,
                  content_type: str | None, extra_headers: dict | None = None) -> urllib.request.Request:
    headers = {"User-Agent": user_agent, "Accept": "application/json, image/*, */*"}
    if content_type:
        headers["Content-Type"] = content_type
    if extra_headers:
        headers.update(extra_headers)
    return urllib.request.Request(url, data=body, headers=headers, method=method)


def fetch_json(url: str, user_agent: str = DEFAULT_USER_AGENT, body: dict | None = None,
               timeout: float = 30.0, headers: dict | None = None) -> dict:
    encoded = json.dumps(body).encode("utf-8") if body is not None else None
    method = "POST" if body is not None else "GET"
    content_type = "application/json" if body is not None else None
    return json.loads(fetch_bytes(url, user_agent, timeout=timeout, method=method, body=encoded,
                                  content_type=content_type, headers=headers))


def download_file(url: str, destination: Path, user_agent: str = DEFAULT_USER_AGENT) -> Path:
    destination = Path(destination)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(fetch_bytes(url, user_agent))
    return destination
