"""Audit title, description, and canonical tags on indexable pages."""
import re
import sys

from django.test import Client

from parlays.models import Parlay

client = Client(HTTP_HOST="localhost:8000")

PATHS = [
    "/",
    "/about/",
    "/create/",
    "/my-parlay/",
]


def audit(path: str) -> dict:
    html = client.get(path).content.decode()
    title_tag = re.search(r"<title[^>]*>([^<]*)</title>", html)
    meta_desc = re.search(r'<meta name="description" content="([^"]*)"', html)
    canonical = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    robots = re.search(r'<meta name="robots" content="([^"]+)"', html)
    return {
        "path": path,
        "title_tag": title_tag.group(1) if title_tag else None,
        "meta_description": meta_desc.group(1) if meta_desc else None,
        "canonical": canonical.group(1) if canonical else None,
        "robots": robots.group(1) if robots else None,
    }


rows = [audit(p) for p in PATHS]

parlay = Parlay.objects.filter(is_public=True).first()
if parlay:
    rows.append(audit(f"/p/{parlay.pk}/"))
    if parlay.host_code:
        rows.append(audit(f"/host/{parlay.host_code}/"))

titles = set()
descriptions = set()
failed = False

for row in rows:
    print(row["path"])
    print("  <title>:     ", row["title_tag"] or "MISSING")
    print("  description: ", row["meta_description"] or "MISSING")
    print("  canonical:   ", row["canonical"] or "MISSING")
    if row["robots"]:
        print("  robots:      ", row["robots"])
    if not row["title_tag"] or not row["meta_description"] or not row["canonical"]:
        failed = True
    if row["title_tag"] in titles:
        print("  DUPLICATE <title>")
        failed = True
    if row["meta_description"] in descriptions:
        print("  DUPLICATE description")
        failed = True
    titles.add(row["title_tag"])
    descriptions.add(row["meta_description"])
    print()

if failed:
    sys.exit(1)
print("SEO metadata checks passed.")
