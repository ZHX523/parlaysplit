from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from django.utils import timezone

from parlays.models import Parlay


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
            "parlays:create",
            "parlays:host_lookup",
        ]

    def location(self, item):
        return reverse(item)


class PublicParlaySitemap(SiteUrlMixin, Sitemap):
    changefreq = "daily"
    priority = 0.6

    def items(self):
        now = timezone.now()
        return (
            Parlay.objects.filter(is_public=True, host_code_expires_at__gt=now)
            .order_by("-updated_at")
        )

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse("parlays:detail", kwargs={"pk": obj.pk})
