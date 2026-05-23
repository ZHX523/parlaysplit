from django.conf import settings


LEGAL_DISCLAIMERS = [
    "This platform does not accept wagers or hold funds.",
    "For informational and coordination purposes only.",
    "Users are responsible for independently placing any sportsbook wagers.",
    "Estimated payouts are not guaranteed and are for planning only.",
]


def legal_disclaimer(request):
    return {"legal_disclaimers": LEGAL_DISCLAIMERS}


def site_settings(request):
    return {
        "site_url": settings.SITE_URL,
        "plausible_domain": settings.PLAUSIBLE_DOMAIN,
    }
