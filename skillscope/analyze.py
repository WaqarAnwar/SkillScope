"""Market analysis on top of the (NoSQL) listings: pandas + scikit-learn.

Reads the TinyDB store, turns it into a DataFrame, computes demand stats,
then runs TF-IDF vectorisation + KMeans clustering so the job market gets
grouped into interpretable role clusters. Nothing is hard-coded: every number
in `report.json` is computed from crawled data.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfTransformer

from skillscope.store import DATA_DIR, all_listings


def listings_frame() -> pd.DataFrame:
    docs = all_listings()
    return pd.DataFrame(docs).drop(columns=["doc_id"], errors="ignore")


def skill_frequencies(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["skill", "count", "share"])
    series = frame.explode("skills")["skills"].dropna().value_counts()
    freq = pd.DataFrame({"skill": series.index, "count": series.values})
    freq["share"] = (freq["count"] / len(frame)).round(3)
    return freq.reset_index(drop=True)


def role_clusters(
    frame: pd.DataFrame,
    n_clusters: int = 3,
    min_docs: int = 2,
    max_freq: float = 0.35,
) -> pd.DataFrame:
    """KMeans over TF-IDF-weighted *skill sets**, labelled by distinctive skills.

    Each listing is a one-hot vector over the extracted skills, TF-IDF weighted
    so a skill is a strong signal when rare in the corpus but present in the
    listing. Ubiquitous buzzwords ("ai" at 0.5 share) and skills seen in one
    posting carry no separability and are dropped from the feature space.

    Clusters are named by the skills most over-represented in a cluster
    *relative to the corpus* (cluster tf-idf mean minus global mean), so every
    name isolates what actually distinguishes that role group; the demo board
    yields devops / data / ML, live boards yield whatever real role families the
    feed contains.
    """
    skills_by = frame["skills"].apply(
        lambda sk: set(sk) if isinstance(sk, list) else set()
    )
    pool = {s for s in set().union(*skills_by) if s}
    if len(pool) < min(2, n_clusters):
        raise ValueError("need more distinct skills to cluster")

    freq = {s: sum(1 for sk in skills_by if s in sk) for s in pool}
    features = sorted(
        s for s in pool if min_docs <= freq[s] <= max_freq * len(frame)
    )
    if not features:  # no skill in the informative band -> use the whole pool
        features = sorted(pool)

    X = np.zeros((len(frame), len(features)), dtype=float)
    for i, sk in enumerate(skills_by):
        for j, s in enumerate(features):
            if s in sk:
                X[i, j] = 1
    X = TfidfTransformer().fit_transform(X)

    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(X)

    global_mean = np.asarray(X.mean(axis=0)).ravel()
    cluster_terms: dict[int, list[str]] = {}
    for cluster in range(n_clusters):
        mean = X.toarray()[labels == cluster].mean(axis=0)
        differential = mean - global_mean
        rank = np.argsort(differential)[::-1]# if none stand out, fall back to plain tf-idf
        top = [features[i] for i in rank[:5] if differential[i] > 0]
        if not top:
            top = [features[i] for i in np.argsort(mean)[::-1][:5] if mean[i] > 0]
        cluster_terms[cluster] = top

    labeled = frame.copy()
    labeled["cluster"] = labels
    labeled["cluster_name"] = labeled["cluster"].map(
        lambda c: f"cluster {c}: {', '.join(cluster_terms[c]) or 'no distinctive skills'}"
    )
    return labeled


def build_report(
    freq: pd.DataFrame,
    clustered: pd.DataFrame,
    counts: dict[str, int],
    skill_mapreduce: dict[str, int],
    word_mapreduce: dict[str, int],
) -> dict[str, Any]:
    clusters: dict[str, Any] = {}
    for label, group in clustered.groupby("cluster"):
        clusters[str(int(label))] = {
            "name": group["cluster_name"].iloc[0],
            "listings": int(len(group)),
            "top_skills": series_top(group.explode("skills")["skills"].dropna()),
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "listings": counts.get("listings", 0),
        "skills_found": int(freq["skill"].nunique() if not freq.empty else 0),
        "top_20_skills": freq.head(20).to_dict("records"),
        "skill_counts_mapreduce": dict(
            sorted(skill_mapreduce.items(), key=lambda kv: kv[1], reverse=True)[:20]
        ),
        "top_10_terms_mapreduce": dict(
            sorted(word_mapreduce.items(), key=lambda kv: kv[1], reverse=True)[:10]
        ),
        "clusters": clusters,
    }


def series_top(series: pd.Series) -> list[str]:
    return series.value_counts().head(5).index.tolist()


def run(n_clusters: int = 3) -> dict[str, Any]:
    frame = listings_frame()
    if frame.empty:
        raise RuntimeError("no listings crawled yet -- run `python run.py scrape`")
    freq = skill_frequencies(frame)
    clustered = role_clusters(frame, n_clusters=n_clusters)
    clustered.to_csv(os.path.join(DATA_DIR, "clusters.csv"), index=False)
    freq.to_csv(os.path.join(DATA_DIR, "top_skills.csv"), index=False)

    from skillscope.mapreduce import count_skills, count_words

    docs = all_listings()
    skill_counts = count_skills(docs)
    word_counts = count_words(docs)

    report = build_report(
        freq,
        clustered,
        {"listings": len(docs)},
        skill_counts,
        word_counts,
    )
    with open(os.path.join(DATA_DIR, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report