"""
run_ingestion.py
----------------
    python ingestion/run_ingestion.py             # live multi-source run
    python ingestion/run_ingestion.py --offline   # deterministic sample (CI)

Append-snapshot loading:
  * every run archives raw parquet to data/raw/snapshot_date=YYYY-MM-DD/
  * duckdb `raw_job_postings` keeps one row per (source, external_id,
    snapshot_date) — re-running the same day replaces that day's rows
    (idempotent), while history accumulates week over week.  dbt builds the
    posting lifecycle (first_seen / last_seen / days_active) from these dates.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from fetch_sources import extract_all, SNAPSHOT  # noqa: E402

log = logging.getLogger("ingestion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = ROOT / "warehouse.duckdb"
RAW_DIR = ROOT / "data" / "raw"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if args.offline:
        from synthetic import generate
        df = generate()
        log.warning("Using SYNTHETIC sample (%d postings)", len(df))
    else:
        log.info("Extracting from 4 job-board APIs…")
        df = extract_all()
        if df.empty:
            log.error("All sources failed — aborting to protect the warehouse")
            return 1
        log.info("Extracted %d data postings total", len(df))

    # -------------------- raw snapshot archive --------------------
    snap = df["snapshot_date"].iloc[0]
    out = RAW_DIR / f"snapshot_date={snap}"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "jobs.parquet", index=False)

    # ------------- idempotent append into duckdb -------------
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw_job_postings AS
        SELECT * FROM df LIMIT 0
    """)
    con.execute("DELETE FROM raw_job_postings WHERE snapshot_date = ? AND source IN "
                "(SELECT DISTINCT source FROM df)", [snap])
    con.register("_append", df)
    con.execute("INSERT INTO raw_job_postings SELECT * FROM _append")
    con.unregister("_append")

    stats = con.execute("""
        SELECT count(*) total_rows,
               count(DISTINCT source || ':' || external_id) distinct_jobs,
               count(DISTINCT snapshot_date) snapshots,
               min(snapshot_date) first_snap, max(snapshot_date) latest_snap
        FROM raw_job_postings
    """).fetchone()
    con.close()
    log.info("Loaded %d rows for snapshot %s", len(df), snap)
    log.info("Warehouse: %d rows · %d jobs · %d snapshots (%s → %s)",
             *stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
