from django.conf import settings

from parlays.seo import PAGE_SEO, SITE_NAME

LEGAL_DISCLAIMERS = [
    "This platform does not accept wagers or hold funds. For informational and coordination purposes only.",
    "Users are responsible for independently placing any sportsbook wagers. Estimated payouts are not guaranteed and are for planning only.",
]


def legal_disclaimer(request):
    return {"legal_disclaimers": LEGAL_DISCLAIMERS}


def site_settings(request):
    return {
        "site_url": settings.SITE_URL,
        "plausible_domain": settings.PLAUSIBLE_DOMAIN,
        "google_analytics_id": settings.GOOGLE_ANALYTICS_ID,
        "host_code_ttl_hours": getattr(settings, "HOST_CODE_TTL_HOURS", 72),
        "site_name": SITE_NAME,
    }


def seo_fallback(request):
    """Default copy if a template renders without an explicit ``meta`` object."""
    landing = PAGE_SEO["landing"]
    return {
        "seo_fallback_title": landing.title,
        "seo_fallback_description": landing.description,
    }
