"""Offline demo job board served over real HTTP (Scrapy crawls it for real).

A tiny threaded HTTP server on 127.0.0.1:8765 serving fabricated job listing
pages. This keeps the crawl -- and therefore the whole project -- fully
reproducible with zero external dependencies, while still exercising a genuine
HTTP crawl path (index -> detail pages).
"""

from __future__ import annotations

import threading
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8765

JOBS = [
    {
        "title": "Senior Python Data Engineer",
        "company": "Dataforge",
        "location": "Remote (EU)",
        "posted": "2026-08-03",
        "description": (
            "We build streaming data infrastructure in Python. You will design "
            "ETL pipelines with pandas and scikit-learn for feature engineering, "
            "ship scrapers with scrapy, and store everything in a nosql MongoDB "
            "cluster. Spark and Kafka experience is a big plus. SQL plus and "
            "Linux administration are a must."
        ),
    },
    {
        "title": "Machine Learning Engineer",
        "company": "Neuralight",
        "location": "Berlin",
        "posted": "2026-08-05",
        "description": (
            "Own models end to end: numpy, pandas, scikit-learn and TensorFlow. "
            "You will productionise NLP features with NLTK and spaCy, retrain "
            "on PyTorch, and serve predictions through FastAPI. Docker and AWS "
            "keep models in prod; experience with airflow and spark helps you "
            "go far here."
        ),
    },
    {
        "title": "Data Analyst",
        "company": "Retailomics",
        "location": "Remote",
        "posted": "2026-08-06",
        "description": (
            "Turn messy SQL exports into decisions. You will clean data with "
            "pandas, build dashboards from numpy and scikit-learn forecasts, "
            "and pull web data with scrapy when the analysts need fresh "
            "pricing. Strong Excel skills are not enough -- SQL and nosql "
            "MongoDB querying matter every day."
        ),
    },
    {
        "title": "Backend Engineer",
        "company": "Algocorp",
        "location": "London",
        "posted": "2026-08-08",
        "description": (
            "Python backend on django and FastAPI behind a Redis cache and "
            "PostgreSQL. You will also write scrapy crawlers for our market "
            "intelligence feed and analyse the output with pandas. We value "
            "solid NLTK text-processing skills and working knowledge of aws "
            "and Docker."
        ),
    },
    {
        "title": "Web Scraping Developer",
        "company": "Scrapewell",
        "location": "Remote (Worldwide)",
        "posted": "2026-08-10",
        "description": (
            "Scrapy experience is a big plus. You will build and maintain "
            "crawlers for dozens of sites, handle captchas and proxies, and "
            "process data with nutshell tools: pandas, NLTK and scikit-learn. "
            "Output lands in nosql MongoDB, so document-store fluency is "
            "expected. Distributed crawls at scale touch on mapreduce-style "
            "jobs, so parallel thinking helps."
        ),
    },
    {
        "title": "Full-Stack Developer",
        "company": "Webworks",
        "location": "Stockholm",
        "posted": "2026-08-11",
        "description": (
            "Ship features across django, JavaScript/React and PostgreSQL. "
            "Familiarity with python scraping tools like scrapy and requests, "
            "with NLTK for text features, is a plus. You will occasionally "
            "mine datasets with pandas and scikit-learn to tune product "
            "signals, and prototype answers in Redis before SQL migrations."
        ),
    },
    {
        "title": "DevOps Engineer",
        "company": "Cloudnine",
        "location": "Amsterdam",
        "posted": "2026-08-13",
        "description": (
            "Run Kubernetes clusters, Terraform and Jenkins pipelines on aws "
            "and GCP. Automation is written in Python and bash, monitored with "
            "Prometheus and Grafana, packaged as Docker images. Experience "
            "with Linux internals is required; a scripting background with "
            "numpy or pandas is a plus for the telemetry side."
        ),
    },
    {
        "title": "Site Reliability Engineer",
        "company": "LatencyLabs",
        "location": "Remote (US)",
        "posted": "2026-08-15",
        "description": (
            "Keep distributed services up: Kubernetes, Docker, Terraform, "
            "Prometheus, Grafana. You write small Python and Go tools, run "
            "incident playbooks on Linux, and automate anything done twice. "
            "Jenkins and aws are core; a touch of scikit-learn for capacity "
            "forecasts is a differentiator."
        ),
    },
    {
        "title": "Platform Engineer",
        "company": "Polycloud",
        "location": "Toronto",
        "posted": "2026-08-17",
        "description": (
            "Build internal platforms on aws with Terraform, Kubernetes and "
            "Docker, wired by Jenkins. The team scripts heavily in Python and "
            "bash, and analyses build KPI telemetry with pandas and numpy. "
            "Redis backs our shared config; new hires with Linux and "
            "Prometheus instincts fit in fastest."
        ),
    },
    {
        "title": "Chief Data Scientist",
        "company": "Insightary",
        "location": "Paris",
        "posted": "2026-08-20",
        "description": (
            "Lead the analytics guild across scikit-learn, TensorFlow and "
            "PyTorch. You will shape NLP work in NLTK and spaCy, own the "
            "pandas data warehouse views, and push models via FastAPI on "
            "Docker. Budget and headcount report to you; a crisp SQL and "
            "nosql understanding is non-negotiable."
        ),
    },
    {
        "title": "ETL Pipeline Engineer",
        "company": "Wareflux",
        "location": "Remote (Europe)",
        "posted": "2026-08-22",
        "description": (
            "Airflow DAGs, Spark batches, Kafka streams and a nosql MongoDB "
            "sink. You will wrangle JSON with pandas, enrich with NLTK text "
            "parsing, then emit features for scikit-learn models. Linux and "
            "Docker keep the pipeline alive; scrapy fetches the upstream "
            "feeds we cannot buy."
        ),
    },
    {
        "title": "NLP Engineer",
        "company": "Linguaflow",
        "location": "Madrid",
        "posted": "2026-08-25",
        "description": (
            "Text is the product. Hone tokenisation, tagging and extraction "
            "pipelines with NLTK and spaCy, batch-clean corpora with pandas, "
            "and classify content with scikit-learn and PyTorch. Python, "
            "numpy and Docker are everyday tools; a dash of aws and FastAPI "
            "for serving is expected."
        ),
    },
]

