"""Polite, cached, robots-aware HTTP fetching for official sources (stdlib only).

No network activity happens at import time. Every error is returned in the
FetchResult rather than raised.
"""

import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from .sources import is_allowed_url

USER_AGENT = "HAQfinder-research/0.1 (hackathon project; contact via repository)"
MIN_DELAY_SECONDS = 2.0
CACHE_TTL_SECONDS = 24 * 3600
MAX_BODY_BYTES = 2_000_000


@dataclass
class FetchResult:
    url: str
    final_url: Optional[str]
    status: Optional[int]
    body: Optional[str]
    error: Optional[str]


_cache = {}         # url -> (timestamp, FetchResult)
_robots_cache = {}  # host -> list of Disallow prefixes, or None if robots.txt unavailable
_last_request = {}  # host -> monotonic time of last request


def clear_cache() -> None:
    """Reset all module-level state (cache, robots rules, rate-limit timers)."""
    _cache.clear()
    _robots_cache.clear()
    _last_request.clear()


def _parse_robots(text: str) -> list:
    """Return Disallow prefixes that apply to the User-agent: * group."""
    rules = []
    in_star = False
    prev_was_agent = False
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if ":" not in line:
            prev_was_agent = False
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if not prev_was_agent:
                in_star = False
            if value == "*":
                in_star = True
            prev_was_agent = True
            continue
        prev_was_agent = False
        if key == "disallow" and in_star and value:
            rules.append(value)
    return rules


def _enforce_delay(host: str) -> None:
    """Sleep so that requests to the same host are at least MIN_DELAY_SECONDS apart."""
    last = _last_request.get(host)
    if last is not None:
        remaining = MIN_DELAY_SECONDS - (time.monotonic() - last)
        if remaining > 0:
            time.sleep(remaining)
    _last_request[host] = time.monotonic()


def _get_robots_rules(host: str, timeout: float) -> Optional[list]:
    """Fetch and cache robots.txt for a host. None means robots.txt could not be read."""
    if host in _robots_cache:
        return _robots_cache[host]
    robots_url = f"https://{host}/robots.txt"
    _enforce_delay(host)
    rules = None
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read(MAX_BODY_BYTES).decode("utf-8", errors="replace")
            rules = _parse_robots(text)
    except urllib.error.HTTPError as e:
        # A 4xx for robots.txt means no published restrictions.
        # A 5xx or other failure leaves rules as None (conservative).
        if 400 <= e.code < 500:
            rules = []
    except Exception:
        rules = None
    _robots_cache[host] = rules
    return rules


def _request(url: str, host: str, timeout: float) -> FetchResult:
    """Perform one rate-limited GET. Never raises."""
    _enforce_delay(host)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(MAX_BODY_BYTES).decode("utf-8", errors="replace")
            return FetchResult(
                url=url,
                final_url=resp.geturl(),
                status=resp.status,
                body=body,
                error=None,
            )
    except urllib.error.HTTPError as e:
        return FetchResult(url=url, final_url=url, status=e.code, body=None, error=str(e.reason))
    except urllib.error.URLError as e:
        return FetchResult(url=url, final_url=None, status=None, body=None,
                           error=str(e.reason) or "network error")
    except (socket.timeout, TimeoutError) as e:
        return FetchResult(url=url, final_url=None, status=None, body=None,
                           error=str(e) or "timeout")
    except ssl.SSLError as e:
        return FetchResult(url=url, final_url=None, status=None, body=None,
                           error=str(e) or "TLS error")
    except OSError as e:
        return FetchResult(url=url, final_url=None, status=None, body=None,
                           error=str(e) or "network error")
    except Exception as e:
        return FetchResult(url=url, final_url=None, status=None, body=None,
                           error=str(e) or "unexpected error")


def fetch_url(url: str, timeout: float = 15) -> FetchResult:
    """Fetch an official-source URL, honouring allow-list, cache, robots.txt and rate limits."""
    if not is_allowed_url(url):
        return FetchResult(url=url, final_url=None, status=None, body=None,
                           error="domain not allowed")

    cached = _cache.get(url)
    if cached is not None and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    host = (urllib.parse.urlparse(url).hostname or "").lower()
    rules = _get_robots_rules(host, timeout)
    if rules is None:
        return FetchResult(url=url, final_url=None, status=None, body=None,
                           error="robots.txt unavailable; not fetching")

    path = urllib.parse.urlparse(url).path or "/"
    if any(path.startswith(rule) for rule in rules):
        return FetchResult(url=url, final_url=None, status=None, body=None,
                           error="disallowed by robots.txt")

    result = _request(url, host, timeout)
    _cache[url] = (time.time(), result)
    return result
