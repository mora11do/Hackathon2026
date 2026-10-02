#!/usr/bin/env python3
"""
jobscraper.py - a polite, robots.txt-respecting job listing collector.

Install:  pip install requests beautifulsoup4 protego

Examples:
  python jobscraper.py -q "python developer" --sources remoteok remotive
  python jobscraper.py -q engineer --greenhouse stripe airbnb --lever netflix
  python jobscraper.py -q analyst --html-config my_site.json --out jobs.csv

Every request (APIs and HTML pages alike) goes through PoliteFetcher, which:
  * fetches and caches robots.txt per host and refuses disallowed URLs
  * honours Crawl-delay and enforces a minimum delay per host
  * backs off on 429/503 (honouring Retry-After)
  * identifies itself with a real User-Agent (edit USER_AGENT below!)
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from protego import Protego

# Identify yourself honestly, with a way for site owners to reach you.
USER_AGENT = "HackathonJobBot/0.1 (+https://github.com/mora11do/Hackathon2026)"
log = logging.getLogger("jobscraper")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Job:
    source: str
    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    posted: str = ""
    salary: str = ""
    description: str = ""
    lat: float | None = None
    lon: float | None = None
    remote: bool = False


class Blocked(Exception):
    """Raised when robots.txt disallows a URL."""


# --------------------------------------------------------------------------- #
# robots.txt handling
# --------------------------------------------------------------------------- #
class RobotsGate:
    """Per-host robots.txt cache.

    Follows RFC 9309: 4xx on robots.txt => no restrictions;
    5xx / network failure => assume everything is disallowed.
    Uses Protego, which understands * and $ wildcards (urllib.robotparser doesn't).
    """

    def __init__(self, session: requests.Session, user_agent: str):
        self.session = session
        self.ua = user_agent
        self._cache: dict[str, tuple[str, Protego | None]] = {}

    def _rules(self, url: str) -> tuple[str, Protego | None]:
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin in self._cache:
            return self._cache[origin]
        try:
            r = self.session.get(f"{origin}/robots.txt", timeout=10)
            if r.status_code == 200:
                result = ("rules", Protego.parse(r.text))
            elif 400 <= r.status_code < 500:
                result = ("allow", None)
            else:
                result = ("deny", None)
        except requests.RequestException:
            result = ("deny", None)
        self._cache[origin] = result
        log.debug("robots.txt for %s -> %s", origin, result[0])
        return result

    def allowed(self, url: str) -> bool:
        mode, rules = self._rules(url)
        if mode == "allow":
            return True
        if mode == "deny":
            return False
        return rules.can_fetch(url, self.ua)

    def crawl_delay(self, url: str) -> float:
        mode, rules = self._rules(url)
        if mode != "rules":
            return 0.0
        return float(rules.crawl_delay(self.ua) or 0)


class PoliteFetcher:
    def __init__(self, user_agent: str = USER_AGENT, min_delay: float = 2.0):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.robots = RobotsGate(self.session, user_agent)
        self.min_delay = min_delay
        self._last_hit: dict[str, float] = {}

    def get(self, url: str, **kwargs) -> requests.Response:
        if not self.robots.allowed(url):
            raise Blocked(f"robots.txt disallows {url}")

        host = urlparse(url).netloc
        delay = max(self.min_delay, self.robots.crawl_delay(url))

        for attempt in range(3):
            wait = self._last_hit.get(host, 0) + delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                resp = self.session.get(url, timeout=20, **kwargs)
            except requests.RequestException as exc:
                log.warning("request error (%s), attempt %d", exc, attempt + 1)
                self._last_hit[host] = time.monotonic()
                time.sleep(2 ** (attempt + 1))
                continue
            self._last_hit[host] = time.monotonic()
            if resp.status_code in (429, 503):
                retry = resp.headers.get("Retry-After", "")
                pause = int(retry) if retry.isdigit() else 2 ** (attempt + 2)
                log.warning("%s from %s; sleeping %ss", resp.status_code, host, pause)
                time.sleep(min(pause, 120))
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"giving up on {url}")


# --------------------------------------------------------------------------- #
# Source adapters
# --------------------------------------------------------------------------- #
def _matches(query: str, *texts: str) -> bool:
    """Client-side keyword filter: every query word must appear somewhere."""
    hay = " ".join(texts).lower()
    return all(word in hay for word in query.lower().split())


class RemoteOK:
    """https://remoteok.com/api - free; their terms require linking back to the listing."""
    name = "remoteok"

    def fetch(self, f: PoliteFetcher, query: str, limit: int) -> Iterator[Job]:
        data = f.get("https://remoteok.com/api").json()
        n = 0
        for item in data:
            if not isinstance(item, dict) or "position" not in item:
                continue  # first element is a legal notice
            if not _matches(query, item.get("position", ""), " ".join(item.get("tags", []))):
                continue
            lo, hi = item.get("salary_min"), item.get("salary_max")
            yield Job(
                source=self.name,
                title=item["position"],
                company=item.get("company", ""),
                location=item.get("location", ""),
                url=item.get("url", ""),
                posted=item.get("date", ""),
                salary=f"{lo}-{hi}" if lo and hi else "",
                description=BeautifulSoup(item.get("description", ""), "html.parser").get_text(" ", strip=True),
            )
            n += 1
            if n >= limit:
                return


class Remotive:
    """https://remotive.com/api/remote-jobs - free public API (rate-limit yourself)."""
    name = "remotive"

    def fetch(self, f: PoliteFetcher, query: str, limit: int) -> Iterator[Job]:
        data = f.get(f"https://remotive.com/api/remote-jobs?search={quote_plus(query)}&limit={limit}").json()
        for item in data.get("jobs", [])[:limit]:
            yield Job(
                source=self.name,
                title=item.get("title", ""),
                company=item.get("company_name", ""),
                location=item.get("candidate_required_location", ""),
                url=item.get("url", ""),
                posted=item.get("publication_date", ""),
                salary=item.get("salary", ""),
                description=BeautifulSoup(item.get("description", ""), "html.parser").get_text(" ", strip=True),
            )


class Greenhouse:
    """Public job-board API used by thousands of companies: boards-api.greenhouse.io"""

    def __init__(self, board: str):
        self.board = board
        self.name = f"greenhouse:{board}"

    def fetch(self, f: PoliteFetcher, query: str, limit: int) -> Iterator[Job]:
        data = f.get(f"https://boards-api.greenhouse.io/v1/boards/{self.board}/jobs?content=true").json()
        n = 0
        for item in data.get("jobs", []):
            if not _matches(query, item.get("title", "")):
                continue
            yield Job(
                source=self.name,
                title=item["title"],
                company=self.board,
                location=(item.get("location") or {}).get("name", ""),
                url=item.get("absolute_url", ""),
                posted=item.get("updated_at", ""),
            )
            n += 1
            if n >= limit:
                return


class Lever:
    """Public postings API used by many companies: api.lever.co"""

    def __init__(self, company: str):
        self.company = company
        self.name = f"lever:{company}"

    def fetch(self, f: PoliteFetcher, query: str, limit: int) -> Iterator[Job]:
        data = f.get(f"https://api.lever.co/v0/postings/{self.company}?mode=json").json()
        n = 0
        for item in data:
            if not _matches(query, item.get("text", "")):
                continue
            cats = item.get("categories") or {}
            ts = item.get("createdAt")
            posted = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat() if ts else ""
            yield Job(
                source=self.name,
                title=item["text"],
                company=self.company,
                location=cats.get("location", ""),
                url=item.get("hostedUrl", ""),
                posted=posted,
                description=item.get("descriptionPlain", ""),
            )
            n += 1
            if n >= limit:
                return


class ConfigurableHTML:
    """Scrape any server-rendered listing page described by a JSON config.

    Example config:
    {
      "name": "examplejobs",
      "url": "https://jobs.example.com/search?q={query}&page={page}",
      "max_pages": 3,
      "item": "div.job-card",
      "fields": {
        "title": "h2 a", "company": ".company", "location": ".location",
        "url": "h2 a@href", "posted": "time@datetime"
      }
    }
    Use "selector@attr" to read an attribute instead of text.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.name = cfg["name"]

    @staticmethod
    def _extract(node, spec: str, base: str) -> str:
        sel, _, attr = spec.partition("@")
        el = node.select_one(sel) if sel else node
        if el is None:
            return ""
        if attr:
            val = el.get(attr, "")
            return urljoin(base, val) if attr == "href" else val
        return el.get_text(" ", strip=True)

    def fetch(self, f: PoliteFetcher, query: str, limit: int) -> Iterator[Job]:
        n = 0
        for page in range(1, int(self.cfg.get("max_pages", 1)) + 1):
            url = self.cfg["url"].format(query=quote_plus(query), page=page)
            soup = BeautifulSoup(f.get(url).text, "html.parser")
            cards = soup.select(self.cfg["item"])
            if not cards:
                return
            for card in cards:
                vals = {k: self._extract(card, spec, url) for k, spec in self.cfg["fields"].items()}
                valid = {k: v for k, v in vals.items() if k in {fl.name for fl in fields(Job)}}
                yield Job(source=self.name, **valid)
                n += 1
                if n >= limit:
                    return


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
BUILTIN = {"remoteok": RemoteOK, "remotive": Remotive}


def write_output(jobs: list[Job], path: str) -> None:
    rows = [asdict(j) for j in jobs]
    if path.endswith(".json"):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2, ensure_ascii=False)
    else:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=[fl.name for fl in fields(Job)])
            w.writeheader()
            w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Polite job listing scraper")
    ap.add_argument("-q", "--query", required=True, help="keywords, e.g. 'python developer'")
    ap.add_argument("--sources", nargs="*", default=[], choices=BUILTIN, help="built-in API sources")
    ap.add_argument("--greenhouse", nargs="*", default=[], metavar="BOARD", help="Greenhouse board tokens")
    ap.add_argument("--lever", nargs="*", default=[], metavar="COMPANY", help="Lever company slugs")
    ap.add_argument("--html-config", nargs="*", default=[], metavar="JSON", help="HTML site config files")
    ap.add_argument("--limit", type=int, default=50, help="max jobs per source")
    ap.add_argument("--delay", type=float, default=2.0, help="min seconds between requests per host")
    ap.add_argument("--geocode", action="store_true", help="add lat/lon/remote so the site can filter by distance")
    ap.add_argument("--out", default="jobs.csv", help="output .csv or .json")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    adapters = [BUILTIN[s]() for s in args.sources]
    adapters += [Greenhouse(b) for b in args.greenhouse]
    adapters += [Lever(c) for c in args.lever]
    for path in args.html_config:
        with open(path, encoding="utf-8") as fh:
            adapters.append(ConfigurableHTML(json.load(fh)))
    if not adapters:
        ap.error("choose at least one source (--sources, --greenhouse, --lever, --html-config)")

    fetcher = PoliteFetcher(min_delay=args.delay)
    seen: set[str] = set()
    results: list[Job] = []

    for adapter in adapters:
        log.info("fetching from %s", adapter.name)
        try:
            for job in adapter.fetch(fetcher, args.query, args.limit):
                key = job.url or f"{job.company}|{job.title}|{job.location}"
                if key not in seen:
                    seen.add(key)
                    results.append(job)
        except Blocked as exc:
            log.error("SKIPPED %s: %s", adapter.name, exc)
        except Exception as exc:  # keep going if one source breaks
            log.error("FAILED %s: %s", adapter.name, exc)

    if args.geocode:
        from geocode import enrich
        enrich(results, fetcher)

    write_output(results, args.out)
    log.info("wrote %d jobs to %s", len(results), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
