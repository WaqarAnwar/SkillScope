"""Minimal MapReduce over the document store, using process pools.

Classic MapReduce decomposition for the "scale-out" bullet on the job spec:

    map      each worker turns a chunk of documents into (key, value) pairs
    shuffle  pairs are grouped by key (in the coordinator)
    reduce   workers merge each group's values into a single result

`count_skills` is the canonical job: count how often each skill appears
across every crawled listing, in parallel.

All functions used as map/reduce steps are module-level so they can be
pickled and shipped to pool workers (closures are not picklable).
"""

from __future__ import annotations

import multiprocessing as mp
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from skillscope.extract import tokenize

Mapper = Callable[[list[dict[str, Any]]], list[tuple[str, int]]]
Reducer = Callable[[tuple[str, list[int]]], tuple[str, int]]


def _run_mapper(mapper: Mapper, chunk: list[dict[str, Any]]) -> list[tuple[str, int]]:
    return mapper(chunk)


def _skill_mapper(chunk: list[dict[str, Any]]) -> list[tuple[str, int]]:
    return [(skill, 1) for doc in chunk for skill in doc.get("skills", [])]


def _word_mapper(chunk: list[dict[str, Any]]) -> list[tuple[str, int]]:
    pairs: list[tuple[str, int]] = []
    for doc in chunk:
        for word in tokenize(doc.get("description", "")):
            if len(word) > 2:
                pairs.append((word, 1))
    return pairs


def _sum_reducer(key_values: tuple[str, list[int]]) -> tuple[str, int]:
    key, values = key_values
    return key, sum(values)


def mapreduce(
    items: list[Any],
    mapper: Mapper = _skill_mapper,
    reducer: Reducer = _sum_reducer,
    chunks: int | None = None,
    workers: int | None = None,
) -> dict[str, int]:
    """Run a map->shuffle->reduce job over `items` and return {key: value}."""
    if not items:
        return {}
    n_workers = workers or mp.cpu_count()
    n_chunks = chunks or max(1, min(len(items), (workers or mp.cpu_count()) * 2))
    splits = [items[i::n_chunks] for i in range(n_chunks)]
    splits = [s for s in splits if s]

    with mp.Pool(processes=n_workers) as pool:  # map
        mapped = pool.starmap(_run_mapper, [(mapper, s) for s in splits])

    grouped: dict[str, list[int]] = defaultdict(list)  # shuffle
    for pairs in mapped:
        for key, value in pairs:
            grouped[key].append(value)

    with mp.Pool(processes=n_workers) as pool:  # reduce
        reduced = pool.map(reducer, list(grouped.items()))

    return dict(reduced)


def count_skills(listings: list[dict[str, Any]]) -> dict[str, int]:
    """How many listings mention each skill (the classic MapReduce job)."""
    return mapreduce(listings, mapper=_skill_mapper, reducer=_sum_reducer, workers=2)


def count_words(listings: list[dict[str, Any]]) -> dict[str, int]:
    """Term frequency over every token across all descriptions."""
    return mapreduce(listings, mapper=_word_mapper, reducer=_sum_reducer, workers=2)