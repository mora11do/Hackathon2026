"""geocode.py - adds lat/lon/remote to jobs so the site can filter by distance.

Uses Open-Meteo's free geocoding API (non-commercial use), called through the
same robots-checking, rate-limited fetcher, and cached in geocache.json.
"""
import json
import os
import re
from urllib.parse import quote_plus

REMOTE = re.compile(r"remote|anywhere|worldwide|work from home", re.I)
API = "https://geocoding-api.open-meteo.com/v1/search?count=5&language=en&format=json&name="


def _lookup(place, fetcher):
    city, *rest = [p.strip() for p in place.split(",")]
    try:
        results = fetcher.get(API + quote_plus(city)).json().get("results", [])
    except Exception:
        return None
    hint = " ".join(rest).lower()
    for r in results:  # prefer a result whose state/country appears in the text
        if hint and (r.get("admin1", "").lower() in hint or r.get("country", "").lower() in hint):
            return [r["latitude"], r["longitude"]]
    return [results[0]["latitude"], results[0]["longitude"]] if results else None


def enrich(jobs, fetcher, cache_path="geocache.json"):
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    for j in jobs:
        parts = [p.strip() for p in re.split(r"[;|]", j.location or "") if p.strip()]
        j.remote = j.source in ("remoteok", "remotive") or any(REMOTE.search(p) for p in parts)
        place = next((p for p in parts if not REMOTE.search(p)), "")
        if not place:
            continue
        if place not in cache:
            cache[place] = _lookup(place, fetcher)
        if cache[place]:
            j.lat, j.lon = cache[place]
    json.dump(cache, open(cache_path, "w"))
