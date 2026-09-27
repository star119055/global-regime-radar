from __future__ import annotations

from collections.abc import Callable
import json
from urllib.request import Request, urlopen

FetchBytes = Callable[[str], bytes]
PostJsonBytes = Callable[[str, dict[str, object]], bytes]


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


def post_json_bytes(
    url: str,
    payload: dict[str, object],
    timeout_seconds: float = 30.0,
) -> bytes:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": "global-regime-radar/0.1 (+https://github.com/star119055/global-regime-radar)",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()
