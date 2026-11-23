"""Parsing helpers: JSON record payloads and HTML link/text extraction (stdlib only)."""

import json
from html.parser import HTMLParser
from urllib.parse import urljoin

from .sources import is_allowed_url


def parse_json_records(text: str) -> list:
    """Parse a JSON payload that is either a list of records or {"schemes": [...]}.

    Non-dict items are dropped. Raises ValueError on invalid JSON or wrong shape.
    """
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as e:
        raise ValueError(f"invalid JSON: {e}") from e
    if isinstance(data, dict) and isinstance(data.get("schemes"), list):
        data = data["schemes"]
    if not isinstance(data, list):
        raise ValueError("expected a JSON list or an object with a 'schemes' list")
    return [item for item in data if isinstance(item, dict)]


class _HtmlExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.text_parts = []
        self.links = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._skip_depth == 0:
            self.text_parts.append(data)


def parse_html(html: str, base_url: str) -> dict:
    """Return {"title", "text", "links"} from an HTML page.

    title and text are whitespace-collapsed. links are absolute URLs that pass
    is_allowed_url; duplicates are removed while keeping first-seen order.
    """
    parser = _HtmlExtractor()
    parser.feed(html or "")
    parser.close()

    title = " ".join("".join(parser.title_parts).split())
    text = " ".join("".join(parser.text_parts).split())

    links = []
    seen = set()
    for href in parser.links:
        absolute = urljoin(base_url, href.strip())
        if absolute in seen or not is_allowed_url(absolute):
            continue
        seen.add(absolute)
        links.append(absolute)

    return {"title": title, "text": text, "links": links}
