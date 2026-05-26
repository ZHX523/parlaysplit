from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class SiteUrlMixin:
    """Build absolute sitemap URLs from SITE_URL in settings."""

    @property
    def protocol(self):
        return urlparse(settings.SITE_URL).scheme or "https"

    def get_domain(self, site=None):
        netloc = urlparse(settings.SITE_URL).netloc
        if netloc:
            return netloc
        if site is not None:
            return site.domain
        return "localhost"


class StaticViewSitemap(SiteUrlMixin, Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return [
            "parlays:landing",
            "parlays:about",
            "parlays:create",
            "parlays:host_lookup",
        ]

    def location(self, item):
        return reverse(item)
