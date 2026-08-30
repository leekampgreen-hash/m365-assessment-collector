"""Microsoft documentation research fetcher."""
from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parent / "knowledge" / "cache"
_ALLOWED_DOMAINS = {"learn.microsoft.com", "docs.microsoft.com"}
_PII_PATTERNS = (
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"\b(?:John|Jane|Alice|Bob)\b(?:['’]s)?", re.IGNORECASE),
    re.compile(r"\b(?:Mr|Mrs|Ms|Dr)\.\s+[A-Z][a-z]+\b"),
)


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.depth = 0
        self.skip_depth = 0
        self.main_depth = 0
        self.found_main = False
        self._skip_tags = {"script", "style", "nav", "footer", "header", "aside", "form"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in self._skip_tags:
            self.skip_depth += 1
        if tag in {"main", "article"} and not self.found_main:
            self.found_main = True
            self.main_depth = self.depth
        self.depth += 1
        if tag == "br":
            self.parts.append(" ")
        if attrs_dict.get("role") in {"navigation", "contentinfo"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        self.depth = max(0, self.depth - 1)
        if tag in self._skip_tags or tag in {"main", "article"}:
            self.skip_depth = max(0, self.skip_depth - 1)

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and (not self.found_main or self.depth > self.main_depth):
            self.parts.append(data)


def _sanitize(text: str) -> str:
    for pattern in _PII_PATTERNS:
        text = pattern.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_allowed(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").casefold().rstrip(".")
    return hostname in _ALLOWED_DOMAINS


def get_curated_urls(intent: str, topics: list[str]) -> list[str]:
    products_dir = Path(__file__).resolve().parent / "knowledge" / "products"
    urls: list[str] = []
    wanted = {topic.casefold() for topic in topics}
    for path in sorted(products_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key, topic in data.get("topics", {}).items():
            if key.casefold() in wanted:
                for url in topic.get("docs_urls", []):
                    if _is_allowed(url) and url not in urls:
                        urls.append(url)
                    if len(urls) >= 3:
                        return urls
    return urls


class _SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._link: str | None = None
        self._title: list[str] = []
        self._in_result = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and "result__a" in (attributes.get("class") or ""):
            href = attributes.get("href") or ""
            parsed = urlparse(href)
            if parsed.path == "/l/":
                href = parse_qs(parsed.query).get("uddg", [""])[0]
            href = unquote(html.unescape(href))
            if _is_allowed(href):
                self._link, self._title, self._in_result = href, [], True

    def handle_data(self, data: str) -> None:
        if self._in_result:
            self._title.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result and self._link:
            self.results.append({"title": re.sub(r"\s+", " ", "".join(self._title)).strip(), "url": self._link})
            self._link, self._in_result = None, False


def fetch_page_content(url: str, timeout: int = 10) -> str:
    if not _is_allowed(url):
        return ""
    cache_path = _CACHE_DIR / (hashlib.md5(url.encode(), usedforsecurity=False).hexdigest() + ".json")
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if datetime.fromisoformat(cached["expires_at"]) > datetime.now(timezone.utc):
            return str(cached.get("content", ""))
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("Cache read failed: %s", exc)
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as response:
            source = response.read().decode("utf-8", errors="replace")
        parser = _TextParser()
        parser.feed(source)
        content = re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()[:800]
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            now = datetime.now(timezone.utc)
            cache_path.write_text(json.dumps({"url": url, "fetched_at": now.isoformat(), "expires_at": (now + timedelta(days=7)).isoformat(), "content": content}), encoding="utf-8")
        except Exception as exc:
            logger.warning("Cache write failed: %s", exc)
        return content
    except Exception as exc:
        logger.warning("Microsoft docs page fetch failed: %s", exc)
        return ""


def research(intent: str) -> str:
    topics = [word for word in re.findall(r"[a-z0-9_]+", intent.casefold())]
    output = ""
    for url in get_curated_urls(intent, topics)[:2]:
        content = fetch_page_content(url)
        if content:
            output += f"Source: {url}\n{content}\n\n"
    return output[:1000]


def extract_intent(message: str, tools_used: list[str]) -> str:
    intent = _sanitize(message)
    intent = re.sub(r"\b(?:please|could you|can you|tell me|show me|I need to know)\b", " ", intent, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", intent).strip()