TITLES = ["{title} - {company}"]


def _page(job_id: int) -> bytes:
    job = JOBS[job_id]
    body = f"""
    <!doctype html><html><head><title>{TITLES[0].format(**job)}</title></head>
    <body>
      <article class="job">
        <h1>{escape(job['title'])}</h1>
        <p class="meta">at <b>{escape(job['company'])}</b> - {escape(job['location'])}
        <span class="posted">{job['posted']}</span></p>
        <p class="description">{escape(job['description'])}</p>
        <p class="apply">Apply at <a href="/apply/{job_id}">{escape(job['company'])} careers</a></p>
      </article>
    </body></html>
    """
    return body.encode("utf-8")


def _index() -> bytes:
    jobs = "".join(
        f'<li><a class="job" href="/job/{i}">'
        f"{escape(j['title'])} at {escape(j['company'])}</a></li>"
        for i, j in enumerate(JOBS)
    )
    body = f"""
    <!doctype html><html><head><title>Demo Jobs</title></head>
    <body><h1>Demo job board (offline)</h1><ul>{jobs}</ul></body></html>
    """
    return body.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (http.server API)
        if self.path == "/" or self.path == "/index.html":
            payload, code = _index(), 200
        elif self.path.startswith("/job/"):
            try:
                idx = int(self.path.rsplit("/", 1)[1])
                payload, code = _page(idx), 200
            except (ValueError, IndexError):
                payload, code = b"not found", 404
        else:
            payload, code = b"not found", 404
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):  # keep test output clean
        return


def start() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


_server: ThreadingHTTPServer | None = None


def ensure_started() -> ThreadingHTTPServer:
    """Start (or return) the demo server; idempotent across crawls."""
    global _server
    if _server is None:
        _server = start()
    return _server


def stop() -> None:
    global _server
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None


if __name__ == "__main__":
    print(f"Demo jobs board on http://{HOST}:{PORT}/")
    start().serve_forever()