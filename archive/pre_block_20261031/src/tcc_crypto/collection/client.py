"""Collection: client."""

from __future__ import annotations

import json
import time
from http.client import IncompleteRead, RemoteDisconnected
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tcc_crypto.collection.config import CollectionConfig


def request_json(
    url: str,
    parameters: Mapping[str, object],
    *,
    timeout_seconds: int,
    max_retries: int,
) -> object:
    """Request public Binance JSON with bounded transient-error retries."""
    request_url = f"{url}?{urlencode(parameters)}"
    for attempt in range(max_retries + 1):
        request = Request(
            request_url,
            headers={"User-Agent": "tcc-crypto-research/0.1"},
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return json.load(response)
        except HTTPError as error:
            is_transient = error.code == 429 or 500 <= error.code < 600
            if is_transient and attempt < max_retries:
                retry_after = error.headers.get("Retry-After")
                delay_seconds = (
                    float(retry_after)
                    if retry_after is not None
                    else min(2**attempt, 30)
                )
                time.sleep(delay_seconds)
                continue
            response_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Binance returned HTTP {error.code} for {url}: {response_body}"
            ) from error
        except URLError as error:
            if attempt < max_retries:
                time.sleep(min(2**attempt, 30))
                continue
            raise RuntimeError(
                f"Could not reach Binance at {url}: {error.reason}"
            ) from error
        except (IncompleteRead, RemoteDisconnected) as error:
            if attempt < max_retries:
                time.sleep(min(2**attempt, 30))
                continue
            raise RuntimeError(
                f"Binance connection was interrupted for {url}: {error}"
            ) from error

    raise RuntimeError(f"Request retry loop ended unexpectedly for {url}.")


PageRequester = Callable[[Mapping[str, object]], object]


def _default_page_requester(config: CollectionConfig) -> PageRequester:
    endpoint = f"{config.base_url}{config.kline_path}"

    def requester(parameters: Mapping[str, object]) -> object:
        return request_json(
            endpoint,
            parameters,
            timeout_seconds=config.request_timeout_seconds,
            max_retries=config.max_retries,
        )

    return requester
