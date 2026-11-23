"""Link verification: classifies a URL without ever marking a network failure as BROKEN."""

from urllib.parse import urlparse

from .fetch import fetch_url
from .sources import is_allowed_url


def check_link(url: str, fetcher=None) -> dict:
    """Check one URL and return a verdict dict.

    Verdicts: OK, BROKEN, REDIRECT_OFFSITE, UNABLE_TO_VERIFY.
    """
    if fetcher is None:
        fetcher = fetch_url

    try:
        parsed = urlparse(url)
        format_ok = bool(parsed.scheme and parsed.netloc)
        scheme_ok = parsed.scheme == "https"
    except Exception:
        format_ok = False
        scheme_ok = False
    domain_ok = is_allowed_url(url)

    report = {
        "url": url,
        "format_ok": format_ok,
        "scheme_ok": scheme_ok,
        "domain_ok": domain_ok,
        "final_url": None,
        "status": None,
        "verdict": None,
        "detail": None,
    }

    if not format_ok:
        report["verdict"] = "BROKEN"
        report["detail"] = "malformed URL (missing scheme or host)"
        return report
    if not scheme_ok:
        report["verdict"] = "BROKEN"
        report["detail"] = "scheme is not https"
        return report

    if not domain_ok:
        report["verdict"] = "NOT_ALLOWED_DOMAIN"
        report["detail"] = "host is not on the allowed official-source list"
        return report

    result = fetcher(url)
    report["final_url"] = result.final_url
    report["status"] = result.status

    if result.error is not None and result.status is None:
        # DNS, timeout, TLS, robots refusal, network: cannot tell if the link works.
        report["verdict"] = "UNABLE_TO_VERIFY"
        report["detail"] = result.error
        return report

    if result.status in (401, 403, 429):
        report["verdict"] = "UNABLE_TO_VERIFY"
        report["detail"] = f"HTTP {result.status}: access restricted or bot-blocked; not verified"
        return report

    if result.status is not None and result.status >= 400:
        report["verdict"] = "BROKEN"
        report["detail"] = f"HTTP {result.status}"
        return report

    if result.status is not None and 200 <= result.status < 400:
        final = result.final_url or url
        if not is_allowed_url(final):
            report["verdict"] = "REDIRECT_OFFSITE"
            report["detail"] = final
        else:
            report["verdict"] = "OK"
            report["detail"] = f"HTTP {result.status}"
        return report

    report["verdict"] = "UNABLE_TO_VERIFY"
    report["detail"] = result.error or "no HTTP status returned"
    return report


def check_links(urls, fetcher=None) -> list:
    """Run check_link over an iterable of URLs and return the list of verdict dicts."""
    return [check_link(u, fetcher=fetcher) for u in urls]
