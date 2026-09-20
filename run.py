"""SkillScope CLI.

    python run.py scrape [--source remoteok|arbeitnow|demo] [--limit N]
                         crawl the chosen board with Scrapy -> TinyDB
    python run.py extract        NLTK skill extraction on every listing
    python run.py count          MapReduce skill/term counts over the store
    python run.py analyze        pandas + scikit-learn -> data/report.json
    python run.py all [--source S] [--limit N]
                                 scrape -> extract -> count -> analyze
    python run.py nltk-data      download the NLTK punkt/stopwords corpora
    python run.py serve          start the FastAPI web UI + API on :8000
"""

from __future__ import annotations

import argparse
import sys

DEFAULT_SOURCE = "remoteok"


def cmd_scrape(args: argparse.Namespace) -> None:
    from crawler import run_crawl

    print(run_crawl(args.source, limit=args.limit))


def cmd_extract() -> None:
    from skillscope.extract import extract_all_listings

    changed = extract_all_listings()
    print(f"extracted skill lists for all listings ({changed} updated)")


def cmd_count() -> None:
    from skillscope.mapreduce import count_skills, count_words
    from skillscope.store import all_listings

    docs = all_listings()
    if not docs:
        sys.exit("no listings yet -- run `python run.py scrape` first")
    print("skill counts (MapReduce):")
    for skill, cnt in sorted(count_skills(docs).items(), key=lambda kv: -kv[1]):
        print(f"  {skill:14} {cnt}")
    words = count_words(docs)
    print("top terms (MapReduce):", dict(sorted(words.items(), key=lambda kv: -kv[1])[:10]))


def cmd_analyze() -> None:
    from skillscope.analyze import run

    report = run()
    print(json_summary(report))


def cmd_all(args: argparse.Namespace) -> None:
    cmd_scrape(args)
    cmd_extract()
    cmd_count()
    cmd_analyze()


def cmd_nltk_data() -> None:
    import nltk

    for resource in ("punkt_tab", "stopwords"):
        print(f"downloading {resource}...")
        nltk.download(resource, quiet=True)


def cmd_serve() -> None:
    import uvicorn

    from skillscope.api import app

    uvicorn.run(app, host="127.0.0.1", port=8000)


def json_summary(report: dict) -> str:
    lines = [
        f"listings:            {report['listings']}",
        f"distinct skills:     {report['skills_found']}",
        "top 5 skills:        " + ", ".join(s["skill"] for s in report["top_20_skills"][:5]),
        "clusters:",
    ]
    for cid, c in report["clusters"].items():
        lines.append(f"  {cid}: {c['name']}")
    lines.append(f"report written -> data/report.json")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="run.py", description=__doc__)
    parser.add_argument("command", choices=["scrape", "extract", "count", "analyze", "all", "nltk-data", "serve"])
    parser.add_argument("--source", default=DEFAULT_SOURCE,
                        help="job board to crawl: remoteok (default), arbeitnow, or demo (offline)")
    parser.add_argument("--limit", type=int, default=100,
                        help="max listings to crawl from a live source (default 100)")
    args = parser.parse_args(argv)

    if args.command == "scrape":
        cmd_scrape(args)
    elif args.command == "all":
        cmd_all(args)
    elif args.command == "extract":
        cmd_extract()
    elif args.command == "count":
        cmd_count()
    elif args.command == "analyze":
        cmd_analyze()
    elif args.command == "nltk-data":
        cmd_nltk_data()
    elif args.command == "serve":
        cmd_serve()


if __name__ == "__main__":
    main()