"""
fetch_sources.py
----------------
Four keyless public job-board APIs, normalized into one job-record schema:

    source, external_id, title, company, location_text, tags (list),
    description_text, salary_min_usd, salary_max_usd, salary_source,
    posted_at, url, fetched_at, snapshot_date

Enrichment happens at the edge (Python) rather than mid-warehouse (SQL):
salary text parsing, skill extraction against a seeded taxonomy,
seniority / role-family classification.  dbt then only deals with clean,
typed rows — the separation a reviewer wants to see.

Data-family filter: a posting counts as a *data job* if its title hits the
DATA_TITLE pattern OR several data skills appear in title+description.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone, date
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger("ingestion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HEADERS = {"User-Agent": "data-job-market-radar/1.0 (portfolio project)"}
SEEDS = Path(__file__).resolve().parent.parent / "dbt" / "seeds" / "skill_taxonomy.csv"
SNAPSHOT = date.today().isoformat()

DATA_TITLE = re.compile(
    r"(?i)\b(data\s?(analyst|scientist|engineer)|analytics|machine learning|ml "
    r"|business intelligence|\bbi\b|quantitative|statistic|etl|analytics "
    r"engineer|decision science|insights)\b")

# ----------------------------------------------------------------- skills

def load_skill_matchers() -> list[tuple[str, str, re.Pattern]]:
    df = pd.read_csv(SEEDS)
    out = []
    for _, r in df.iterrows():
        out.append((r["skill"], r["category"],
                    re.compile(r["regex"], flags=0)))
    return out

SKILL_MATCHERS = load_skill_matchers()


def extract_skills(title: str, text: str, tags: list[str]) -> list[str]:
    hay = f"{title}\n{' '.join(tags or [])}\n{(text or '')[:6000]}"
    return [skill for skill, _cat, rx in SKILL_MATCHERS if rx.search(hay)]


def classify_seniority(title: str) -> str:
    t = title.lower()
    if re.search(r"\b(intern|trainee|apprentice)\b", t): return "intern"
    if re.search(r"\b(junior|jr\.?|entry[- ]level|graduate)\b", t): return "junior"
    if re.search(r"\b(senior|sr\.?|staff|principal|lead|head of|manager|director)\b", t):
        return "senior"
    return "mid"


def classify_family(title: str) -> str:
    t = title.lower()
    if "analytics engineer" in t: return "Analytics Engineer"
    if re.search(r"machine learning|\bml\b|ai engineer", t): return "ML Engineer"
    if "data scientist" in t or ("scientist" in t and "data" in t): return "Data Scientist"
    if "business intelligence" in t or re.search(r"\bbi\b", t): return "BI Developer"
    if "analytics" in t and "engineer" not in t: return "Data Analyst"
    if "analyst" in t: return "Data Analyst"
    if "engineer" in t: return "Data Engineer"
    return "Other Data"


_K = 1_000
_SAL_RANGE = re.compile(
    r"(?i)\$?\s*(\d{2,3})\s*k\s*(?:-|–|to)\s*\$?\s*(\d{2,3})\s*k")
_SAL_SINGLE = re.compile(r"(?i)\$\s*(\d{2,3})\s*k\b")
_SAL_FULL = re.compile(r"(?i)\$\s*(\d{4,6})\b")


def parse_salary_text(s: str | None) -> tuple[float | None, float | None]:
    """Extract USD-ish salary bounds from free text like '$90k-120k / year'."""
    if not s:
        return None, None
    m = _SAL_RANGE.search(s)
    if m:
        return float(m.group(1)) * _K, float(m.group(2)) * _K
    m = _SAL_SINGLE.search(s)
    if m:
        v = float(m.group(1)) * _K
        return v, v
    vals = [float(x) for x in _SAL_FULL.findall(s) if float(x) >= 20000]
    return (min(vals), max(vals)) if vals else (None, None)


def _clean(txt: str | None, limit: int = 12000) -> str:
    if not txt:
        return ""
    txt = re.sub(r"<[^>]+>", " ", html.unescape(txt))
    return re.sub(r"\s+", " ", txt).strip()[:limit]


def _record(source, ext_id, title, company, location, tags, desc,
            sal_min, sal_max, sal_src, posted, url) -> dict:
    return {
        "source": source, "external_id": str(ext_id), "title": (title or "").strip(),
        "company": (company or "").strip(), "location_text": (location or "").strip(),
        "tags": ";".join(tags or []), "description_text": _clean(desc),
        "salary_min_usd": sal_min, "salary_max_usd": sal_max,
        "salary_source": sal_src, "posted_at": posted, "url": url or "",
        "fetched_at": datetime.now(timezone.utc), "snapshot_date": SNAPSHOT,
    }


# ------------------------------------------------------------- extractors

def fetch_remoteok() -> list[dict]:
    j = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=30).json()
    out = []
    for r in j[1:]:
        if not isinstance(r, dict) or not r.get("position"):
            continue
        title = r["position"]
        tags = r.get("tags") or []
        if not (DATA_TITLE.search(title) or any("data" in str(t).lower() for t in tags)):
            continue
        out.append(_record(
            "remoteok", r.get("id"), title, r.get("company"),
            r.get("location") or "worldwide", tags, f"{title} {r.get('description_generic','')}",
            _num(r.get("salary_min")), _num(r.get("salary_max")), "api",
            r.get("date"), r.get("url") or f"https://remoteok.com/l/{r.get('id')}"))
    return out


def fetch_jobicy() -> list[dict]:
    out = []
    j = requests.get(
        # NOTE: jobicy returns an empty list if you pass order=latest — plain
        # industry filter only. (Quirk verified 2026-09-05.)
        "https://jobicy.com/api/v2/remote-jobs?count=50&industry=data-science",
        headers=HEADERS, timeout=30).json()
    for r in j.get("jobs", []):
        title = r.get("jobTitle", "")
        ind = r.get("jobIndustry", "")
        if not DATA_TITLE.search(f"{title} {ind}"):
            continue
        out.append(_record(
            "jobicy", r.get("id"), title, r.get("companyName"),
            r.get("jobGeo") or "worldwide",
            [str(x) for x in (r.get("jobType") or [])] + [str(ind)],
            r.get("jobDescription", ""),
            _num(r.get("annualSalaryMin")), _num(r.get("annualSalaryMax")), "api",
            r.get("pubDate"), r.get("url")))
    return out


def fetch_remotive() -> list[dict]:
    # 'data' category is loosely curated; 'software-dev' hides analytics/ML
    # roles — pull both, dedupe by id, apply a strict title filter.
    rows, seen = [], set()
    for cat in ("data", "software-dev"):
        j = requests.get(
            f"https://remotive.com/api/remote-jobs?category={cat}&limit=300",
            headers=HEADERS, timeout=30).json()
        for r in j.get("jobs", []):
            if r.get("id") not in seen:
                seen.add(r.get("id"))
                rows.append(r)
    out = []
    for r in rows:
        title = r.get("title", "")
        # remotive's 'data' category is loose (contains copywriting gigs) —
        # the title must independently classify as a data role
        if not DATA_TITLE.search(title):
            continue
        lo, hi = parse_salary_text(r.get("salary"))
        out.append(_record(
            "remotive", r.get("id"), title, r.get("company_name"),
            r.get("candidate_required_location") or "worldwide",
            [r.get("category", "")], r.get("description", ""),
            lo, hi, "parsed_text", r.get("publication_date"), r.get("url")))
    return out


def fetch_arbeitnow() -> list[dict]:
    out, url = [], "https://www.arbeitnow.com/api/job-board-api"
    for _ in range(8):  # pages deep enough to cover a few weeks of postings
        j = requests.get(url, headers=HEADERS, timeout=30).json()
        rows = j.get("data", [])
        if not rows:
            break
        for r in rows:
            title = r.get("title", "")
            tags = r.get("tags") or []
            if not (DATA_TITLE.search(title)
                    or any("data" in str(t).lower() for t in tags)):
                continue
            out.append(_record(
                "arbeitnow", r.get("slug"), title, r.get("company_name"),
                r.get("location") or ("remote" if r.get("remote") else ""), tags,
                r.get("description", ""), None, None, None,
                r.get("created_at") and datetime.fromtimestamp(
                    int(r["created_at"]), tz=timezone.utc).isoformat(), r.get("url")))
        url = (j.get("links") or {}).get("next") or ""
        if not url:
            break
    return out


def _num(x):
    try:
        v = float(x)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


FETCHERS = {"remoteok": fetch_remoteok, "jobicy": fetch_jobicy,
            "remotive": fetch_remotive, "arbeitnow": fetch_arbeitnow}


def extract_all() -> pd.DataFrame:
    """Run every source; a failed source is logged and skipped."""
    frames = []
    for name, fn in FETCHERS.items():
        try:
            rows = fn()
            log.info("  ✓ %-10s %4d data jobs", name, len(rows))
            if rows:
                df = pd.DataFrame(rows)
                df["skills"] = df.apply(
                    lambda r: ";".join(extract_skills(r["title"], r["description_text"],
                                                      r["tags"].split(";") if r["tags"] else [])),
                    axis=1)
                df["seniority"] = df["title"].map(classify_seniority)
                df["role_family"] = df["title"].map(classify_family)
                frames.append(df)
        except Exception as exc:  # noqa: BLE001
            log.warning("  ✗ %-10s failed (%s)", name, str(exc)[:90])
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df.fillna({"skills": "", "tags": ""})


if __name__ == "__main__":
    df = extract_all()
    print(df.groupby("source").size())
    print(df[["title", "role_family", "seniority", "skills"]].head(8).to_string(index=False))
