"""NLTK-based skill extraction.

Tokenise each job description with NLTK's `word_tokenize`, then match a
curated skill dictionary longest-match-first. Skills that are punctuation-y
(c++, .net, node.js) or multi-token (ci/cd) are matched on the raw text as a
second pass, so tokenisation artifacts never hide them.

If the `punkt_tab` corpus is not installed the tokeniser falls back to a
regex so the pipeline still runs offline -- but NLTK is used whenever the
corpus is present, and `python run.py nltk-data` installs it.
"""

from __future__ import annotations

import re
from typing import Iterable

# name -> aliases (normalised, lowercase)
SKILLS: dict[str, tuple[str, ...]] = {
    "python": ("python", "python3", "python 3"),
    "sql": ("sql",),
    "mysql": ("mysql",),
    "postgresql": ("postgresql", "postgres"),
    "oracle": ("oracle",),
    "nosql": ("nosql", "no-sql"),
    "mongodb": ("mongodb", "mongo"),
    "redis": ("redis",),
    "elasticsearch": ("elasticsearch", "elastic"),
    "cassandra": ("cassandra",),
    "pandas": ("pandas",),
    "numpy": ("numpy",),
    "scikit-learn": ("scikit-learn", "scikit learn", "sklearn"),
    "tensorflow": ("tensorflow",),
    "pytorch": ("pytorch",),
    "ml": ("ml", "machine learning"),
    "mlops": ("mlops",),
    "ai": ("ai", "artificial intelligence"),
    "llm": ("llm", "llms", "large language model", "large language models", "gpt", "openai", "langchain", "genai"),
    "spark": ("spark", "pyspark"),
    "kafka": ("kafka",),
    "airflow": ("airflow",),
    "hadoop": ("hadoop",),
    "mapreduce": ("mapreduce", "map-reduce"),
    "databricks": ("databricks",),
    "snowflake": ("snowflake",),
    "dbt": ("dbt",),
    "tableau": ("tableau",),
    "power bi": ("power bi", "powerbi"),
    "analytics": ("analytics", "google analytics", "ga4"),
    "scrapy": ("scrapy",),
    "requests": ("requests",),
    "bs4": ("beautifulsoup", "bs4"),
    "nltk": ("nltk",),
    "spacy": ("spacy",),
    "django": ("django",),
    "flask": ("flask",),
    "fastapi": ("fastapi",),
    "javascript": ("javascript", "js"),
    "typescript": ("typescript",),
    "react": ("react", "next.js", "nextjs"),
    "vue": ("vue", "vue.js", "nuxt", "nuxt.js"),
    "angular": ("angular",),
    "svelte": ("svelte",),
    "flutter": ("flutter", "dart"),
    "node.js": ("node.js", "nodejs", "node"),
    "go": ("go", "golang"),
    "rust": ("rust",),
    "java": ("java",),
    "kotlin": ("kotlin",),
    "swift": ("swift",),
    "ruby": ("ruby", "rails", "ruby on rails"),
    "php": ("php", "laravel"),
    "c#": ("c#", "csharp", "dotnet"),
    ".net": (".net", "dotnet"),
    "git": ("git", "github", "gitlab"),
    "devops": ("devops",),
    "ci/cd": ("ci/cd", "cicd", "ci cd"),
    "docker": ("docker",),
    "kubernetes": ("kubernetes", "k8s"),
    "helm": ("helm",),
    "terraform": ("terraform",),
    "jenkins": ("jenkins",),
    "ansible": ("ansible",),
    "puppet": ("puppet",),
    "aws": ("aws", "amazon web services"),
    "gcp": ("gcp", "google cloud"),
    "azure": ("azure", "microsoft azure"),
    "linux": ("linux",),
    "unix": ("unix",),
    "bash": ("bash", "shell"),
    "powershell": ("powershell",),
    "prometheus": ("prometheus",),
    "grafana": ("grafana",),
    "splunk": ("splunk",),
    "security": ("security", "cybersecurity", "cyber security", "infosec", "soc2", "iso27001", "gdpr"),
    "c++": ("c++", "cpp"),
    "excel": ("excel",),
    "google sheets": ("google sheets", "g sheets", "spreadsheets"),
    "salesforce": ("salesforce", "sfdc"),
    "hubspot": ("hubspot",),
    "marketing": ("marketing",),
    "seo": ("seo",),
    "crm": ("crm",),
    "etl": ("etl",),
    "figma": ("figma",),
    "blockchain": ("blockchain", "web3", "solidity", "ethereum"),
    "graphql": ("graphql",),
    "rest": ("restful",),
}

# Multi-token / punctuation-y skills matched on the raw (lowercased) text.
_RAW_RE = re.compile(
    r"((?:c\+\+|\.net|node\.js|ci/cd|scikit[- ]learn|c#|machine learning|ruby on rails|power bi|google sheets|amazon web services|large language models?|artificial intelligence))\b",
    re.I,
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]*")
_RAW_RE = re.compile(r"((?:c\+\+|\.net|node\.js|ci/cd|scikit[- ]learn))\b", re.I)


def _normalise(tokens: Iterable[str]) -> list[str]:
    out: list[str] = []
    for tok in tokens:
        tok = tok.rstrip(".:,;!?)\"'")
        tok = ".".join(part for part in tok.split(".") if part)  # node.js -> node.js
        if tok:
            out.append(tok)
    return out


def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = []
    try:
        from nltk.tokenize import word_tokenize

        tokens = word_tokenize(text)
    except LookupError:  # NLTK corpus missing -> regex safety net
        tokens = _TOKEN_RE.findall(text)
    return _normalise(tokens)


def _lookup(skill_tokens: set[str], text: str) -> list[str]:
    """Longest-match-first lookup of the skill dictionary."""
    found: set[str] = set()
    ranked = sorted(
        ((len(names[0]), name, names) for name, names in SKILLS.items()),
        reverse=True,
    )
    for _, name, aliases in ranked:
        if any(alias in skill_tokens for alias in aliases):
            found.add(name)
    for m in _RAW_RE.finditer(text):
        alias = m.group(1).lower().replace("_", "-")
        for name, aliases in SKILLS.items():
            if alias in aliases:
                found.add(name)
    return sorted(found)


def extract_skills(text: str) -> list[str]:
    """Return the sorted list of skills found in a job description."""
    return _lookup(set(tokenize(text)), text.lower())


def extract_all_listings() -> int:
    """Backfill `skills` for every stored listing; returns how many changed."""
    import skillscope.store as store

    changed = 0
    for doc in store.all_listings():
        skills = extract_skills(doc.get("description", ""))
        if skills != doc.get("skills"):
            store.update_listing(
                doc.doc_id, {"skills": skills, "skill_count": len(skills)}
            )
            changed += 1
    return changed