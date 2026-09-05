"""
synthetic.py — deterministic offline sample for CI (no network on PR runners).
~140 postings across the four sources with realistic skill/salary structure.
"""

from datetime import datetime, timezone, date, timedelta
import numpy as np
import pandas as pd

SEED = 7
TITLES = [
    ("Data Analyst", "mid", ("SQL", "Excel", "Power BI", "Tableau", "Python"),
     (45_000, 95_000)),
    ("Senior Data Analyst", "senior", ("SQL", "Python", "Power BI", "dbt", "Snowflake"),
     (90_000, 140_000)),
    ("Data Engineer", "mid", ("Python", "SQL", "Spark", "Airflow", "AWS", "Kafka"),
     (95_000, 150_000)),
    ("Analytics Engineer", "mid", ("dbt", "SQL", "Snowflake", "BigQuery", "Looker"),
     (85_000, 135_000)),
    ("Data Scientist", "mid", ("Python", "scikit-learn", "Statistics", "SQL", "A/B Testing"),
     (90_000, 150_000)),
    ("Senior Data Scientist", "senior", ("Python", "MLflow", "PyTorch", "GenAI/LLMs", "A/B Testing"),
     (130_000, 190_000)),
    ("BI Developer", "mid", ("Power BI", "SQL", "Tableau", "Dashboarding"),
     (70_000, 120_000)),
    ("ML Engineer", "senior", ("Python", "PyTorch", "Docker", "Kubernetes", "GCP"),
     (120_000, 185_000)),
    ("Junior Data Analyst", "junior", ("SQL", "Excel", "Dashboarding"),
     (35_000, 60_000)),
    ("Staff Analytics Engineer", "senior", ("dbt", "Snowflake", "Data Modeling", "Airflow", "Semantic Layer"),
     (150_000, 210_000)),
]
SOURCES = ["remoteok", "jobicy", "remotive", "arbeitnow"]
COMPANIES = ["Nimbus Health", "CartLoop", "FinEdge", "Datawise", "Helio Retail",
             "OrbitPay", "Stackline AI", "Northbeam", "CloudCart", "Rivet"]
LOCATIONS = ["worldwide", "Anywhere in the World", "US", "EU", "AMER", "EMEA",
             "Pakistan", "remote"]


def generate() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    today = date.fromisoformat(data_snapshot())
    rows = []
    for i in range(140):
        title, senior, skills, (slo, shi) = TITLES[i % len(TITLES)]
        lo = round(rng.uniform(0.8, 1.15) * slo, -3)
        hi = round(lo * rng.uniform(1.15, 1.45), -3)
        has_salary = rng.random() < 0.55
        posted = today - timedelta(days=int(rng.integers(0, 21)))
        rows.append({
            "source": SOURCES[i % len(SOURCES)], "external_id": f"syn-{i}",
            "title": title,
            "company": COMPANIES[i % len(COMPANIES)],
            "location_text": LOCATIONS[i % len(LOCATIONS)],
            "tags": ";".join(["remote", "data"]),
            "description_text": f"{title}. We use {', '.join(skills)}. "
                                f"{'Salary range $' + str(int(lo)) + 'k-$' + str(int(hi/1000)) + 'k.' if has_salary else ''}",
            "salary_min_usd": lo if has_salary else None,
            "salary_max_usd": hi if has_salary else None,
            "salary_source": "api" if has_salary else None,
            "posted_at": posted.isoformat(), "url": "https://example.com/job/" + str(i),
            "fetched_at": datetime.now(timezone.utc), "snapshot_date": SNAPSHOT_DATE(),
            "skills": ";".join(skills), "seniority": senior,
            "role_family": _family(title),
        })
    return pd.DataFrame(rows)


def SNAPSHOT_DATE() -> str:
    return date.today().isoformat()


def data_snapshot() -> str:
    return date.today().isoformat()


def _family(t: str) -> str:
    return {"Data Analyst": "Data Analyst", "Senior Data Analyst": "Data Analyst",
            "Junior Data Analyst": "Data Analyst", "Data Engineer": "Data Engineer",
            "Analytics Engineer": "Analytics Engineer",
            "Staff Analytics Engineer": "Analytics Engineer",
            "BI Developer": "BI Developer", "ML Engineer": "ML Engineer",
            "Data Scientist": "Data Scientist",
            "Senior Data Scientist": "Data Scientist"}[t]
