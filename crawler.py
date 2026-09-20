"""Scrapy crawl of real + demo job boards -> TinyDB (NoSQL).

A single-file Scrapy "project": several Spiders + one Item pipeline. The
pipeline upserts documents into the TinyDB store, so re-crawling updates rows
instead of duplicating.

Sources (choose via `python run.py scrape --source <name>`):

  remoteok     live remote jobs from Remote OK's public JSON endpoint
               (their page HTML is a JS shell, so this is the crawlable form;
               robots.txt allows / and sets a crawl-delay of 1s).
  arbeitnow    live jobs from Arbeitnow's open API
               (robots.txt permits crawling; returns ~250 listings).
  demo         the offline demo board (demo_board.py) -- deterministic, no
               network needed; used to keep the repo self-contained and testable.

Run via `python run.py scrape --source remoteok`, or directly with
`scrapy runspider crawler.py`. `python run.py all` crawls remoteok by default.
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime

# Make the sibling skillscope/demo_board imports work under both
# `scrapy runspider` and `python run.py` entry points.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.http import Response

from demo_board import HOST, PORT, ensure_started, stop

USER_AGENT = ("SkillScope/1.1 (portfolio job-market demo; "
              "polite crawler, respects robots.txt)")

# f"{__name__}...." is both "__main__...." under `scrapy runspider` and
# "crawler...." when driven from run.py, so one pipeline setup covers both.
ITEM_PIPELINES = {f"{__name__}.TinyDBPipeline": 300}

REMOTE_OK_URL = "https://remoteok.com/api"
ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"

HTML_TAG_RE = re.compile(r"<[^>]+>")


def clean_html(text: str) -> str:
    """Strip tags + unescape entities from raw HTML descriptions.

    Some boards double-encode their descriptions (`&lt;h3&gt;`), so entities
    must be unescaped *before* tag removal -- otherwise the decode would
    reintroduce the very tags we just stripped.
    """
    if not text:
        return ""
    text = _html.unescape(text)
    text = HTML_TAG_RE.sub(" ", text)
    return " ".join(_html.unescape(text).split())


class JobItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    company = scrapy.Field()
    location = scrapy.Field()
    posted = scrapy.Field()
    description = scrapy.Field()


class DemoBoardSpider(scrapy.Spider):
    name = "demo"
    start_urls = [f"http://{HOST}:{PORT}/"]
    custom_settings = {
        "USER_AGENT": USER_AGENT,
        "ROBOTSTXT_OBEY": False,  # local demo server has no meaningful robots.txt
        "DOWNLOAD_DELAY": 0.15,
        "RETRY_TIMES": 2,
        "LOG_LEVEL": "INFO",
        "ITEM_PIPELINES": ITEM_PIPELINES,
    }

    async def start(self):
        ensure_started()  # Scrapy 2.13+: async def start replaces start_requests
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response: Response):
        for href in response.css("a.job::attr(href)").getall():
            yield response.follow(href, callback=self.parse_job)

    def parse_job(self, response: Response):
        yield JobItem(
            url=response.url,
            title=response.css("h1::text").get("").strip(),
            company=response.css("p.meta b::text").get("").strip(),
            location=(response.css("p.meta::text").getall() or [""])[0].strip(),
            posted=response.css("span.posted::text").get("").strip(),
            description=" ".join(
                response.css("p.description::text").getall()
            ).strip(),
        )


class RemoteOKSpider(scrapy.Spider):
    """Live jobs from Remote OK's public JSON endpoint."""

    name = "remoteok"
    limit: int = 100
    custom_settings = {
        "USER_AGENT": USER_AGENT,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 1.0,   # their robots.txt sets Crawl-delay: 1
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_TIMEOUT": 25,
        "RETRY_TIMES": 2,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "LOG_LEVEL": "INFO",
        "ITEM_PIPELINES": ITEM_PIPELINES,
    }

    async def start(self):
        yield scrapy.Request(REMOTE_OK_URL, callback=self.parse)

    def parse(self, response: Response):
        # The payload is a JSON list; the first element can be a poster note,
        # so only rows shaped like real jobs (with a position) are kept.
        rows = [r for r in json.loads(response.text) if isinstance(r, dict) and r.get("position")]
        for row in rows[: self.limit]:
            yield JobItem(
                url=f"https://remoteok.com/remote-jobs/{row['slug']}",
                title=row["position"],
                company=row.get("company") or "",
                location=row.get("location") or "",
                posted=row.get("date") or "",
                description=clean_html(row.get("description")),
            )


class ArbeitnowSpider(scrapy.Spider):
    """Live jobs from Arbeitnow's open API."""

    name = "arbeitnow"
    limit: int = 100
    custom_settings = {
        "USER_AGENT": USER_AGENT,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_TIMEOUT": 25,
        "RETRY_TIMES": 2,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "LOG_LEVEL": "INFO",
        "ITEM_PIPELINES": ITEM_PIPELINES,
    }

    async def start(self):
        yield scrapy.Request(ARBEITNOW_URL, callback=self.parse)

    def parse(self, response: Response):
        payload = json.loads(response.text)
        rows = payload.get("data", [])[: self.limit]
        for row in rows:
            posted = row.get("created_at") or ""
            if posted:
                try:
                    posted = (
                        datetime.fromtimestamp(float(posted)).date().isoformat()
                    )
                except (ValueError, OSError):
                    posted = ""
            yield JobItem(
                url=row.get("url") or f"https://www.arbeitnow.com/view/{row['slug']}",
                title=row.get("title") or "",
                company=row.get("company_name") or "",
                location=row.get("location") or "",
                posted=posted,
                description=clean_html(row.get("description")),
            )


SOURCES = {
    "demo": DemoBoardSpider,
    "remoteok": RemoteOKSpider,
    "arbeitnow": ArbeitnowSpider,
}


class TinyDBPipeline:
    def process_item(self, item: scrapy.Item):
        from skillscope.store import upsert_listing

        upsert_listing(dict(item))
        return item


@contextmanager
def _demo_board():
    """Start the demo board only for the offline source; stop after."""
    ensure_started()
    try:
        yield
    finally:
        stop()


def run_crawl(source: str = "remoteok", limit: int = 100) -> dict[str, int]:
    """Crawl `source` into a fresh store and persist via the pipeline.

    The table is cleared first so the report reflects only the selected
    source (no mixing of previous crawls). Returns store counts.
    """
    from skillscope.store import clear, counts

    spider_cls = SOURCES.get(source)
    if spider_cls is None:
        raise ValueError(f"unknown source {source!r}; choose one of {sorted(SOURCES)}")

    clear()

    enter = _demo_board() if source == "demo" else _null_ctx()

    with enter:
        process = CrawlerProcess(
            settings={**spider_cls.custom_settings, "BOT_NAME": "skillscope"}
        )
        process.crawl(spider_cls, limit=limit)
        process.start()
    return counts()


@contextmanager
def _null_ctx():
    yield