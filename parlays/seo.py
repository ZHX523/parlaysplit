"""
Server-side SEO metadata for ParlaySplit.

Central registry of page titles, descriptions, canonical URLs, and robots directives.
Use ``build_page_meta`` / ``build_parlay_page_meta`` in views; templates render via
``templates/seo/head.html``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.urls import reverse
from meta.views import Meta

from parlays.models import Parlay

# Temporary parlay pages (72h) and host dashboards should not be indexed.
ROBOTS_NOINDEX = "noindex, nofollow"
SITE_NAME = "ParlaySplit"

DEFAULT_KEYWORDS = [
    "parlay",
    "sportsbook parlay",
    "group parlay",
    "shared parlay",
    "parlay splitter",
    "sports betting coordination",
    "estimate parlay payout",
]


@dataclass(frozen=True)
class PageSEO:
    """Static page metadata definition."""

    title: str
    description: str
    view_name: str
    robots: str | None = None
    keywords: tuple[str, ...] = field(default_factory=lambda: tuple(DEFAULT_KEYWORDS))
    og_type: str = "website"


# Registry — keep titles unique across the site.
PAGE_SEO: dict[str, PageSEO] = {
    "landing": PageSEO(
        title="ParlaySplit - Coordinate Group Parlays",
        description=(
            "Share sportsbook parlays, track participation, and estimate payouts with friends."
        ),
        view_name="parlays:landing",
    ),
    "create": PageSEO(
        title="Create a Group Parlay | ParlaySplit",
        description=(
            "Start a sportsbook parlay split: enter legs manually, upload a slip screenshot, "
            "or paste a share link. Set ownership and invite friends."
        ),
        view_name="parlays:create",
    ),
    "host_lookup": PageSEO(
        title="Find Your Parlay | ParlaySplit",
        description=(
            "Enter your host code to open and manage your group parlay dashboard."
        ),
        view_name="parlays:host_lookup",
        robots=None,
    ),
}


def absolute_url(request, path: str) -> str:
    """Build a stable absolute URL; prefer SITE_URL in production."""
    if not path.startswith("/"):
        path = f"/{path}"
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    if site_url and not settings.DEBUG:
        return f"{site_url}{path}"
    return request.build_absolute_uri(path)


def page_url(request, view_name: str, *args, **kwargs) -> str:
    return absolute_url(request, reverse(view_name, args=args, kwargs=kwargs))


def parlay_public_url(request, parlay: Parlay) -> str:
    """Canonical URL for a parlay (always the public join link)."""
    return page_url(request, "parlays:detail", slug=parlay.slug)


def default_page_meta(request) -> Meta:
    """Fallback when a view does not set page-specific metadata."""
    return build_page_meta(request, "landing")


def build_page_meta(
    request,
    page_key: str,
    *,
    url_kwargs: dict[str, Any] | None = None,
    **overrides,
) -> Meta:
    """Build django-meta ``Meta`` for a registered static page."""
    if page_key not in PAGE_SEO:
        raise KeyError(f"Unknown SEO page key: {page_key}")

    page = PAGE_SEO[page_key]
    url_kwargs = url_kwargs or {}

    meta_kwargs: dict[str, Any] = {
        "request": request,
        "title": overrides.get("title", page.title),
        "description": overrides.get("description", page.description),
        "url": overrides.get("url", page_url(request, page.view_name, **url_kwargs)),
        "keywords": list(overrides.get("keywords", page.keywords)),
        "object_type": overrides.get("og_type", page.og_type),
        "site_name": SITE_NAME,
        "twitter_type": "summary_large_image",
    }

    robots = overrides.get("robots", page.robots)
    if robots:
        meta_kwargs["extra_props"] = {"robots": robots}

    image = overrides.get("image")
    if image:
        meta_kwargs["image"] = image
        meta_kwargs["image_width"] = overrides.get("image_width", 1200)
        meta_kwargs["image_height"] = overrides.get("image_height", 630)

    return Meta(**meta_kwargs)


def build_parlay_page_meta(
    request,
    parlay: Parlay,
    *,
    is_host_view: bool = False,
) -> Meta:
    """Dynamic metadata for public and host parlay pages."""
    from parlays.opengraph import (
        parlay_opengraph_description,
        parlay_opengraph_image_url,
        parlay_opengraph_title,
    )

    title = parlay_opengraph_title(parlay)
    description = parlay_opengraph_description(parlay)
    if is_host_view:
        title = f"Manage · {title}"
        description = f"Host dashboard · {description}"

    meta_kwargs: dict[str, Any] = {
        "request": request,
        "title": title,
        "description": description,
        "url": parlay_public_url(request, parlay),
        "keywords": list(DEFAULT_KEYWORDS),
        "image": parlay_opengraph_image_url(request, parlay),
        "image_width": 1200,
        "image_height": 630,
        "object_type": "website",
        "site_name": SITE_NAME,
        "twitter_type": "summary_large_image",
        "extra_custom_props": [
            ("property", "og:image:alt", description),
        ],
    }
    meta_kwargs["extra_props"] = {"robots": ROBOTS_NOINDEX}

    return Meta(**meta_kwargs)
