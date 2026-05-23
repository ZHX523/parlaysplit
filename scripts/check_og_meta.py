"""Verify Open Graph tags on a public parlay page."""
import re
import sys

from django.test import Client

from parlays.models import Parlay

parlay = Parlay.objects.filter(is_public=True).prefetch_related("legs", "participants").first()
if not parlay:
    print("NO_PUBLIC_PARLAY")
    sys.exit(1)

client = Client(HTTP_HOST="localhost:8000")
page = client.get(f"/p/{parlay.pk}/")
html = page.content.decode()

print("page_status", page.status_code)


def find_meta(prop: str, *, name_attr: str = "property") -> str | None:
    patterns = [
        rf'<meta[^>]+{name_attr}="{re.escape(prop)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+{name_attr}="{re.escape(prop)}"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return None


checks = {
    "og:title": find_meta("og:title"),
    "og:description": find_meta("og:description"),
    "og:url": find_meta("og:url"),
    "og:image": find_meta("og:image"),
    "og:image:url": find_meta("og:image:url"),
    "og:type": find_meta("og:type"),
    "twitter:card": find_meta("twitter:card", name_attr="name"),
    "twitter:image": find_meta("twitter:image", name_attr="name"),
}

for key, value in checks.items():
    status = "ok" if value else "MISSING"
    print(f"{key}: {status}" + (f" -> {value[:80]}" if value else ""))

img = client.get(f"/p/{parlay.pk}/og.png")
print(
    "og.png:",
    img.status_code,
    img.get("Content-Type"),
    "bytes",
    len(img.content),
    "cache",
    img.get("Cache-Control"),
)
if img.content[:8] != b"\x89PNG\r\n\x1a\n":
    sys.exit("invalid_png")

if not checks["og:image"] and not checks["og:image:url"]:
    sys.exit("no_preview_image_meta")
