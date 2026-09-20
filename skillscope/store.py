"""TinyDB: the project's NoSQL document store.

One small pure-Python DB file, `data/jobs.json`, keeps the whole project a
zero-infrastructure demo -- but every read/write goes through here, so swapping
in MongoDB (pymongo) later means changing only this module.
"""

from __future__ import annotations

import os
from typing import Any

from tinydb import Query, TinyDB, where

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "jobs.json")

_jobs_table = None


def _table():
    global _jobs_table
    if _jobs_table is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _jobs_table = TinyDB(DB_PATH).table("listings")
    return _jobs_table


def upsert_listing(doc: dict[str, Any]) -> None:
    """De-dupe is (url): re-crawling updates rows instead of duplicating."""
    existing = _table().get(where("url") == doc["url"])
    if existing:
        _table().update(doc, doc_ids=[existing.doc_id])
    else:
        _table().insert(doc)


def get_listing(url: str) -> dict[str, Any] | None:
    return _table().get(where("url") == url)


def all_listings() -> list[dict[str, Any]]:
    return _table().all()


def update_listing(doc_id: int, fields: dict[str, Any]) -> None:
    _table().update(fields, doc_ids=[doc_id])


def counts() -> dict[str, int]:
    return {"listings": len(_table())}


def clear() -> None:
    _table().truncate()


def sample(n: int = 3) -> list[dict[str, Any]]:
    docs = _table().all()
    return docs[:n]