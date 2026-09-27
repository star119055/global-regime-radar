from __future__ import annotations

from collections.abc import Callable
from urllib.request import Request, urlopen

FetchBytes = Callable[[str], bytes]


def fetch_bytes(url: str, timeout_seconds: float = 30.0) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "global-regime-radar/0.1 (+https://github.com/star119055/global-regime-radar)",
            "Accept": "*/*",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()
