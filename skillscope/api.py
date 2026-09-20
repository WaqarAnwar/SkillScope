"""FastAPI wrapper: vanilla-JS web UI + read-only JSON API.

`POST /run` executes the whole pipeline (scrape -> extract -> count -> analyse)
as a subprocess, so Scrapy's Twisted reactor and the MapReduce process pools
stay out of the uvicorn process. The page is served from skillscope/static.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse

from skillscope.analyze import listings_frame, skill_frequencies
from skillscope.store import DATA_DIR, all_listings, counts, sample

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "skillscope" / "static"
RUN_PY = BASE_DIR / "run.py"
REPORT_PATH = Path(DATA_DIR) / "report.json"

app = FastAPI(title="SkillScope", version="1.1.0")

_run_lock = threading.Lock()
_run_state: dict = {"running": False, "last_run": None, "last_ok": None, "last_output": []}


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api")
def api_root() -> dict:
    return {"name": "SkillScope", "endpoints": [x for x in ("", "api", "listings", "skills/top", "sample", "report", "run")]}


@app.get("/listings")
def listings(limit: int = Query(20, ge=1, le=1000), offset: int = Query(0, ge=0)):
    docs = all_listings()
    return {
        "total": len(docs),
        "limit": limit,
        "offset": offset,
        "items": [
            {k: v for k, v in d.items() if k not in ("doc_id", "description_raw")}
            for d in docs[offset : offset + limit]
        ],
    }


@app.get("/skills/top")
def top_skills(k: int = Query(20, ge=1, le=200)):
    frame = listings_frame()
    freq = skill_frequencies(frame) if not frame.empty else None
    return {"total_listings": counts()["listings"], "top": (freq.head(k).to_dict("records") if freq is not None else [])}


@app.get("/sample")
def sample_listings() -> list[dict]:
    return sample(3)


@app.get("/report")
def report():
    try:
        return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"error": "no report yet -- press Run pipeline in the UI"}


@app.get("/run/status")
def run_status() -> dict:
    return dict(_run_state)


@app.post("/run")
def run_pipeline(source: str = Query("remoteok"), limit: int = Query(100, ge=1, le=500)):
    """Run scrape -> extract -> count -> analyse as a subprocess."""
    if source not in ("remoteok", "arbeitnow", "demo"):
        return {"status": "error", "returncode": None, "output": [], "stderr_tail": [f"unknown source: {source}"], "report": None}
    if not _run_lock.acquire(blocking=False):
        return {"status": "running", "already_running": True}
    _run_state.update(running=True, last_source=source)
    try:
        result = subprocess.run(
            [sys.executable, str(RUN_PY), "all", "--source", source, "--limit", str(limit)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = result.returncode == 0
        report = None
        if REPORT_PATH.exists():
            report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        output_tail = (result.stdout or "").strip().splitlines()[-40:]
        err_tail = (result.stderr or "").strip().splitlines()[-10:]
        _run_state.update(
            running=False,
            last_ok=ok,
            last_run=datetime.now(timezone.utc).isoformat(),
            last_output=output_tail,
        )
        return {
            "status": "ok" if ok else "error",
            "returncode": result.returncode,
            "output": output_tail,
            "stderr_tail": err_tail,
            "report": report,
        }
    except subprocess.TimeoutExpired:
        _run_state.update(running=False, last_ok=False, last_run=datetime.now(timezone.utc).isoformat())
        return {"status": "error", "returncode": None, "output": [], "stderr_tail": ["pipeline timed out"], "report": None}
    finally:
        _run_state["running"] = False
        _run_lock.release()