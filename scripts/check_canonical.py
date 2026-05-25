"""Audit canonical URLs and noindex directives."""
import re
import sys

from django.test import Client, RequestFactory

from parlays.models import Parlay
from parlays.seo import parlay_public_url

client = Client(HTTP_HOST="localhost:8000")
request = RequestFactory().get("/")


def audit(path: str) -> dict:
    response = client.get(path)
    html = response.content.decode()
    canonical = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    robots = re.search(r'<meta name="robots" content="([^"]+)"', html)
    og_url = re.search(r'<meta property="og:url" content="([^"]+)"', html)
    return {
        "path": path,
        "status": response.status_code,
        "canonical": canonical.group(1) if canonical else None,
        "robots": robots.group(1) if robots else None,
        "og_url": og_url.group(1) if og_url else None,
    }


rows = [
    audit("/"),
    audit("/create/"),
    audit("/my-parlay/"),
]

parlay = Parlay.objects.filter(is_public=True).first()
if not parlay:
    print("NO_PUBLIC_PARLAY")
    sys.exit(1)

expected_public = parlay_public_url(request, parlay)
rows.append(audit(f"/p/{parlay.slug}/"))

host_row = None
if parlay.host_code:
    host_row = audit(f"/host/{parlay.host_code}/")

robots_txt = client.get("/robots.txt").content.decode()
print("robots.txt:")
for line in robots_txt.strip().splitlines():
    if line.strip():
        print(" ", line)

failed = False
for row in rows:
    print(f"\n{row['path']} ({row['status']})")
    print("  canonical:", row["canonical"] or "MISSING")
    print("  og:url:   ", row["og_url"] or "MISSING")
    print("  robots:   ", row["robots"] or "MISSING")
    if not row["canonical"]:
        failed = True
    if row["canonical"] != row["og_url"]:
        print("  MISMATCH canonical vs og:url")
        failed = True
    if row["path"].startswith("/p/") or row["path"] == "/my-parlay/":
        if not row["robots"] or "noindex" not in row["robots"]:
            print("  parlay pages should be noindex")
            failed = True
    elif row["robots"]:
        print("  static pages should not be noindex")
        failed = True

if host_row:
    print(f"\n{host_row['path']} ({host_row['status']})")
    print("  canonical:", host_row["canonical"] or "MISSING")
    print("  og:url:   ", host_row["og_url"] or "MISSING")
    print("  robots:   ", host_row["robots"] or "MISSING")
    if host_row["canonical"] != expected_public:
        print("  host canonical should be public parlay URL")
        failed = True
    if not host_row["robots"] or "noindex" not in host_row["robots"]:
        print("  host page should be noindex")
        failed = True

og = client.get(f"/p/{parlay.pk}/og.png")
print(f"\nog.png X-Robots-Tag: {og.get('X-Robots-Tag') or 'MISSING'}")
if og.get("X-Robots-Tag") != "noindex":
    failed = True

if "Disallow: /host/" not in robots_txt:
    failed = True
if "Disallow: /p/" not in robots_txt:
    failed = True

if failed:
    sys.exit(1)
print("\nCanonical / noindex checks passed.")
