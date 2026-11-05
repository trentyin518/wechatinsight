"""URL normalization used for article de-duplication.

Two links that point at the same article should collapse to one stored article.
We never dedupe by title alone; normalized URL (plus provider id) is the key.
"""

from __future__ import annotations

from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

# Query params that vary per share/tracking but not by article identity.
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"from", "scene", "isappinstalled", "clicktime", "enterid", "chksm", "ascene"}


def normalize_article_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    # Drop default ports.
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    kept: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.lower()
        if lower in _TRACKING_KEYS or any(lower.startswith(p) for p in _TRACKING_PREFIXES):
            continue
        kept.append((key, value))
    query = urlencode(sorted(kept))

    path = parts.path or "/"
    path = path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, query, ""))


def extract_wechat_biz(url: str) -> str | None:
    """Return the stable ``__biz`` account id from a WeChat article URL.

    ``__biz`` identifies the official account and is stable across its articles,
    which makes it a reliable provider account key (unlike display names).
    """
    if not url:
        return None
    parts = urlsplit(url)
    if "mp.weixin.qq.com" not in parts.netloc:
        return None
    values = parse_qs(parts.query).get("__biz")
    return values[0] if values else None
